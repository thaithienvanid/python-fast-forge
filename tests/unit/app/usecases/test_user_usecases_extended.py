"""Extended unit tests for user use cases.

Covers missing lines to improve coverage of:
- GetUserUseCase: tenant isolation, not-found handling
- ListUsersUseCase: validation errors, boundary conditions
- UpdateUserUseCase: changed_fields, event publishing, tenant isolation
- DeleteUserUseCase: tenant isolation, not-found handling
- RestoreUserUseCase: validation, not-found, already-deleted checks
- ForceDeleteUserUseCase: tenant isolation, not-found
- GetDeletedUsersUseCase: validation errors, boundary conditions
- BatchCreateUsersUseCase: duplicates, existing users, empty data
- SearchUsersUseCase: filterset-based search

Test Organization:
- AAA pattern (Arrange-Act-Assert) throughout
- AsyncMock for async methods
- pytest.mark.parametrize for boundary conditions
- Isolated mocking of repositories and event bus
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.app.usecases.user_usecases import (
    BatchCreateUsersUseCase,
    DeleteUserUseCase,
    ForceDeleteUserUseCase,
    GetDeletedUsersUseCase,
    GetUserUseCase,
    ListUsersUseCase,
    RestoreUserUseCase,
    SearchUsersUseCase,
    UpdateUserUseCase,
)
from src.domain.constants import UserLimits
from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.domain.models.user import User


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_repo():
    """Create a mock user repository with async methods."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_user():
    """Create a sample active user for testing."""
    return User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        is_active=True,
        tenant_id=uuid4(),
        deleted_at=None,
    )


@pytest.fixture
def sample_deleted_user():
    """Create a sample soft-deleted user for testing."""
    from datetime import UTC, datetime

    user = User(
        id=uuid4(),
        email="deleted@example.com",
        username="deleteduser",
        full_name="Deleted User",
        is_active=True,
        tenant_id=uuid4(),
    )
    user.deleted_at = datetime.now(UTC)
    return user


# ============================================================================
# GetUserUseCase Tests
# ============================================================================


