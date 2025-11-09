"""Tests for database connection manager.

Test Organization:
- TestDatabaseInitialization: Database initialization
- TestDatabaseEngine: Engine creation and caching
- TestDatabaseSessionFactory: Session factory creation
- TestDatabaseSessionContextManager: Session lifecycle
- TestDatabaseClose: Connection cleanup
- TestDatabaseHealthCheck: Health check functionality
- TestDatabaseEdgeCases: Edge cases and boundaries
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.infrastructure.config import Settings
from src.infrastructure.persistence.database import Database


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_settings() -> Settings:
    """Create test database settings.

    Returns:
        Settings instance with test database configuration
    """
    return Settings(
        database_url="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db",
        database_echo=False,
        database_pool_size=5,
        database_max_overflow=10,
    )


@pytest.fixture
def database(test_settings: Settings) -> Database:
    """Create Database instance with test settings.

    Args:
        test_settings: Test database settings

    Returns:
        Database instance for testing
    """
    return Database(test_settings)


# ============================================================================
# Initialization Tests
# ============================================================================


class TestDatabaseInitialization:
    """Test Database initialization."""

    def test_initializes_with_settings(self, test_settings: Settings) -> None:
        """Test Database stores settings on initialization.

        Arrange: Test settings
        Act: Create Database instance
        Assert: Settings are stored
        """
        # Arrange & Act
        db = Database(test_settings)

        # Assert
        assert db.settings is test_settings

    def test_engine_starts_as_none(self, test_settings: Settings) -> None:
        """Test _engine is None before first access.

        Arrange: Test settings
        Act: Create Database instance
        Assert: _engine is None
        """
        # Arrange & Act
        db = Database(test_settings)

        # Assert
        assert db._engine is None

    def test_session_factory_starts_as_none(self, test_settings: Settings) -> None:
        """Test _session_factory is None before first access.

        Arrange: Test settings
        Act: Create Database instance
        Assert: _session_factory is None
        """
        # Arrange & Act
        db = Database(test_settings)

        # Assert
        assert db._session_factory is None

    def test_initializes_with_different_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Database can be initialized with different settings.

        Arrange: Different database URL via environment
        Act: Create Database instances
        Assert: Each has its own settings
        """
        # Arrange
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db1/test")
        settings1 = Settings()

        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db2/test")
        settings2 = Settings()

        # Act
        db1 = Database(settings1)
        db2 = Database(settings2)

        # Assert
        assert db1.settings.database_url != db2.settings.database_url


# ============================================================================
# Engine Tests
# ============================================================================


class TestDatabaseEngine:
    """Test engine creation and caching."""

    def test_get_engine_creates_engine_on_first_call(
        self, database: Database, test_settings: Settings
    ) -> None:
        """Test get_engine creates engine on first call.

        Arrange: Database with no engine
        Act: Call get_engine()
        Assert: Engine is created with correct settings
        """
        # Arrange
        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine

            # Act
            engine = database.get_engine()

            # Assert
            assert engine is mock_engine
            mock_create.assert_called_once_with(
                test_settings.database_url,
                echo=test_settings.database_echo,
                pool_size=test_settings.database_pool_size,
                max_overflow=test_settings.database_max_overflow,
                pool_pre_ping=True,
            )

    def test_get_engine_caches_engine(self, database: Database) -> None:
        """Test get_engine stores created engine in _engine.

        Arrange: Database with mock engine
        Act: Call get_engine()
        Assert: Engine is cached in _engine
        """
        # Arrange
        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine

            # Act
            database.get_engine()

            # Assert
            assert database._engine is mock_engine

    def test_get_engine_returns_cached_engine_on_subsequent_calls(self, database: Database) -> None:
        """Test get_engine returns cached engine without recreating.

        Arrange: Database
        Act: Call get_engine() twice
        Assert: Same engine returned, create called once
        """
        # Arrange
        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine

            # Act
            engine1 = database.get_engine()
            engine2 = database.get_engine()

            # Assert
            assert engine1 is engine2
            mock_create.assert_called_once()

    def test_get_engine_uses_pool_pre_ping(self, database: Database) -> None:
        """Test get_engine enables pool_pre_ping for connection health checks.

        Arrange: Database
        Act: Call get_engine()
        Assert: pool_pre_ping is True
        """
        # Arrange
        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine

            # Act
            database.get_engine()

            # Assert
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["pool_pre_ping"] is True

    def test_get_engine_uses_database_echo_setting(self, test_settings: Settings) -> None:
        """Test get_engine respects database_echo setting.

        Arrange: Settings with echo=True
        Act: Call get_engine()
        Assert: Echo setting is passed to create_async_engine
        """
        # Arrange
        test_settings.database_echo = True
        db = Database(test_settings)

        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine

            # Act
            db.get_engine()

            # Assert
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["echo"] is True


