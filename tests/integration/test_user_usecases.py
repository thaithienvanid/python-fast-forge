"""Integration tests for user use cases."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from uuid_extension import uuid7

from src.app.usecases.user_usecases import (
    BatchCreateUsersUseCase,
    CreateUserUseCase,
    DeleteUserUseCase,
    GetUserUseCase,
    ListUsersUseCase,
    UpdateUserUseCase,
)
from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.domain.models.user import User
from src.infrastructure.persistence.unit_of_work import UnitOfWork


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    return AsyncMock()


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        id=uuid7(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        is_active=True,
        tenant_id=uuid7(),
    )


class TestGetUserUseCase:
    """Test GetUserUseCase for retrieving individual users."""

    async def test_execute_returns_user_when_found(self, mock_repository, sample_user):
        """Test that execute returns user when found in repository.

        Arrange: Mock repository with user, create use case
        Act: Execute use case with user ID
        Assert: Returns expected user, repository called once
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        use_case = GetUserUseCase(mock_repository)

        # Act
        result = await use_case.execute(sample_user.id)

        # Assert
        assert result == sample_user
        mock_repository.get_by_id.assert_called_once_with(sample_user.id)

    async def test_execute_raises_not_found_when_user_missing(self, mock_repository):
        """Test that execute raises EntityNotFoundError when user not found.

        Arrange: Mock repository returns None, create use case
        Act: Execute use case with non-existent user ID
        Assert: Raises EntityNotFoundError
        """
        # Arrange
        user_id = uuid7()
        mock_repository.get_by_id.return_value = None
        use_case = GetUserUseCase(mock_repository)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(user_id)

    async def test_execute_enforces_tenant_isolation(self, mock_repository, sample_user):
        """Test that execute enforces tenant isolation when tenant_id provided.

        Arrange: Mock repository with user from different tenant
        Act: Execute use case with different tenant_id
        Assert: Raises EntityNotFoundError (access denied)
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        use_case = GetUserUseCase(mock_repository)
        different_tenant_id = uuid7()

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(sample_user.id, tenant_id=different_tenant_id)

    async def test_execute_allows_access_with_matching_tenant(self, mock_repository, sample_user):
        """Test that execute allows access when tenant_id matches user's tenant.

        Arrange: Mock repository with user, create use case
        Act: Execute use case with matching tenant_id
        Assert: Returns user successfully
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        use_case = GetUserUseCase(mock_repository)

        # Act
        result = await use_case.execute(sample_user.id, tenant_id=sample_user.tenant_id)

        # Assert
        assert result == sample_user


class TestListUsersUseCase:
    """Test ListUsersUseCase for retrieving user lists with pagination."""

    async def test_execute_returns_users(self, mock_repository, sample_user):
        """Test that execute returns list of users from repository.

        Arrange: Mock repository with user list, create use case
        Act: Execute use case without parameters
        Assert: Returns expected user list, repository called once
        """
        # Arrange
        users = [sample_user]
        mock_repository.get_all.return_value = users
        use_case = ListUsersUseCase(mock_repository)

        # Act
        result = await use_case.execute()

        # Assert
        assert result == users
        mock_repository.get_all.assert_called_once()

    async def test_execute_respects_pagination(self, mock_repository):
        """Test that execute passes pagination parameters to repository.

        Arrange: Mock repository, create use case
        Act: Execute use case with skip and limit parameters
        Assert: Repository called with correct pagination values
        """
        # Arrange
        mock_repository.get_all.return_value = []
        use_case = ListUsersUseCase(mock_repository)

        # Act
        await use_case.execute(skip=10, limit=20)

        # Assert
        mock_repository.get_all.assert_called_once_with(skip=10, limit=20, tenant_id=None)

    async def test_execute_raises_validation_error_on_negative_skip(self, mock_repository):
        """Test that execute raises ValidationError for negative skip value.

        Arrange: Create use case
        Act: Execute use case with negative skip
        Assert: Raises ValidationError with appropriate message
        """
        # Arrange
        use_case = ListUsersUseCase(mock_repository)

        # Act & Assert
        with pytest.raises(ValidationError, match="Skip must be non-negative"):
            await use_case.execute(skip=-1)

    async def test_execute_raises_validation_error_on_invalid_limit(self, mock_repository):
        """Test that execute raises ValidationError for invalid limit values.

        Arrange: Create use case
        Act: Execute use case with limit=0 and limit=101
        Assert: Raises ValidationError for both edge cases
        """
        # Arrange
        use_case = ListUsersUseCase(mock_repository)

        # Act & Assert - limit too small
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            await use_case.execute(limit=0)

        # Act & Assert - limit too large
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            await use_case.execute(limit=101)

    async def test_execute_passes_tenant_id(self, mock_repository):
        """Test that execute passes tenant_id to repository for filtering.

        Arrange: Mock repository, create use case with tenant_id
        Act: Execute use case with tenant_id parameter
        Assert: Repository called with tenant_id for filtering
        """
        # Arrange
        tenant_id = uuid7()
        mock_repository.get_all.return_value = []
        use_case = ListUsersUseCase(mock_repository)

        # Act
        await use_case.execute(tenant_id=tenant_id)

        # Assert
        mock_repository.get_all.assert_called_once_with(skip=0, limit=100, tenant_id=tenant_id)


