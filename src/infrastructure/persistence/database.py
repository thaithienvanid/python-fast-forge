"""Database connection and session management.

This module provides async SQLAlchemy database connectivity with connection
pooling, session lifecycle management, and health check capabilities.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.config import Settings


class Database:
    """Database connection manager with async SQLAlchemy support.

    Handles database engine creation, connection pooling, session factory
    management, and provides transactional session context managers.

    Connection Pool Configuration:
        - pool_size: Base number of persistent connections
        - max_overflow: Additional connections during traffic spikes
        - pool_pre_ping: Validates connections before use (prevents stale connections)
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize database manager with application settings.

        Args:
            settings: Application configuration containing database connection details
        """
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def get_engine(self) -> AsyncEngine:
        """Get or create the database engine (singleton pattern).

        Lazily initializes the engine on first access with configured
        connection pool settings.

        Returns:
            Async SQLAlchemy engine instance
        """
        if self._engine is None:
            self._engine = create_async_engine(
                self.settings.database_url,
                echo=self.settings.database_echo,
                pool_size=self.settings.database_pool_size,
                max_overflow=self.settings.database_max_overflow,
                pool_pre_ping=True,
            )
        return self._engine

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create the session factory (singleton pattern).

        Configures sessions with:
        - expire_on_commit=False: Allows access to objects after commit
        - autocommit=False: Requires explicit commit for changes
        - autoflush=False: Requires explicit flush for database writes

        Returns:
            Session factory for creating database sessions
        """
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession]:
        """Provide a transactional database session with automatic commit/rollback.

        Usage:
            async with database.session() as session:
                # Perform database operations
                result = await session.execute(query)
                # Automatic commit on success, rollback on exception

        Yields:
            Active database session

        Raises:
            Exception: Re-raises any exception after rolling back transaction
        """
        session_factory = self.get_session_factory()
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Close all database connections and dispose of the engine.

        Should be called during application shutdown to ensure clean
        resource cleanup and prevent connection leaks.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def health_check(self) -> bool:
        """Verify database connectivity with a simple query.

        Executes a lightweight SELECT 1 query to confirm the database
        is accessible and responsive.

        Returns:
            True if database is accessible, False on any error
        """
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