# ============================================================================
# Session Factory Tests
# ============================================================================


class TestDatabaseSessionFactory:
    """Test session factory creation and caching."""

    def test_get_session_factory_creates_factory_on_first_call(self, database: Database) -> None:
        """Test get_session_factory creates factory on first call.

        Arrange: Database with no factory
        Act: Call get_session_factory()
        Assert: Factory is created with correct settings
        """
        # Arrange
        with (
            patch("src.infrastructure.persistence.database.create_async_engine"),
            patch("src.infrastructure.persistence.database.async_sessionmaker") as mock_maker,
        ):
            mock_factory = MagicMock(spec=async_sessionmaker)
            mock_maker.return_value = mock_factory

            # Act
            factory = database.get_session_factory()

            # Assert
            assert factory is mock_factory
            mock_maker.assert_called_once()

    def test_get_session_factory_uses_correct_settings(self, database: Database) -> None:
        """Test get_session_factory uses correct session settings.

        Arrange: Database
        Act: Call get_session_factory()
        Assert: Factory created with expire_on_commit=False, autocommit=False, autoflush=False
        """
        # Arrange
        with (
            patch("src.infrastructure.persistence.database.create_async_engine"),
            patch("src.infrastructure.persistence.database.async_sessionmaker") as mock_maker,
        ):
            mock_factory = MagicMock(spec=async_sessionmaker)
            mock_maker.return_value = mock_factory

            # Act
            database.get_session_factory()

            # Assert
            call_kwargs = mock_maker.call_args.kwargs
            assert call_kwargs["class_"] == AsyncSession
            assert call_kwargs["expire_on_commit"] is False
            assert call_kwargs["autocommit"] is False
            assert call_kwargs["autoflush"] is False

    def test_get_session_factory_binds_to_engine(self, database: Database) -> None:
        """Test get_session_factory binds factory to engine.

        Arrange: Database with mock engine
        Act: Call get_session_factory()
        Assert: Factory is bound to engine
        """
        # Arrange
        with (
            patch("src.infrastructure.persistence.database.create_async_engine") as mock_create,
            patch("src.infrastructure.persistence.database.async_sessionmaker") as mock_maker,
        ):
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine
            mock_factory = MagicMock(spec=async_sessionmaker)
            mock_maker.return_value = mock_factory

            # Act
            database.get_session_factory()

            # Assert
            call_kwargs = mock_maker.call_args.kwargs
            assert call_kwargs["bind"] is mock_engine

    def test_get_session_factory_caches_factory(self, database: Database) -> None:
        """Test get_session_factory stores created factory.

        Arrange: Database
        Act: Call get_session_factory()
        Assert: Factory is cached in _session_factory
        """
        # Arrange
        with (
            patch("src.infrastructure.persistence.database.create_async_engine"),
            patch("src.infrastructure.persistence.database.async_sessionmaker") as mock_maker,
        ):
            mock_factory = MagicMock(spec=async_sessionmaker)
            mock_maker.return_value = mock_factory

            # Act
            database.get_session_factory()

            # Assert
            assert database._session_factory is mock_factory

    def test_get_session_factory_returns_cached_factory(self, database: Database) -> None:
        """Test get_session_factory returns cached factory.

        Arrange: Database
        Act: Call get_session_factory() twice
        Assert: Same factory returned, created once
        """
        # Arrange
        with (
            patch("src.infrastructure.persistence.database.create_async_engine"),
            patch("src.infrastructure.persistence.database.async_sessionmaker") as mock_maker,
        ):
            mock_factory = MagicMock(spec=async_sessionmaker)
            mock_maker.return_value = mock_factory

            # Act
            factory1 = database.get_session_factory()
            factory2 = database.get_session_factory()

            # Assert
            assert factory1 is factory2
            mock_maker.assert_called_once()


# ============================================================================
# Session Context Manager Tests
# ============================================================================