class TestCreateUserUseCase:
    """Test CreateUserUseCase for creating new users."""

    async def test_execute_creates_user(self, mock_repository, sample_user, mock_temporal_client):
        """Test that execute creates user successfully and starts workflow.

        Arrange: Mock repository to return created user, mock Temporal client
        Act: Execute use case with user data
        Assert: Returns created user, repository called, workflow started
        """
        # Arrange
        mock_repository.create.return_value = sample_user
        use_case = CreateUserUseCase(mock_repository)

        # Act
        result = await use_case.execute(
            email=sample_user.email,
            username=sample_user.username,
            full_name=sample_user.full_name,
        )

        # Assert
        assert result == sample_user
        mock_repository.create.assert_called_once()
        # Verify Temporal workflow was started
        mock_temporal_client.start_workflow.assert_called_once()

    async def test_execute_handles_duplicate_email(self, mock_repository):
        """Test that execute raises ValidationError on duplicate email constraint.

        Arrange: Mock repository to raise IntegrityError for email
        Act: Execute use case with duplicate email
        Assert: Raises ValidationError with email message
        """
        # Arrange
        error = IntegrityError(
            "", "", Exception("duplicate key value violates unique constraint on email")
        )
        error.orig = Exception("duplicate key value violates unique constraint on email")
        mock_repository.create.side_effect = error
        use_case = CreateUserUseCase(mock_repository)

        # Act & Assert
        with pytest.raises(ValidationError, match="email .* already exists"):
            await use_case.execute(
                email="duplicate@example.com",
                username="user",
            )

    async def test_execute_handles_duplicate_username(self, mock_repository):
        """Test that execute raises ValidationError on duplicate username constraint.

        Arrange: Mock repository to raise IntegrityError for username
        Act: Execute use case with duplicate username
        Assert: Raises ValidationError with username message
        """
        # Arrange
        error = IntegrityError(
            "", "", Exception("duplicate key value violates unique constraint on username")
        )
        error.orig = Exception("duplicate key value violates unique constraint on username")
        mock_repository.create.side_effect = error
        use_case = CreateUserUseCase(mock_repository)

        # Act & Assert
        with pytest.raises(ValidationError, match="username .* already exists"):
            await use_case.execute(
                email="test@example.com",
                username="duplicate",
            )

    async def test_execute_includes_tenant_id(self, mock_repository, sample_user):
        """Test that execute includes tenant_id in created user when provided.

        Arrange: Mock repository, create use case with tenant_id
        Act: Execute use case with tenant_id parameter
        Assert: Created user has correct tenant_id
        """
        # Arrange
        mock_repository.create.return_value = sample_user
        use_case = CreateUserUseCase(mock_repository)
        tenant_id = uuid7()

        # Act
        await use_case.execute(
            email=sample_user.email,
            username=sample_user.username,
            tenant_id=tenant_id,
        )

        # Assert
        # Verify User object created with tenant_id
        call_args = mock_repository.create.call_args
        created_user = call_args[0][0]
        assert created_user.tenant_id == tenant_id


class TestUpdateUserUseCase:
    """Test UpdateUserUseCase for modifying existing users."""

    async def test_execute_updates_user(self, mock_repository, sample_user):
        """Test that execute updates user successfully with new data.

        Arrange: Mock repository with existing user and updated user
        Act: Execute use case with update data
        Assert: Returns updated user with modified fields
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        updated_user = User(
            id=sample_user.id,
            email="updated@example.com",
            username=sample_user.username,
            full_name="Updated Name",
            is_active=True,
        )
        mock_repository.update.return_value = updated_user
        use_case = UpdateUserUseCase(mock_repository)

        # Act
        result = await use_case.execute(
            user_id=sample_user.id,
            email="updated@example.com",
            full_name="Updated Name",
        )

        # Assert
        assert result.email == "updated@example.com"
        assert result.full_name == "Updated Name"
        mock_repository.update.assert_called_once()

    async def test_execute_raises_not_found_when_user_missing(self, mock_repository):
        """Test that execute raises EntityNotFoundError when user doesn't exist.

        Arrange: Mock repository returns None for user
        Act: Execute use case with non-existent user ID
        Assert: Raises EntityNotFoundError
        """
        # Arrange
        user_id = uuid7()
        mock_repository.get_by_id.return_value = None
        use_case = UpdateUserUseCase(mock_repository)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(user_id, email="test@example.com")

    async def test_execute_enforces_tenant_isolation(self, mock_repository, sample_user):
        """Test that execute enforces tenant isolation on updates.

        Arrange: Mock repository with user from different tenant
        Act: Execute use case with different tenant_id
        Assert: Raises EntityNotFoundError (access denied)
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        use_case = UpdateUserUseCase(mock_repository)
        different_tenant_id = uuid7()

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(
                sample_user.id,
                tenant_id=different_tenant_id,
                email="new@example.com",
            )


