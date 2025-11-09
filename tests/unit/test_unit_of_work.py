"""Tests for Unit of Work pattern.

Test Organization:
- TestUnitOfWorkContextManager: Context manager lifecycle
- TestUnitOfWorkCommit: Commit behavior and scenarios
- TestUnitOfWorkRollback: Rollback behavior and scenarios
- TestUnitOfWorkRepositories: Repository management
- TestUnitOfWorkSessionLifecycle: Session creation and cleanup
- TestUnitOfWorkErrorHandling: Error handling and edge cases
- TestGetUnitOfWorkHelper: get_unit_of_work helper function
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infrastructure.persistence.unit_of_work import UnitOfWork, get_unit_of_work
from src.infrastructure.repositories.user_repository import UserRepository


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock database session.

    Returns:
        AsyncMock configured as AsyncSession
    """
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    """Create mock session factory.

    Args:
        mock_session: Mock session to return from factory

    Returns:
        MagicMock configured as async_sessionmaker
    """
    factory = MagicMock(spec=async_sessionmaker)
    factory.return_value = mock_session
    return factory


# ============================================================================
# Context Manager Tests
# ============================================================================


class TestUnitOfWorkContextManager:
    """Test UnitOfWork context manager lifecycle."""

    async def test_enter_creates_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test __aenter__ creates database session.

        Arrange: Mock session factory
        Act: Enter UnitOfWork context
        Assert: Session is created from factory
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act
        await uow.__aenter__()

        # Assert
        assert uow._session is mock_session
        mock_session_factory.assert_called_once()

    async def test_enter_initializes_repositories(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test __aenter__ initializes repositories.

        Arrange: Mock session factory
        Act: Enter UnitOfWork context
        Assert: Repositories are initialized with session
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act
        async with uow:
            # Assert
            assert isinstance(uow.users, UserRepository)
            assert uow.users._session is mock_session

    async def test_enter_returns_self(self, mock_session_factory: MagicMock) -> None:
        """Test __aenter__ returns self for 'as' clause.

        Arrange: UnitOfWork instance
        Act: Enter context
        Assert: Returns self
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act
        result = await uow.__aenter__()

        # Assert
        assert result is uow

    async def test_exit_commits_on_success(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test __aexit__ commits when no exception occurs.

        Arrange: UnitOfWork in successful transaction
        Act: Exit context without exception
        Assert: Session is committed
        """
        # Arrange & Act
        async with UnitOfWork(mock_session_factory):
            pass

        # Assert
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    async def test_exit_rolls_back_on_exception(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test __aexit__ rolls back when exception occurs.

        Arrange: UnitOfWork in transaction
        Act: Raise exception in context
        Assert: Session is rolled back, not committed
        """
        # Arrange & Act
        with pytest.raises(ValueError, match="Test error"):
            async with UnitOfWork(mock_session_factory):
                raise ValueError("Test error")

        # Assert
        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()

    async def test_exit_closes_session_on_success(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test __aexit__ closes session after successful commit.

        Arrange: UnitOfWork in successful transaction
        Act: Exit context
        Assert: Session is closed
        """
        # Arrange & Act
        async with UnitOfWork(mock_session_factory):
            pass

        # Assert
        mock_session.close.assert_awaited_once()

    async def test_exit_closes_session_on_exception(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test __aexit__ closes session after rollback.

        Arrange: UnitOfWork with exception
        Act: Exit context with exception
        Assert: Session is closed even after rollback
        """
        # Arrange & Act
        with pytest.raises(ValueError):
            async with UnitOfWork(mock_session_factory):
                raise ValueError("Test error")

        # Assert
        mock_session.close.assert_awaited_once()

    async def test_exit_without_enter_is_safe(self, mock_session_factory: MagicMock) -> None:
        """Test __aexit__ is safe when session is None.

        Arrange: UnitOfWork without entering context
        Act: Call __aexit__ directly
        Assert: No errors raised
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act
        await uow.__aexit__(None, None, None)

        # Assert: No exception raised

    async def test_exit_sets_session_to_none(self, mock_session_factory: MagicMock) -> None:
        """Test __aexit__ sets session to None after closing.

        Arrange: UnitOfWork in context
        Act: Exit context
        Assert: Session is set to None
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)
        async with uow:
            assert uow._session is not None

        # Assert
        assert uow._session is None


# ============================================================================
# Commit Tests
# ============================================================================


class TestUnitOfWorkCommit:
    """Test UnitOfWork commit behavior."""

    async def test_commit_calls_session_commit(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test commit calls session.commit().

        Arrange: UnitOfWork in context
        Act: Call commit()
        Assert: Session commit is called
        """
        # Arrange
        async with UnitOfWork(mock_session_factory) as uow:
            # Act
            await uow.commit()

        # Assert
        assert mock_session.commit.await_count >= 1

    async def test_manual_commit_within_transaction(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test manual commit within transaction.

        Arrange: UnitOfWork in context
        Act: Call commit() manually
        Assert: Commit called, plus automatic commit on exit
        """
        # Arrange
        async with UnitOfWork(mock_session_factory) as uow:
            # Act
            await uow.commit()

            # Assert: manual commit
            assert mock_session.commit.await_count == 1

        # Assert: automatic commit on exit
        assert mock_session.commit.await_count == 2

    async def test_commit_without_session_raises_error(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test commit raises error when called outside context.

        Arrange: UnitOfWork outside context
        Act: Call commit()
        Assert: RuntimeError raised
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot commit: session not initialized"):
            await uow.commit()

    async def test_commit_after_exit_raises_error(self, mock_session_factory: MagicMock) -> None:
        """Test commit raises error after context exit.

        Arrange: UnitOfWork after exiting context
        Act: Call commit()
        Assert: RuntimeError raised
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)
        async with uow:
            pass

        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot commit: session not initialized"):
            await uow.commit()

    async def test_multiple_manual_commits(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test multiple manual commits in same transaction.

        Arrange: UnitOfWork in context
        Act: Call commit() multiple times
        Assert: Each commit calls session.commit()
        """
        # Arrange
        async with UnitOfWork(mock_session_factory) as uow:
            # Act
            await uow.commit()
            await uow.commit()
            await uow.commit()

            # Assert: 3 manual commits
            assert mock_session.commit.await_count == 3

        # Assert: + 1 automatic commit on exit
        assert mock_session.commit.await_count == 4


# ============================================================================
# Rollback Tests
# ============================================================================


class TestUnitOfWorkRollback:
    """Test UnitOfWork rollback behavior."""

    async def test_rollback_calls_session_rollback(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test rollback calls session.rollback().

        Arrange: UnitOfWork in context
        Act: Call rollback()
        Assert: Session rollback is called
        """
        # Arrange
        async with UnitOfWork(mock_session_factory) as uow:
            # Act
            await uow.rollback()

        # Assert
        mock_session.rollback.assert_awaited_once()

    async def test_manual_rollback_within_transaction(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test manual rollback within transaction.

        Arrange: UnitOfWork in context
        Act: Call rollback() manually
        Assert: Rollback called, transaction still commits on exit
        """
        # Arrange
        async with UnitOfWork(mock_session_factory) as uow:
            # Act
            await uow.rollback()

            # Assert: manual rollback
            mock_session.rollback.assert_awaited_once()

        # Assert: automatic commit on exit (even after manual rollback)
        mock_session.commit.assert_awaited_once()

    async def test_rollback_without_session_raises_error(
        self, mock_session_factory: MagicMock
    ) -> None:
        """Test rollback raises error when called outside context.

        Arrange: UnitOfWork outside context
        Act: Call rollback()
        Assert: RuntimeError raised
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot rollback: session not initialized"):
            await uow.rollback()

    async def test_rollback_after_exit_raises_error(self, mock_session_factory: MagicMock) -> None:
        """Test rollback raises error after context exit.

        Arrange: UnitOfWork after exiting context
        Act: Call rollback()
        Assert: RuntimeError raised
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)
        async with uow:
            pass

        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot rollback: session not initialized"):
            await uow.rollback()

    async def test_automatic_rollback_on_exception(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test automatic rollback when exception is raised.

        Arrange: UnitOfWork in context
        Act: Raise exception
        Assert: Rollback is called automatically
        """
        # Arrange & Act
        with pytest.raises(ValueError):
            async with UnitOfWork(mock_session_factory):
                raise ValueError("Test error")

        # Assert
        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()


# ============================================================================
# Repository Tests
# ============================================================================


class TestUnitOfWorkRepositories:
    """Test UnitOfWork repository management."""

    async def test_users_repository_initialized(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test users repository is initialized on enter.

        Arrange: UnitOfWork
        Act: Enter context
        Assert: users repository is UserRepository instance
        """
        # Arrange & Act
        async with UnitOfWork(mock_session_factory) as uow:
            # Assert
            assert isinstance(uow.users, UserRepository)

    async def test_users_repository_uses_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test users repository uses UoW session.

        Arrange: UnitOfWork in context
        Act: Access users repository
        Assert: Repository uses same session
        """
        # Arrange & Act
        async with UnitOfWork(mock_session_factory) as uow:
            # Assert
            assert uow.users._session is mock_session

    async def test_repositories_share_same_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test all repositories share the same session.

        Arrange: UnitOfWork in context
        Act: Access multiple repositories
        Assert: All use the same session instance
        """
        # Arrange & Act
        async with UnitOfWork(mock_session_factory) as uow:
            # Assert: all repositories use same session
            assert uow.users._session is mock_session


# ============================================================================
# Session Lifecycle Tests
# ============================================================================


class TestUnitOfWorkSessionLifecycle:
    """Test UnitOfWork session lifecycle management."""

    async def test_session_is_none_before_enter(self, mock_session_factory: MagicMock) -> None:
        """Test session is None before entering context.

        Arrange: UnitOfWork instance
        Act: Check _session
        Assert: _session is None
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Assert
        assert uow._session is None

    async def test_session_created_on_enter(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test session is created when entering context.

        Arrange: UnitOfWork
        Act: Enter context
        Assert: _session is set to mock session
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act
        async with uow:
            # Assert
            assert uow._session is mock_session

    async def test_session_is_none_after_exit(self, mock_session_factory: MagicMock) -> None:
        """Test session is set to None after exiting context.

        Arrange: UnitOfWork
        Act: Exit context
        Assert: _session is None
        """
        # Arrange
        uow = UnitOfWork(mock_session_factory)

        # Act
        async with uow:
            pass

        # Assert
        assert uow._session is None

    async def test_session_closed_on_successful_exit(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test session is closed on successful exit.

        Arrange: UnitOfWork in successful transaction
        Act: Exit context
        Assert: Session close is called
        """
        # Arrange & Act
        async with UnitOfWork(mock_session_factory):
            pass

        # Assert
        mock_session.close.assert_awaited_once()

    async def test_session_closed_on_failed_exit(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test session is closed even when exception occurs.

        Arrange: UnitOfWork with exception
        Act: Exit context with exception
        Assert: Session is still closed
        """
        # Arrange & Act
        with pytest.raises(ValueError):
            async with UnitOfWork(mock_session_factory):
                raise ValueError("Test error")

        # Assert
        mock_session.close.assert_awaited_once()


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestUnitOfWorkErrorHandling:
    """Test UnitOfWork error handling and edge cases."""

    async def test_commit_error_still_closes_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test session is closed even if commit fails.

        Arrange: Mock commit to raise error
        Act: Exit context (triggers commit)
        Assert: Session is still closed despite error
        """
        # Arrange
        mock_session.commit.side_effect = RuntimeError("Commit failed")

        # Act
        with pytest.raises(RuntimeError, match="Commit failed"):
            async with UnitOfWork(mock_session_factory):
                pass

        # Assert
        mock_session.close.assert_awaited_once()

    async def test_rollback_error_still_closes_session(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test session is closed even if rollback fails.

        Arrange: Mock rollback to raise error
        Act: Exit context with exception (triggers rollback)
        Assert: Session is still closed despite rollback error
        """
        # Arrange
        mock_session.rollback.side_effect = RuntimeError("Rollback failed")

        # Act: Rollback error replaces original exception
        with pytest.raises(RuntimeError, match="Rollback failed"):
            async with UnitOfWork(mock_session_factory):
                raise ValueError("Original error")

        # Assert
        mock_session.close.assert_awaited_once()

    async def test_close_error_is_propagated(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test close error is propagated if no other exception.

        Arrange: Mock close to raise error
        Act: Exit context (triggers close)
        Assert: Close error is raised
        """
        # Arrange
        mock_session.close.side_effect = RuntimeError("Close failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Close failed"):
            async with UnitOfWork(mock_session_factory):
                pass

    async def test_exception_propagated_after_rollback(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test original exception is propagated after rollback.

        Arrange: UnitOfWork
        Act: Raise exception in context
        Assert: Original exception is propagated, not swallowed
        """
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Original error"):
            async with UnitOfWork(mock_session_factory):
                raise ValueError("Original error")

    async def test_exception_type_preserved(self, mock_session_factory: MagicMock) -> None:
        """Test exception type is preserved through rollback.

        Arrange: UnitOfWork
        Act: Raise specific exception type
        Assert: Same exception type is propagated
        """

        # Arrange
        class CustomError(Exception):
            pass

        # Act & Assert
        with pytest.raises(CustomError):
            async with UnitOfWork(mock_session_factory):
                raise CustomError("Custom error")


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestGetUnitOfWorkHelper:
    """Test get_unit_of_work helper function."""

    async def test_yields_unit_of_work_instance(self, mock_session_factory: MagicMock) -> None:
        """Test get_unit_of_work yields UnitOfWork instance.

        Arrange: Mock session factory
        Act: Use get_unit_of_work as context manager
        Assert: Yields UnitOfWork instance
        """
        # Arrange & Act
        async with get_unit_of_work(mock_session_factory) as uow:
            # Assert
            assert isinstance(uow, UnitOfWork)

    async def test_yields_initialized_unit_of_work(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test get_unit_of_work yields initialized UoW.

        Arrange: Mock session factory
        Act: Use get_unit_of_work
        Assert: UoW has session and repositories initialized
        """
        # Arrange & Act
        async with get_unit_of_work(mock_session_factory) as uow:
            # Assert
            assert uow._session is mock_session
            assert isinstance(uow.users, UserRepository)

    async def test_commits_on_successful_completion(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test get_unit_of_work commits on success.

        Arrange: Mock session factory
        Act: Complete context successfully
        Assert: Session is committed
        """
        # Arrange & Act
        async with get_unit_of_work(mock_session_factory):
            pass

        # Assert
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    async def test_rolls_back_on_exception(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test get_unit_of_work rolls back on exception.

        Arrange: Mock session factory
        Act: Raise exception in context
        Assert: Session is rolled back, not committed
        """
        # Arrange & Act
        with pytest.raises(ValueError):
            async with get_unit_of_work(mock_session_factory):
                raise ValueError("Test error")

        # Assert
        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()

    async def test_closes_session_on_completion(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test get_unit_of_work closes session.

        Arrange: Mock session factory
        Act: Complete context
        Assert: Session is closed
        """
        # Arrange & Act
        async with get_unit_of_work(mock_session_factory):
            pass

        # Assert
        mock_session.close.assert_awaited_once()

    async def test_closes_session_on_exception(
        self, mock_session_factory: MagicMock, mock_session: AsyncMock
    ) -> None:
        """Test get_unit_of_work closes session even on exception.

        Arrange: Mock session factory
        Act: Raise exception in context
        Assert: Session is closed
        """
        # Arrange & Act
        with pytest.raises(ValueError):
            async with get_unit_of_work(mock_session_factory):
                raise ValueError("Test error")

        # Assert
        mock_session.close.assert_awaited_once()