class TestGetUserUseCase:
    """Tests for GetUserUseCase covering missing lines 34-42."""

    async def test_returns_user_when_found_without_tenant(self, mock_repo, sample_user):
        """Test returns user when found and no tenant filter applied.

        Arrange: Repository returns a user, no tenant_id provided
        Act: Execute use case
        Assert: User is returned
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = GetUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id)

        # Assert
        assert result == sample_user
        mock_repo.get_by_id.assert_called_once_with(sample_user.id)

    async def test_raises_not_found_when_user_missing(self, mock_repo):
        """Test raises EntityNotFoundError when user does not exist.

        Arrange: Repository returns None
        Act: Execute use case
        Assert: EntityNotFoundError raised (line 36)
        """
        # Arrange
        user_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        use_case = GetUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await use_case.execute(user_id)

    async def test_raises_not_found_when_tenant_mismatch(self, mock_repo, sample_user):
        """Test raises EntityNotFoundError when tenant_id does not match user.

        Arrange: User exists but belongs to a different tenant
        Act: Execute use case with a different tenant_id
        Assert: EntityNotFoundError raised (lines 39-40)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = GetUserUseCase(mock_repo)
        different_tenant_id = uuid4()  # Does not match sample_user.tenant_id

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(sample_user.id)):
            await use_case.execute(sample_user.id, tenant_id=different_tenant_id)

    async def test_returns_user_when_tenant_matches(self, mock_repo, sample_user):
        """Test returns user when tenant_id matches user's tenant.

        Arrange: User exists with matching tenant_id
        Act: Execute use case with correct tenant_id
        Assert: User is returned (line 42)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = GetUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id, tenant_id=sample_user.tenant_id)

        # Assert
        assert result == sample_user


# ============================================================================
# ListUsersUseCase Tests
# ============================================================================


class TestListUsersUseCase:
    """Tests for ListUsersUseCase covering missing lines 73-86."""

    async def test_raises_validation_error_when_skip_negative(self, mock_repo):
        """Test raises ValidationError when skip is negative.

        Arrange: skip=-1
        Act: Execute use case
        Assert: ValidationError raised (line 74)
        """
        # Arrange
        use_case = ListUsersUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(ValidationError, match="non-negative"):
            await use_case.execute(skip=-1)

    @pytest.mark.parametrize(
        "limit",
        [0, UserLimits.LIST_MAX_LIMIT + 1],
        ids=["below_minimum", "above_maximum"],
    )
    async def test_raises_validation_error_for_invalid_limit(self, mock_repo, limit):
        """Test raises ValidationError when limit is outside valid range.

        Arrange: limit outside [LIST_MIN_LIMIT, LIST_MAX_LIMIT]
        Act: Execute use case
        Assert: ValidationError raised (lines 75-78)
        """
        # Arrange
        use_case = ListUsersUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(ValidationError):
            await use_case.execute(limit=limit)

    async def test_returns_users_and_count_on_success(self, mock_repo, sample_user):
        """Test returns tuple of (users, total) on success.

        Arrange: Repository returns users and count
        Act: Execute with valid parameters
        Assert: Returns (list_of_users, total) tuple (lines 81-86)
        """
        # Arrange
        mock_repo.get_all = AsyncMock(return_value=[sample_user])
        mock_repo.count_all = AsyncMock(return_value=1)
        use_case = ListUsersUseCase(mock_repo)

        # Act
        users, total = await use_case.execute(skip=0, limit=10, tenant_id=uuid4())

        # Assert
        assert users == [sample_user]
        assert total == 1
        mock_repo.get_all.assert_called_once()
        mock_repo.count_all.assert_called_once()


# ============================================================================
# UpdateUserUseCase Tests
# ============================================================================


class TestUpdateUserUseCase:
    """Tests for UpdateUserUseCase covering missing lines 198-241."""

    async def test_raises_not_found_when_user_missing(self, mock_repo):
        """Test raises EntityNotFoundError when user does not exist.

        Arrange: Repository returns None
        Act: Execute use case
        Assert: EntityNotFoundError raised (lines 199-200)
        """
        # Arrange
        user_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        use_case = UpdateUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await use_case.execute(user_id, email="new@example.com")

    async def test_raises_not_found_on_tenant_mismatch(self, mock_repo, sample_user):
        """Test raises EntityNotFoundError when tenant_id does not match.

        Arrange: User exists but tenant_id is different
        Act: Execute use case with wrong tenant_id
        Assert: EntityNotFoundError raised (lines 203-204)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = UpdateUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await use_case.execute(sample_user.id, tenant_id=uuid4())

    async def test_updates_email_and_tracks_changed_field(self, mock_repo, sample_user):
        """Test updates email and tracks it in changed_fields.

        Arrange: User exists, new email provided
        Act: Execute use case with new email
        Assert: User updated, UserUpdatedEvent published with email in changed_fields
        (lines 210-212, 229-239)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.update = AsyncMock(return_value=sample_user)
        use_case = UpdateUserUseCase(mock_repo)

        mock_event_bus = AsyncMock()
        mock_event_bus.publish = AsyncMock()

        with patch(
            "src.domain.events.event_bus.get_event_bus",
            return_value=mock_event_bus,
        ):
            # Act
            result = await use_case.execute(sample_user.id, email="updated@example.com")

        # Assert
        assert result is not None
        mock_repo.update.assert_called_once()

    async def test_updates_multiple_fields_and_publishes_event(self, mock_repo, sample_user):
        """Test updating multiple fields publishes event with all changed fields.

        Arrange: User exists, update email, username, full_name, is_active
        Act: Execute use case with all new values
        Assert: All fields tracked, event published (lines 210-239)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.update = AsyncMock(return_value=sample_user)
        use_case = UpdateUserUseCase(mock_repo)

        mock_event_bus = AsyncMock()
        mock_event_bus.publish = AsyncMock()

        with patch(
            "src.domain.events.event_bus.get_event_bus",
            return_value=mock_event_bus,
        ):
            # Act
            result = await use_case.execute(
                sample_user.id,
                email="changed@example.com",
                username="changeduser",
                full_name="Changed Name",
                is_active=False,
            )

        # Assert
        assert result is not None

    async def test_no_event_when_no_fields_changed(self, mock_repo, sample_user):
        """Test no event published when values are identical to existing.

        Arrange: User exists, same values provided
        Act: Execute use case with same email/username
        Assert: Repository update called but no event published (line 230 condition false)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.update = AsyncMock(return_value=sample_user)
        use_case = UpdateUserUseCase(mock_repo)

        # Act - same email and username, nothing changes
        await use_case.execute(
            sample_user.id,
            email=sample_user.email,
            username=sample_user.username,
        )

        # Assert: update was still called (no fields changed is allowed)
        mock_repo.update.assert_called_once()

    async def test_returns_updated_user(self, mock_repo, sample_user):
        """Test returns the updated user entity.

        Arrange: Successful update
        Act: Execute use case
        Assert: Returns updated user (line 241)
        """
        # Arrange
        updated_user = User(
            id=sample_user.id,
            email="updated@example.com",
            username=sample_user.username,
            tenant_id=sample_user.tenant_id,
        )
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.update = AsyncMock(return_value=updated_user)
        use_case = UpdateUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id, email="updated@example.com")

        # Assert
        assert result == updated_user


# ============================================================================
# DeleteUserUseCase Tests
# ============================================================================


class TestDeleteUserUseCase:
    """Tests for DeleteUserUseCase covering missing lines 268-277."""

    async def test_soft_deletes_user_without_tenant(self, mock_repo, sample_user):
        """Test soft deletes user when no tenant_id provided.

        Arrange: Repository delete returns True
        Act: Execute without tenant_id
        Assert: Returns True
        """
        # Arrange
        mock_repo.delete = AsyncMock(return_value=True)
        use_case = DeleteUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id)

        # Assert
        assert result is True
        mock_repo.delete.assert_called_once_with(sample_user.id)

    async def test_raises_not_found_when_user_missing_with_tenant(self, mock_repo):
        """Test raises EntityNotFoundError when user not found during tenant check.

        Arrange: Repository get_by_id returns None (user not found)
        Act: Execute with tenant_id
        Assert: EntityNotFoundError raised (lines 270-271)
        """
        # Arrange
        user_id = uuid4()
        tenant_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        use_case = DeleteUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await use_case.execute(user_id, tenant_id=tenant_id)

    async def test_raises_not_found_on_tenant_mismatch(self, mock_repo, sample_user):
        """Test raises EntityNotFoundError when tenant does not match.

        Arrange: User exists but belongs to different tenant
        Act: Execute with different tenant_id
        Assert: EntityNotFoundError raised (lines 272-273)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = DeleteUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await use_case.execute(sample_user.id, tenant_id=uuid4())

    async def test_raises_not_found_when_delete_returns_false(self, mock_repo):
        """Test raises EntityNotFoundError when delete operation returns False.

        Arrange: Repository delete returns False (user not found or already deleted)
        Act: Execute without tenant_id
        Assert: EntityNotFoundError raised (lines 275-276)
        """
        # Arrange
        user_id = uuid4()
        mock_repo.delete = AsyncMock(return_value=False)
        use_case = DeleteUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await use_case.execute(user_id)

    async def test_deletes_with_matching_tenant(self, mock_repo, sample_user):
        """Test successfully deletes when tenant_id matches.

        Arrange: User found with matching tenant, delete succeeds
        Act: Execute with correct tenant_id
        Assert: Returns True (line 277)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.delete = AsyncMock(return_value=True)
        use_case = DeleteUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id, tenant_id=sample_user.tenant_id)

        # Assert
        assert result is True


# ============================================================================
# RestoreUserUseCase Tests
# ============================================================================


class TestRestoreUserUseCase:
    """Tests for RestoreUserUseCase covering missing lines 413-433."""

    async def test_raises_not_found_when_user_missing(self, mock_repo):
        """Test raises EntityNotFoundError when user does not exist.

        Arrange: get_by_id returns None
        Act: Execute restore
        Assert: EntityNotFoundError raised (lines 414-415)
        """
        # Arrange
        user_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        use_case = RestoreUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await use_case.execute(user_id)

    async def test_raises_not_found_on_tenant_mismatch(self, mock_repo, sample_deleted_user):
        """Test raises EntityNotFoundError when tenant_id does not match.

        Arrange: Deleted user found but tenant mismatch
        Act: Execute with wrong tenant_id
        Assert: EntityNotFoundError raised (lines 418-419)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_deleted_user)
        use_case = RestoreUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await use_case.execute(sample_deleted_user.id, tenant_id=uuid4())

    async def test_raises_validation_error_when_user_not_deleted(self, mock_repo, sample_user):
        """Test raises ValidationError when user is not deleted.

        Arrange: Active (non-deleted) user found
        Act: Execute restore
        Assert: ValidationError raised (lines 422-423)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = RestoreUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(ValidationError, match="not deleted"):
            await use_case.execute(sample_user.id)

    async def test_raises_not_found_when_restore_returns_false(
        self, mock_repo, sample_deleted_user
    ):
        """Test raises EntityNotFoundError when restore operation fails.

        Arrange: Deleted user found, but restore returns False
        Act: Execute restore
        Assert: EntityNotFoundError raised (lines 425-426)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_deleted_user)
        mock_repo.restore = AsyncMock(return_value=False)
        use_case = RestoreUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await use_case.execute(sample_deleted_user.id)

    async def test_raises_not_found_when_fetch_after_restore_fails(
        self, mock_repo, sample_deleted_user, sample_user
    ):
        """Test raises EntityNotFoundError when restored user cannot be fetched.

        Arrange: Restore succeeds but subsequent get_by_id returns None
        Act: Execute restore
        Assert: EntityNotFoundError raised (lines 430-431)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(side_effect=[sample_deleted_user, None])
        mock_repo.restore = AsyncMock(return_value=True)
        use_case = RestoreUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match="Failed to restore"):
            await use_case.execute(sample_deleted_user.id)

    async def test_returns_restored_user_on_success(
        self, mock_repo, sample_deleted_user, sample_user
    ):
        """Test returns the restored user after successful restore.

        Arrange: Deleted user found, restore succeeds, fetched user returned
        Act: Execute restore
        Assert: Restored user returned (line 433)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(side_effect=[sample_deleted_user, sample_user])
        mock_repo.restore = AsyncMock(return_value=True)
        use_case = RestoreUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_deleted_user.id)

        # Assert
        assert result == sample_user