class TestDeleteUserUseCase:
    """Test DeleteUserUseCase for removing users."""

    async def test_execute_deletes_user(self, mock_repository, sample_user):
        """Test that execute deletes user successfully.

        Arrange: Mock repository with existing user
        Act: Execute use case with user ID
        Assert: Returns True, repository delete called
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        mock_repository.delete.return_value = True
        use_case = DeleteUserUseCase(mock_repository)

        # Act
        result = await use_case.execute(sample_user.id)

        # Assert
        assert result is True
        mock_repository.delete.assert_called_once_with(sample_user.id)

    async def test_execute_raises_not_found_when_user_missing(self, mock_repository):
        """Test that execute raises EntityNotFoundError when user doesn't exist.

        Arrange: Mock repository returns False for delete (user not found)
        Act: Execute use case with non-existent user ID
        Assert: Raises EntityNotFoundError
        """
        # Arrange
        user_id = uuid7()
        mock_repository.delete.return_value = False
        use_case = DeleteUserUseCase(mock_repository)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(user_id)

    async def test_execute_enforces_tenant_isolation(self, mock_repository, sample_user):
        """Test that execute enforces tenant isolation on deletion.

        Arrange: Mock repository with user from different tenant
        Act: Execute use case with different tenant_id
        Assert: Raises EntityNotFoundError (access denied)
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        use_case = DeleteUserUseCase(mock_repository)
        different_tenant_id = uuid7()

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="not found"):
            await use_case.execute(sample_user.id, tenant_id=different_tenant_id)


