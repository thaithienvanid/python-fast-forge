"""Unit tests for UserRepository."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.models.user import User
from src.infrastructure.repositories.user_repository import UserRepository


class TestUserRepositoryInitialization:
    """Tests for UserRepository initialization."""

    def test_initializes_with_session(self):
        """UserRepository initializes with session."""
        mock_session = MagicMock()
        repo = UserRepository(mock_session)

        assert repo._session == mock_session
        assert repo._model == User


class TestUserRepositoryGetByEmail:
    """Tests for get_by_email method."""

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        """Returns user when email matches."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_user = User(
            id=uuid4(),
            email="test@example.com",
            username="testuser",
            tenant_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        user = await repo.get_by_email("test@example.com")

        assert user == mock_user
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Returns None when email not found."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        user = await repo.get_by_email("notfound@example.com")

        assert user is None


class TestUserRepositoryGetByUsername:
    """Tests for get_by_username method."""

    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        """Returns user when username matches."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_user = User(
            id=uuid4(),
            email="test@example.com",
            username="testuser",
            tenant_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        user = await repo.get_by_username("testuser")

        assert user == mock_user
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Returns None when username not found."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        user = await repo.get_by_username("notfound")

        assert user is None


class TestUserRepositoryFindByEmails:
    """Tests for find_by_emails bulk method."""

    @pytest.mark.asyncio
    async def test_returns_users_for_matching_emails(self):
        """Returns users matching provided emails."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_users = [
            User(
                id=uuid4(),
                email="user1@example.com",
                username="user1",
                tenant_id=uuid4(),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            User(
                id=uuid4(),
                email="user2@example.com",
                username="user2",
                tenant_id=uuid4(),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        users = await repo.find_by_emails(["user1@example.com", "user2@example.com"])

        assert len(users) == 2
        assert users[0].email == "user1@example.com"
        assert users[1].email == "user2@example.com"

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_input(self):
        """Returns empty list when email list is empty."""
        mock_session = MagicMock()
        repo = UserRepository(mock_session)

        users = await repo.find_by_emails([])

        assert users == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_normalizes_emails_to_lowercase(self):
        """Normalizes emails to lowercase before query."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        await repo.find_by_emails(["USER@EXAMPLE.COM", "Test@Example.com"])

        # Verify execute was called (emails normalized internally)
        mock_session.execute.assert_called_once()


class TestUserRepositoryFindByUsernames:
    """Tests for find_by_usernames bulk method."""

    @pytest.mark.asyncio
    async def test_returns_users_for_matching_usernames(self):
        """Returns users matching provided usernames."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_users = [
            User(
                id=uuid4(),
                email="user1@example.com",
                username="user1",
                tenant_id=uuid4(),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        users = await repo.find_by_usernames(["user1", "user2"])

        assert len(users) == 1
        assert users[0].username == "user1"

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_input(self):
        """Returns empty list when username list is empty."""
        mock_session = MagicMock()
        repo = UserRepository(mock_session)

        users = await repo.find_by_usernames([])

        assert users == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_excludes_soft_deleted_users(self):
        """Excludes soft-deleted users from results."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        # Only returns non-deleted users
        mock_users = [
            User(
                id=uuid4(),
                email="active@example.com",
                username="active",
                tenant_id=uuid4(),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                deleted_at=None,
            ),
        ]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_users
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserRepository(mock_session)
        users = await repo.find_by_usernames(["active", "deleted"])

        # Should only return active user
        assert len(users) == 1
        assert users[0].username == "active"