class TestDatabaseSessionContextManager:
    """Test session context manager lifecycle."""

    async def test_session_yields_async_session(self, database: Database) -> None:
        """Test session() yields AsyncSession instance.

        Arrange: Database with mock session
        Act: Use session() context manager
        Assert: AsyncSession is yielded
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(spec=async_sessionmaker)
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None
        database._session_factory = mock_factory

        # Act
        async with database.session() as session:
            # Assert
            assert session is mock_session

    async def test_session_commits_on_success(self, database: Database) -> None:
        """Test session() commits on successful completion.

        Arrange: Database with mock session
        Act: Complete session context successfully
        Assert: Session commit is called
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(spec=async_sessionmaker)
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None
        database._session_factory = mock_factory

        # Act
        async with database.session():
            pass

        # Assert
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    async def test_session_rolls_back_on_exception(self, database: Database) -> None:
        """Test session() rolls back when exception occurs.

        Arrange: Database with mock session
        Act: Raise exception in session context
        Assert: Session rollback is called, not commit
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(spec=async_sessionmaker)
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None
        database._session_factory = mock_factory

        # Act
        with pytest.raises(ValueError, match="Test error"):
            async with database.session():
                raise ValueError("Test error")

        # Assert
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()

    async def test_session_propagates_exception(self, database: Database) -> None:
        """Test session() propagates exceptions after rollback.

        Arrange: Database with mock session
        Act: Raise exception in session
        Assert: Exception is propagated
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(spec=async_sessionmaker)
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None
        database._session_factory = mock_factory

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database error"):
            async with database.session():
                raise RuntimeError("Database error")

    async def test_session_calls_get_session_factory(self, database: Database) -> None:
        """Test session() calls get_session_factory.

        Arrange: Database
        Act: Use session() context manager
        Assert: get_session_factory is called
        """
        # Arrange
        with patch.object(database, "get_session_factory") as mock_get_factory:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_factory = MagicMock(spec=async_sessionmaker)
            mock_factory.return_value.__aenter__.return_value = mock_session
            mock_factory.return_value.__aexit__.return_value = None
            mock_get_factory.return_value = mock_factory

            # Act
            async with database.session():
                pass

            # Assert
            mock_get_factory.assert_called_once()


# ============================================================================
# Close Tests
# ============================================================================


class TestDatabaseClose:
    """Test database connection cleanup."""

    async def test_close_disposes_engine(self, database: Database) -> None:
        """Test close() disposes engine.

        Arrange: Database with mock engine
        Act: Call close()
        Assert: Engine dispose is called
        """
        # Arrange
        mock_engine = AsyncMock(spec=AsyncEngine)
        database._engine = mock_engine

        # Act
        await database.close()

        # Assert
        mock_engine.dispose.assert_called_once()

    async def test_close_clears_engine_reference(self, database: Database) -> None:
        """Test close() sets _engine to None.

        Arrange: Database with engine
        Act: Call close()
        Assert: _engine is None
        """
        # Arrange
        mock_engine = AsyncMock(spec=AsyncEngine)
        database._engine = mock_engine

        # Act
        await database.close()

        # Assert
        assert database._engine is None

    async def test_close_clears_session_factory_reference(self, database: Database) -> None:
        """Test close() sets _session_factory to None.

        Arrange: Database with session factory
        Act: Call close()
        Assert: _session_factory is None
        """
        # Arrange
        mock_engine = AsyncMock(spec=AsyncEngine)
        database._engine = mock_engine
        database._session_factory = MagicMock()

        # Act
        await database.close()

        # Assert
        assert database._session_factory is None

    async def test_close_when_no_engine_is_safe(self, database: Database) -> None:
        """Test close() is safe when no engine exists.

        Arrange: Database with no engine
        Act: Call close()
        Assert: No errors raised
        """
        # Arrange
        assert database._engine is None

        # Act
        await database.close()

        # Assert: No exception raised
        assert database._engine is None

    async def test_close_can_be_called_multiple_times(self, database: Database) -> None:
        """Test close() can be called multiple times safely.

        Arrange: Database
        Act: Call close() twice
        Assert: No errors raised
        """
        # Arrange
        mock_engine = AsyncMock(spec=AsyncEngine)
        database._engine = mock_engine

        # Act
        await database.close()
        await database.close()

        # Assert: No exception raised


# ============================================================================
# Health Check Tests
# ============================================================================


