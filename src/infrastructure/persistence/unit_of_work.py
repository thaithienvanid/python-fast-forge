"""Unit of Work pattern for transaction management.

The Unit of Work pattern maintains a list of objects affected by a business transaction
and coordinates the writing out of changes.

Key benefits:
- Single transaction boundary for business operations
- Automatic commit/rollback handling
- Explicit transaction lifecycle
- Prevents partial updates from failures
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.domain.interfaces import IUserRepository
from src.domain.models.user import User
from src.infrastructure.repositories.user_repository import UserRepository


class IUnitOfWork(Protocol):
    """Unit of Work interface.

    Defines the contract for managing transactions and repositories.
    All repositories are accessed through the UoW to ensure they share
    the same database session and transaction.
    """

    users: IUserRepository[User]
    """User repository within this transaction"""

    async def commit(self) -> None:
        """Commit the current transaction.

        Persists all changes made through repositories to the database.
        """
        ...

    async def rollback(self) -> None:
        """Rollback the current transaction.

        Discards all changes made through repositories.
        """
        ...

    async def __aenter__(self) -> "IUnitOfWork":
        """Enter the context manager."""
        ...

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Exit the context manager."""
        ...


class UnitOfWork:
    """SQLAlchemy implementation of Unit of Work pattern.

    Manages database transactions and provides repository instances that share
    the same session. Automatically commits on success or rolls back on error.

    Example:
        ```python
        async with UnitOfWork(session_factory) as uow:
            # All repository operations share same transaction
            user = await uow.users.get_by_id(user_id)
            user.email = "new@example.com"
            await uow.users.update(user)

            # Commit is automatic on successful exit
            # Rollback is automatic if exception occurs
        ```
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize Unit of Work.

        Args:
            session_factory: Factory for creating database sessions
        """
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "UnitOfWork":
        """Enter context: create session and initialize repositories.

        Returns:
            Self with initialized repositories
        """
        # Create new session for this transaction
        self._session = self._session_factory()

        # Initialize all repositories with the same session
        # This ensures they all participate in the same transaction
        self.users = UserRepository(self._session)

        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Exit context: commit or rollback based on exceptions.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        if self._session is None:
            return

        try:
            if exc_type is None:
                # No exception: commit the transaction
                await self.commit()
            else:
                # Exception occurred: rollback the transaction
                await self.rollback()
        finally:
            # Always close the session
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        """Commit all changes in the current transaction.

        Raises:
            RuntimeError: If called outside of context manager
        """
        if self._session is None:
            raise RuntimeError("Cannot commit: session not initialized")
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback all changes in the current transaction.

        Raises:
            RuntimeError: If called outside of context manager
        """
        if self._session is None:
            raise RuntimeError("Cannot rollback: session not initialized")
        await self._session.rollback()


@asynccontextmanager
async def get_unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[UnitOfWork]:
    """Get Unit of Work instance as context manager.

    This is a convenience function for dependency injection that ensures
    proper transaction handling.

    Args:
        session_factory: Database session factory

    Yields:
        Unit of Work instance

    Example:
        ```python
        async with get_unit_of_work(session_factory) as uow:
            user = await uow.users.get_by_email("test@example.com")
            # ... use user
        ```
    """
    async with UnitOfWork(session_factory) as uow:
        yield uow