class TestBatchCreateUsersUseCase:
    """Tests for BatchCreateUsersUseCase."""

    @pytest.fixture
    def mock_uow(self):
        """Create a mock Unit of Work."""
        uow = AsyncMock(spec=UnitOfWork)
        uow.users = AsyncMock()
        uow.users.get_by_email = AsyncMock(return_value=None)
        uow.users.get_by_username = AsyncMock(return_value=None)
        uow.users.create = AsyncMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=None)
        return uow

    @pytest.fixture
    def mock_uow_factory(self, mock_uow):
        """Create a mock UoW factory."""
        return MagicMock(return_value=mock_uow)

    @pytest.fixture
    def sample_users_data(self):
        """Create sample user data for batch creation."""
        return [
            {
                "email": "user1@example.com",
                "username": "user1",
                "full_name": "User One",
            },
            {
                "email": "user2@example.com",
                "username": "user2",
                "full_name": "User Two",
            },
            {
                "email": "user3@example.com",
                "username": "user3",
                "full_name": None,
            },
        ]

    async def test_execute_creates_multiple_users_successfully(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute creates multiple users in a transaction."""
        # Arrange
        created_users = [
            User(
                id=uuid7(),
                email=data["email"],
                username=data["username"],
                full_name=data.get("full_name"),
                is_active=True,
            )
            for data in sample_users_data
        ]
        mock_uow.users.create.side_effect = created_users
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act
        result = await use_case.execute(sample_users_data)

        # Assert
        assert len(result) == 3
        assert mock_uow.users.create.call_count == 3
        mock_uow.__aenter__.assert_called_once()
        mock_uow.__aexit__.assert_called_once()

    async def test_execute_checks_for_duplicate_emails_in_batch(
        self, mock_uow_factory, sample_users_data
    ):
        """Test that execute raises ValidationError for duplicate emails in batch."""
        # Arrange
        duplicate_data = sample_users_data + [
            {
                "email": "user1@example.com",  # Duplicate
                "username": "user4",
                "full_name": "User Four",
            }
        ]
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate emails found in batch"):
            await use_case.execute(duplicate_data)

    async def test_execute_checks_for_duplicate_usernames_in_batch(
        self, mock_uow_factory, sample_users_data
    ):
        """Test that execute raises ValidationError for duplicate usernames in batch."""
        # Arrange
        duplicate_data = sample_users_data + [
            {
                "email": "user4@example.com",
                "username": "user1",  # Duplicate
                "full_name": "User Four",
            }
        ]
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate usernames found in batch"):
            await use_case.execute(duplicate_data)

    async def test_execute_checks_for_existing_email_in_database(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute raises ValidationError if email already exists in database."""
        # Arrange
        existing_user = User(
            id=uuid7(),
            email="user1@example.com",
            username="existing",
            is_active=True,
        )
        mock_uow.users.get_by_email.return_value = existing_user
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="User with email .* already exists"):
            await use_case.execute(sample_users_data)

    async def test_execute_checks_for_existing_username_in_database(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute raises ValidationError if username already exists in database."""
        # Arrange
        existing_user = User(
            id=uuid7(),
            email="existing@example.com",
            username="user1",
            is_active=True,
        )

        async def get_by_username_side_effect(username):
            if username == "user1":
                return existing_user
            return None

        mock_uow.users.get_by_username.side_effect = get_by_username_side_effect
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="User with username .* already exists"):
            await use_case.execute(sample_users_data)

    async def test_execute_raises_value_error_on_empty_list(self, mock_uow_factory):
        """Test that execute raises ValueError for empty users_data."""
        # Arrange
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValueError, match="users_data cannot be empty"):
            await use_case.execute([])

    async def test_execute_raises_validation_error_on_too_many_users(self, mock_uow_factory):
        """Test that execute raises ValidationError for more than 100 users."""
        # Arrange
        too_many_users = [
            {"email": f"user{i}@example.com", "username": f"user{i}", "full_name": f"User {i}"}
            for i in range(101)
        ]
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="Cannot create more than 100 users at once"):
            await use_case.execute(too_many_users)

    async def test_execute_includes_tenant_id_in_created_users(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute includes tenant_id in all created users."""
        # Arrange
        tenant_id = uuid7()
        created_users = []

        async def create_side_effect(user):
            created_users.append(user)
            return user

        mock_uow.users.create.side_effect = create_side_effect
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act
        await use_case.execute(sample_users_data, tenant_id=tenant_id)

        # Assert
        assert len(created_users) == 3
        for user in created_users:
            assert user.tenant_id == tenant_id

    async def test_execute_handles_integrity_error_for_email(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute handles IntegrityError for duplicate email."""
        # Arrange
        error = IntegrityError("", "", Exception("duplicate key value on email"))
        error.orig = Exception("duplicate key value on email")
        mock_uow.users.create.side_effect = error
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="One or more emails already exist"):
            await use_case.execute(sample_users_data)

    async def test_execute_handles_integrity_error_for_username(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute handles IntegrityError for duplicate username."""
        # Arrange
        error = IntegrityError("", "", Exception("duplicate key value on username"))
        error.orig = Exception("duplicate key value on username")
        mock_uow.users.create.side_effect = error
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(ValidationError, match="One or more usernames already exist"):
            await use_case.execute(sample_users_data)

    async def test_execute_uses_unit_of_work_context_manager(
        self, mock_uow_factory, mock_uow, sample_users_data
    ):
        """Test that execute properly uses UnitOfWork context manager."""
        # Arrange
        created_users = [
            User(
                id=uuid7(),
                email=data["email"],
                username=data["username"],
                full_name=data.get("full_name"),
                is_active=True,
            )
            for data in sample_users_data
        ]
        mock_uow.users.create.side_effect = created_users
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act
        await use_case.execute(sample_users_data)

        # Assert: UnitOfWork context manager was used
        mock_uow_factory.assert_called_once()
        mock_uow.__aenter__.assert_called_once()
        mock_uow.__aexit__.assert_called_once()

    async def test_execute_transaction_rolls_back_on_error(self, mock_uow_factory, mock_uow):
        """Test that transaction is rolled back when error occurs."""
        # Arrange
        users_data = [
            {"email": "user1@example.com", "username": "user1"},
            {"email": "user2@example.com", "username": "user2"},
        ]

        # First create succeeds, second fails
        user1 = User(id=uuid7(), email="user1@example.com", username="user1", is_active=True)
        mock_uow.users.create.side_effect = [user1, RuntimeError("Database error")]
        use_case = BatchCreateUsersUseCase(mock_uow_factory)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database error"):
            await use_case.execute(users_data)

        # Assert: Context manager still called (rollback happens in __aexit__)
        mock_uow.__aenter__.assert_called_once()
        mock_uow.__aexit__.assert_called_once()
        # Verify exception was passed to __aexit__
        exit_call_args = mock_uow.__aexit__.call_args
        assert exit_call_args[0][0] is not None  # exc_type should not be None