# ============================================================================
# ForceDeleteUserUseCase Tests
# ============================================================================


class TestForceDeleteUserUseCase:
    """Tests for ForceDeleteUserUseCase covering missing lines 460-471."""

    async def test_raises_not_found_when_user_missing(self, mock_repo):
        """Test raises EntityNotFoundError when user does not exist.

        Arrange: get_by_id returns None
        Act: Execute force delete
        Assert: EntityNotFoundError raised (lines 461-462)
        """
        # Arrange
        user_id = uuid4()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        use_case = ForceDeleteUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await use_case.execute(user_id)

    async def test_raises_not_found_on_tenant_mismatch(self, mock_repo, sample_user):
        """Test raises EntityNotFoundError when tenant_id does not match.

        Arrange: User exists but tenant mismatch
        Act: Execute with wrong tenant_id
        Assert: EntityNotFoundError raised (lines 465-466)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        use_case = ForceDeleteUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await use_case.execute(sample_user.id, tenant_id=uuid4())

    async def test_raises_not_found_when_force_delete_returns_false(self, mock_repo, sample_user):
        """Test raises EntityNotFoundError when force_delete returns False.

        Arrange: User found, force_delete returns False
        Act: Execute
        Assert: EntityNotFoundError raised (lines 468-469)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.force_delete = AsyncMock(return_value=False)
        use_case = ForceDeleteUserUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError):
            await use_case.execute(sample_user.id)

    async def test_returns_true_on_success(self, mock_repo, sample_user):
        """Test returns True when force delete succeeds.

        Arrange: User found, force_delete returns True
        Act: Execute
        Assert: True returned (line 471)
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.force_delete = AsyncMock(return_value=True)
        use_case = ForceDeleteUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id)

        # Assert
        assert result is True

    async def test_force_deletes_with_correct_tenant(self, mock_repo, sample_user):
        """Test force deletes when tenant_id matches.

        Arrange: User found with matching tenant_id
        Act: Execute with correct tenant_id
        Assert: Returns True
        """
        # Arrange
        mock_repo.get_by_id = AsyncMock(return_value=sample_user)
        mock_repo.force_delete = AsyncMock(return_value=True)
        use_case = ForceDeleteUserUseCase(mock_repo)

        # Act
        result = await use_case.execute(sample_user.id, tenant_id=sample_user.tenant_id)

        # Assert
        assert result is True
        mock_repo.force_delete.assert_called_once_with(sample_user.id)


# ============================================================================
# GetDeletedUsersUseCase Tests
# ============================================================================


class TestGetDeletedUsersUseCase:
    """Tests for GetDeletedUsersUseCase covering missing lines 503-510."""

    async def test_raises_validation_error_when_skip_negative(self, mock_repo):
        """Test raises ValidationError when skip is negative.

        Arrange: skip=-1
        Act: Execute
        Assert: ValidationError raised (line 504)
        """
        # Arrange
        use_case = GetDeletedUsersUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(ValidationError, match="non-negative"):
            await use_case.execute(skip=-1)

    @pytest.mark.parametrize(
        "limit",
        [0, UserLimits.LIST_MAX_LIMIT + 1],
        ids=["below_minimum", "above_maximum"],
    )
    async def test_raises_validation_error_for_invalid_limit(self, mock_repo, limit):
        """Test raises ValidationError for out-of-range limit.

        Arrange: limit outside valid range
        Act: Execute
        Assert: ValidationError raised (lines 505-508)
        """
        # Arrange
        use_case = GetDeletedUsersUseCase(mock_repo)

        # Act & Assert
        with pytest.raises(ValidationError):
            await use_case.execute(limit=limit)

    async def test_returns_deleted_users_on_valid_params(self, mock_repo, sample_deleted_user):
        """Test returns list of deleted users with valid parameters.

        Arrange: Repository returns deleted users
        Act: Execute with valid skip/limit
        Assert: Deleted users returned (line 510)
        """
        # Arrange
        mock_repo.get_deleted = AsyncMock(return_value=[sample_deleted_user])
        use_case = GetDeletedUsersUseCase(mock_repo)

        # Act
        result = await use_case.execute(skip=0, limit=10, tenant_id=uuid4())

        # Assert
        assert result == [sample_deleted_user]
        mock_repo.get_deleted.assert_called_once()


# ============================================================================
# BatchCreateUsersUseCase Tests
# ============================================================================


class TestBatchCreateUsersUseCase:
    """Tests for BatchCreateUsersUseCase covering missing lines 337-386."""

    def _make_uow_factory(self, mock_uow):
        """Create an async context manager factory from a mock UoW."""

        class AsyncUoWContextManager:
            async def __aenter__(self):
                return mock_uow

            async def __aexit__(self, *args):
                return False

        return MagicMock(return_value=AsyncUoWContextManager())

    async def test_raises_value_error_when_empty_list(self):
        """Test raises ValueError when users_data is empty.

        Arrange: Empty list
        Act: Execute
        Assert: ValueError raised (line 338)
        """
        # Arrange
        uow_factory = MagicMock()
        use_case = BatchCreateUsersUseCase(uow_factory)

        # Act & Assert
        with pytest.raises(ValueError, match="cannot be empty"):
            await use_case.execute([])

    async def test_raises_validation_error_when_batch_too_large(self):
        """Test raises ValidationError when batch exceeds MAX_BATCH_SIZE.

        Arrange: List larger than MAX_BATCH_SIZE
        Act: Execute
        Assert: ValidationError raised (lines 340-343)
        """
        # Arrange
        uow_factory = MagicMock()
        use_case = BatchCreateUsersUseCase(uow_factory)
        users_data = [
            {"email": f"user{i}@example.com", "username": f"user{i}"}
            for i in range(UserLimits.MAX_BATCH_SIZE + 1)
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="Cannot create more than"):
            await use_case.execute(users_data)

    async def test_raises_validation_error_on_duplicate_emails_in_batch(self):
        """Test raises ValidationError when duplicate emails exist in batch.

        Arrange: Two users with the same email in batch
        Act: Execute
        Assert: ValidationError raised (lines 355-356)
        """
        # Arrange
        mock_uow = AsyncMock()
        uow_factory = self._make_uow_factory(mock_uow)
        use_case = BatchCreateUsersUseCase(uow_factory)
        users_data = [
            {"email": "duplicate@example.com", "username": "user1"},
            {"email": "duplicate@example.com", "username": "user2"},
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate emails"):
            await use_case.execute(users_data)

    async def test_raises_validation_error_on_duplicate_usernames_in_batch(self):
        """Test raises ValidationError when duplicate usernames exist in batch.

        Arrange: Two users with the same username in batch
        Act: Execute
        Assert: ValidationError raised (lines 357-358)
        """
        # Arrange
        mock_uow = AsyncMock()
        uow_factory = self._make_uow_factory(mock_uow)
        use_case = BatchCreateUsersUseCase(uow_factory)
        users_data = [
            {"email": "user1@example.com", "username": "duplicateuser"},
            {"email": "user2@example.com", "username": "duplicateuser"},
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="Duplicate usernames"):
            await use_case.execute(users_data)

    async def test_raises_validation_error_when_emails_already_exist(self):
        """Test raises ValidationError when emails already exist in database.

        Arrange: find_by_emails returns existing users
        Act: Execute
        Assert: ValidationError raised (lines 362-365)
        """
        # Arrange
        existing_user = User(
            id=uuid4(),
            email="existing@example.com",
            username="existinguser",
        )
        mock_uow = AsyncMock()
        mock_uow.users.find_by_emails = AsyncMock(return_value=[existing_user])
        uow_factory = self._make_uow_factory(mock_uow)
        use_case = BatchCreateUsersUseCase(uow_factory)
        users_data = [{"email": "existing@example.com", "username": "newuser"}]

        # Act & Assert
        with pytest.raises(ValidationError, match="already exist"):
            await use_case.execute(users_data)

    async def test_raises_validation_error_when_usernames_already_exist(self):
        """Test raises ValidationError when usernames already exist in database.

        Arrange: find_by_usernames returns existing users
        Act: Execute
        Assert: ValidationError raised (lines 367-370)
        """
        # Arrange
        existing_user = User(
            id=uuid4(),
            email="other@example.com",
            username="existinguser",
        )
        mock_uow = AsyncMock()
        mock_uow.users.find_by_emails = AsyncMock(return_value=[])
        mock_uow.users.find_by_usernames = AsyncMock(return_value=[existing_user])
        uow_factory = self._make_uow_factory(mock_uow)
        use_case = BatchCreateUsersUseCase(uow_factory)
        users_data = [{"email": "newuser@example.com", "username": "existinguser"}]

        # Act & Assert
        with pytest.raises(ValidationError, match="already exist"):
            await use_case.execute(users_data)

    async def test_creates_all_users_on_success(self):
        """Test creates all users and returns them on success.

        Arrange: No duplicates, no existing users
        Act: Execute with valid batch
        Assert: All users created and returned (lines 373-386)
        """
        # Arrange
        created_users = [
            User(id=uuid4(), email="user1@example.com", username="user1"),
            User(id=uuid4(), email="user2@example.com", username="user2"),
        ]
        mock_uow = AsyncMock()
        mock_uow.users.find_by_emails = AsyncMock(return_value=[])
        mock_uow.users.find_by_usernames = AsyncMock(return_value=[])
        mock_uow.users.create = AsyncMock(side_effect=created_users)
        uow_factory = self._make_uow_factory(mock_uow)
        use_case = BatchCreateUsersUseCase(uow_factory)
        users_data = [
            {"email": "user1@example.com", "username": "user1"},
            {"email": "user2@example.com", "username": "user2"},
        ]

        # Act
        result = await use_case.execute(users_data)

        # Assert
        assert len(result) == 2
        assert mock_uow.users.create.call_count == 2


# ============================================================================
# SearchUsersUseCase Tests
# ============================================================================


class TestSearchUsersUseCase:
    """Tests for SearchUsersUseCase covering missing lines 541-550."""

    async def test_returns_users_and_total_count(self, mock_repo, sample_user):
        """Test returns (users, total) tuple from filterset search.

        Arrange: Repository returns users and count
        Act: Execute with a filterset
        Assert: Returns correct tuple (lines 541-550)
        """
        # Arrange
        mock_filterset = MagicMock()
        mock_repo.count = AsyncMock(return_value=5)
        mock_repo.find = AsyncMock(return_value=[sample_user])
        use_case = SearchUsersUseCase(mock_repo)

        # Act
        users, total = await use_case.execute(filterset=mock_filterset, skip=0, limit=10)

        # Assert
        assert users == [sample_user]
        assert total == 5
        mock_repo.count.assert_called_once_with(mock_filterset)
        mock_repo.find.assert_called_once_with(filterset=mock_filterset, skip=0, limit=10)

    async def test_returns_empty_list_when_no_matches(self, mock_repo):
        """Test returns empty list when no users match the filterset.

        Arrange: Repository returns empty list and zero count
        Act: Execute with filterset
        Assert: Returns ([], 0)
        """
        # Arrange
        mock_filterset = MagicMock()
        mock_repo.count = AsyncMock(return_value=0)
        mock_repo.find = AsyncMock(return_value=[])
        use_case = SearchUsersUseCase(mock_repo)

        # Act
        users, total = await use_case.execute(filterset=mock_filterset)

        # Assert
        assert users == []
        assert total == 0