class TestDatabaseHealthCheck:
    """Test database health check functionality."""

    async def test_health_check_returns_true_on_success(self, database: Database) -> None:
        """Test health_check returns True when database is accessible.

        Arrange: Database with working session
        Act: Call health_check()
        Assert: Returns True
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock()

        with patch.object(database, "session") as mock_context:
            mock_context.return_value.__aenter__.return_value = mock_session
            mock_context.return_value.__aexit__.return_value = None

            # Act
            result = await database.health_check()

            # Assert
            assert result is True

    async def test_health_check_executes_select_one(self, database: Database) -> None:
        """Test health_check executes 'SELECT 1' query.

        Arrange: Database with mock session
        Act: Call health_check()
        Assert: Session execute is called with SELECT 1
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock()

        with patch.object(database, "session") as mock_context:
            mock_context.return_value.__aenter__.return_value = mock_session
            mock_context.return_value.__aexit__.return_value = None

            # Act
            await database.health_check()

            # Assert
            mock_session.execute.assert_called_once()
            # Verify SQL text contains SELECT 1
            call_args = mock_session.execute.call_args[0][0]
            assert "SELECT 1" in str(call_args)

    async def test_health_check_returns_false_on_session_creation_failure(
        self, database: Database
    ) -> None:
        """Test health_check returns False when session creation fails.

        Arrange: Database with session that raises on entry
        Act: Call health_check()
        Assert: Returns False
        """
        # Arrange
        with patch.object(database, "session") as mock_context:
            mock_context.return_value.__aenter__.side_effect = Exception("Connection failed")

            # Act
            result = await database.health_check()

            # Assert
            assert result is False

    async def test_health_check_returns_false_on_query_failure(self, database: Database) -> None:
        """Test health_check returns False when query fails.

        Arrange: Database with session that fails on execute
        Act: Call health_check()
        Assert: Returns False
        """
        # Arrange
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(side_effect=Exception("Query failed"))

        with patch.object(database, "session") as mock_context:
            mock_context.return_value.__aenter__.return_value = mock_session
            mock_context.return_value.__aexit__.return_value = None

            # Act
            result = await database.health_check()

            # Assert
            assert result is False

    async def test_health_check_handles_timeout_errors(self, database: Database) -> None:
        """Test health_check handles timeout errors gracefully.

        Arrange: Database with session that times out
        Act: Call health_check()
        Assert: Returns False without raising
        """
        # Arrange
        with patch.object(database, "session") as mock_context:
            mock_context.return_value.__aenter__.side_effect = TimeoutError("Connection timeout")

            # Act
            result = await database.health_check()

            # Assert
            assert result is False


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestDatabaseEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_multiple_database_instances_are_independent(self, test_settings: Settings) -> None:
        """Test multiple Database instances don't share state.

        Arrange: Two Database instances
        Act: Create engines for both
        Assert: Each has independent engine
        """
        # Arrange
        db1 = Database(test_settings)
        db2 = Database(test_settings)

        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine1 = MagicMock(spec=AsyncEngine)
            mock_engine2 = MagicMock(spec=AsyncEngine)
            mock_create.side_effect = [mock_engine1, mock_engine2]

            # Act
            engine1 = db1.get_engine()
            engine2 = db2.get_engine()

            # Assert
            assert engine1 is not engine2
            assert mock_create.call_count == 2

    async def test_get_engine_after_close_creates_new_engine(self, database: Database) -> None:
        """Test get_engine creates new engine after close.

        Arrange: Database with engine
        Act: Close, then get_engine again
        Assert: New engine is created
        """
        # Arrange
        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine1 = AsyncMock(spec=AsyncEngine)
            mock_engine2 = MagicMock(spec=AsyncEngine)
            mock_create.side_effect = [mock_engine1, mock_engine2]

            # Act
            engine1 = database.get_engine()
            await database.close()
            engine2 = database.get_engine()

            # Assert
            assert engine1 is not engine2
            assert mock_create.call_count == 2

    def test_get_session_factory_with_custom_pool_size(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test session factory with custom pool size settings.

        Arrange: Settings with custom pool size via environment
        Act: Create engine
        Assert: Pool size is used
        """
        # Arrange
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test/db")
        monkeypatch.setenv("DATABASE_POOL_SIZE", "20")
        monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "40")
        settings = Settings()
        db = Database(settings)

        with patch("src.infrastructure.persistence.database.create_async_engine") as mock_create:
            mock_engine = MagicMock(spec=AsyncEngine)
            mock_create.return_value = mock_engine

            # Act
            db.get_engine()

            # Assert
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["pool_size"] == 20
            assert call_kwargs["max_overflow"] == 40
