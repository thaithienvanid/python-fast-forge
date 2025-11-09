"""Tests for User schemas.

Test Organization:
- TestUserCreateValidation: UserCreate field validation
- TestUserCreateUsernamePatterns: Username pattern validation
- TestUserCreateEmailValidation: Email validation
- TestUserCreateFullNameValidation: Full name sanitization
- TestUserUpdateValidation: UserUpdate partial updates
- TestUserResponseValidation: UserResponse schema
- TestUserListResponseValidation: UserListResponse schema
- TestBatchUserCreateValidation: BatchUserCreate schema
- TestBatchUserCreateResponseValidation: BatchUserCreateResponse schema
- TestSchemaPropertyBased: Property-based tests
"""

from datetime import datetime
from uuid import UUID

import pytest
from hypothesis import given
from pydantic import ValidationError
from uuid_extension import uuid7

from src.presentation.schemas.user import (
    BatchUserCreate,
    BatchUserCreateResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from tests.strategies import (
    email_strategy,
    full_name_with_control_chars_strategy,
    invalid_email_strategy,
    invalid_username_strategy,
    username_strategy,
)


# ============================================================================
# UserCreate Validation Tests
# ============================================================================


class TestUserCreateValidation:
    """Test UserCreate schema field validation."""

    def test_creates_user_with_all_required_fields(self) -> None:
        """Test UserCreate accepts all required fields.

        Arrange: Valid user data with required fields
        Act: Create UserCreate instance
        Assert: All fields are set correctly
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.full_name == "Test User"

    def test_creates_user_without_optional_full_name(self) -> None:
        """Test UserCreate accepts None for optional full_name.

        Arrange: User data without full_name
        Act: Create UserCreate instance
        Assert: full_name is None
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.full_name is None

    def test_rejects_missing_email(self) -> None:
        """Test UserCreate rejects missing email field.

        Arrange: User data without email
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "username": "testuser",
            "full_name": "Test User",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**data)

        assert "email" in str(exc_info.value)

    def test_rejects_missing_username(self) -> None:
        """Test UserCreate rejects missing username field.

        Arrange: User data without username
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "full_name": "Test User",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**data)

        assert "username" in str(exc_info.value)

    def test_rejects_empty_email(self) -> None:
        """Test UserCreate rejects empty email string.

        Arrange: User data with empty email
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "",
            "username": "testuser",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    def test_rejects_empty_username(self) -> None:
        """Test UserCreate rejects empty username string.

        Arrange: User data with empty username
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)


# ============================================================================
# Username Pattern Tests
# ============================================================================


class TestUserCreateUsernamePatterns:
    """Test UserCreate username pattern validation."""

    def test_accepts_alphanumeric_username(self) -> None:
        """Test UserCreate accepts alphanumeric usernames.

        Arrange: Alphanumeric username
        Act: Create UserCreate
        Assert: Username is accepted
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "user123",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == "user123"

    def test_accepts_username_with_underscores(self) -> None:
        """Test UserCreate accepts usernames with underscores.

        Arrange: Username with underscores
        Act: Create UserCreate
        Assert: Username is accepted
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "user_name",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == "user_name"

    def test_accepts_username_with_hyphens(self) -> None:
        """Test UserCreate accepts usernames with hyphens.

        Arrange: Username with hyphens
        Act: Create UserCreate
        Assert: Username is accepted
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "user-name",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == "user-name"

    def test_accepts_mixed_case_username(self) -> None:
        """Test UserCreate accepts mixed case usernames.

        Arrange: Mixed case username
        Act: Create UserCreate
        Assert: Username preserves case
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "UserName123",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == "UserName123"

    def test_rejects_username_too_short(self) -> None:
        """Test UserCreate rejects username shorter than 3 characters.

        Arrange: 2-character username
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "ab",
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**data)

        assert "username" in str(exc_info.value)

    def test_rejects_username_with_spaces(self) -> None:
        """Test UserCreate rejects username with spaces.

        Arrange: Username with space
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "user name",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    def test_rejects_username_with_special_chars(self) -> None:
        """Test UserCreate rejects username with special characters.

        Arrange: Username with @!
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "user@name!",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    def test_accepts_username_at_min_length(self) -> None:
        """Test UserCreate accepts username at minimum length (3 chars).

        Arrange: 3-character username
        Act: Create UserCreate
        Assert: Username is accepted
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "abc",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == "abc"

    def test_accepts_username_at_max_length(self) -> None:
        """Test UserCreate accepts username at maximum length (100 chars).

        Arrange: 100-character username
        Act: Create UserCreate
        Assert: Username is accepted
        """
        # Arrange
        username = "a" * 100
        data = {
            "email": "test@example.com",
            "username": username,
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == username
        assert len(user.username) == 100

    def test_rejects_username_exceeding_max_length(self) -> None:
        """Test UserCreate rejects username longer than 100 characters.

        Arrange: 101-character username
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        username = "a" * 101
        data = {
            "email": "test@example.com",
            "username": username,
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)


# ============================================================================
# Email Validation Tests
# ============================================================================


class TestUserCreateEmailValidation:
    """Test UserCreate email validation."""

    def test_accepts_valid_simple_email(self) -> None:
        """Test UserCreate accepts simple valid email.

        Arrange: Simple email address
        Act: Create UserCreate
        Assert: Email is accepted
        """
        # Arrange
        data = {
            "email": "user@example.com",
            "username": "testuser",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.email == "user@example.com"

    def test_accepts_email_with_subdomain(self) -> None:
        """Test UserCreate accepts email with subdomain.

        Arrange: Email with subdomain
        Act: Create UserCreate
        Assert: Email is accepted
        """
        # Arrange
        data = {
            "email": "user@mail.example.com",
            "username": "testuser",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.email == "user@mail.example.com"

    def test_accepts_email_with_plus_addressing(self) -> None:
        """Test UserCreate accepts email with plus addressing.

        Arrange: Email with + character
        Act: Create UserCreate
        Assert: Email is accepted
        """
        # Arrange
        data = {
            "email": "user+tag@example.com",
            "username": "testuser",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.email == "user+tag@example.com"

    def test_rejects_email_without_at_symbol(self) -> None:
        """Test UserCreate rejects email without @ symbol.

        Arrange: Email without @
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "invalid-email",
            "username": "testuser",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    def test_rejects_email_without_domain(self) -> None:
        """Test UserCreate rejects email without domain.

        Arrange: Email missing domain
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "user@",
            "username": "testuser",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    def test_rejects_email_without_local_part(self) -> None:
        """Test UserCreate rejects email without local part.

        Arrange: Email missing local part
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "@example.com",
            "username": "testuser",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    def test_rejects_email_with_spaces(self) -> None:
        """Test UserCreate rejects email with spaces.

        Arrange: Email with space
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "user name@example.com",
            "username": "testuser",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)


# ============================================================================
# Full Name Validation Tests
# ============================================================================


class TestUserCreateFullNameValidation:
    """Test UserCreate full_name validation and sanitization."""

    def test_accepts_simple_full_name(self) -> None:
        """Test UserCreate accepts simple full name.

        Arrange: Simple full name
        Act: Create UserCreate
        Assert: Full name is accepted
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "John Doe",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.full_name == "John Doe"

    def test_strips_control_characters_from_full_name(self) -> None:
        """Test UserCreate strips control characters from full_name.

        Arrange: Full name with control characters (ASCII < 32)
        Act: Create UserCreate
        Assert: Control characters are removed
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "John\x00\x01Doe\x1f",  # Null, SOH, Unit Separator
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.full_name == "JohnDoe"
        assert "\x00" not in user.full_name
        assert "\x01" not in user.full_name
        assert "\x1f" not in user.full_name

    def test_strips_tabs_from_full_name(self) -> None:
        """Test UserCreate strips tab characters from full_name.

        Arrange: Full name with tabs
        Act: Create UserCreate
        Assert: Tabs are removed
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "John\tDoe",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.full_name == "JohnDoe"
        assert "\t" not in user.full_name

    def test_strips_newlines_from_full_name(self) -> None:
        """Test UserCreate strips newline characters from full_name.

        Arrange: Full name with newlines
        Act: Create UserCreate
        Assert: Newlines are removed
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "John\nDoe\r\n",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.full_name == "JohnDoe"
        assert "\n" not in user.full_name
        assert "\r" not in user.full_name

    def test_preserves_regular_spaces_in_full_name(self) -> None:
        """Test UserCreate preserves regular spaces in full_name.

        Arrange: Full name with regular spaces (ASCII 32)
        Act: Create UserCreate
        Assert: Spaces are preserved
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "John Middle Doe",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.full_name == "John Middle Doe"
        assert " " in user.full_name

    def test_accepts_unicode_characters_in_full_name(self) -> None:
        """Test UserCreate accepts Unicode characters in full_name.

        Arrange: Full name with Unicode characters
        Act: Create UserCreate
        Assert: Unicode is preserved
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "José García 李明",
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.full_name == "José García 李明"

    def test_rejects_full_name_exceeding_max_length(self) -> None:
        """Test UserCreate rejects full_name longer than 255 characters.

        Arrange: 256-character full name
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        full_name = "a" * 256
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": full_name,
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)


# ============================================================================
# UserUpdate Validation Tests
# ============================================================================


class TestUserUpdateValidation:
    """Test UserUpdate schema partial updates."""

    def test_creates_update_with_no_fields(self) -> None:
        """Test UserUpdate accepts empty update (all None).

        Arrange: Empty update data
        Act: Create UserUpdate
        Assert: All fields are None
        """
        # Arrange
        data = {}

        # Act
        update = UserUpdate(**data)

        # Assert
        assert update.email is None
        assert update.username is None
        assert update.full_name is None
        assert update.is_active is None

    def test_creates_update_with_only_email(self) -> None:
        """Test UserUpdate accepts partial update with only email.

        Arrange: Update with only email
        Act: Create UserUpdate
        Assert: Email is set, others None
        """
        # Arrange
        data = {
            "email": "newemail@example.com",
        }

        # Act
        update = UserUpdate(**data)

        # Assert
        assert update.email == "newemail@example.com"
        assert update.username is None
        assert update.full_name is None
        assert update.is_active is None

    def test_creates_update_with_only_username(self) -> None:
        """Test UserUpdate accepts partial update with only username.

        Arrange: Update with only username
        Act: Create UserUpdate
        Assert: Username is set, others None
        """
        # Arrange
        data = {
            "username": "newusername",
        }

        # Act
        update = UserUpdate(**data)

        # Assert
        assert update.username == "newusername"
        assert update.email is None
        assert update.full_name is None
        assert update.is_active is None

    def test_creates_update_with_only_is_active(self) -> None:
        """Test UserUpdate accepts partial update with only is_active.

        Arrange: Update with only is_active
        Act: Create UserUpdate
        Assert: is_active is set, others None
        """
        # Arrange
        data = {
            "is_active": False,
        }

        # Act
        update = UserUpdate(**data)

        # Assert
        assert update.is_active is False
        assert update.email is None
        assert update.username is None
        assert update.full_name is None

    def test_creates_update_with_all_fields(self) -> None:
        """Test UserUpdate accepts update with all fields.

        Arrange: Update with all fields
        Act: Create UserUpdate
        Assert: All fields are set
        """
        # Arrange
        data = {
            "email": "newemail@example.com",
            "username": "newusername",
            "full_name": "New Name",
            "is_active": False,
        }

        # Act
        update = UserUpdate(**data)

        # Assert
        assert update.email == "newemail@example.com"
        assert update.username == "newusername"
        assert update.full_name == "New Name"
        assert update.is_active is False

    def test_rejects_invalid_email_in_update(self) -> None:
        """Test UserUpdate rejects invalid email.

        Arrange: Update with invalid email
        Act: Attempt to create UserUpdate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "invalid-email",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserUpdate(**data)

    def test_rejects_invalid_username_in_update(self) -> None:
        """Test UserUpdate rejects invalid username.

        Arrange: Update with invalid username (too short)
        Act: Attempt to create UserUpdate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "username": "ab",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserUpdate(**data)


# ============================================================================
# UserResponse Validation Tests
# ============================================================================


class TestUserResponseValidation:
    """Test UserResponse schema validation."""

    def test_creates_response_with_all_fields(self) -> None:
        """Test UserResponse accepts all required fields.

        Arrange: Complete user response data
        Act: Create UserResponse
        Assert: All fields are set correctly
        """
        # Arrange
        test_uuid = uuid7()
        now = datetime.now()
        data = {
            "id": test_uuid,
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        # Act
        user = UserResponse(**data)

        # Assert
        assert user.id == test_uuid
        assert isinstance(user.id, UUID)
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.created_at == now
        assert user.updated_at == now

    def test_accepts_uuid_as_string(self) -> None:
        """Test UserResponse converts UUID string to UUID.

        Arrange: User data with UUID as string
        Act: Create UserResponse
        Assert: UUID is converted to UUID type
        """
        # Arrange
        uuid_string = "550e8400-e29b-41d4-a716-446655440000"
        data = {
            "id": uuid_string,
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Act
        user = UserResponse(**data)

        # Assert
        assert str(user.id) == uuid_string
        assert isinstance(user.id, UUID)

    def test_rejects_invalid_uuid_string(self) -> None:
        """Test UserResponse rejects invalid UUID string.

        Arrange: User data with invalid UUID
        Act: Attempt to create UserResponse
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "id": "not-a-valid-uuid",
            "email": "test@example.com",
            "username": "testuser",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserResponse(**data)

    def test_rejects_missing_required_id(self) -> None:
        """Test UserResponse rejects missing id field.

        Arrange: User data without id
        Act: Attempt to create UserResponse
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserResponse(**data)

        assert "id" in str(exc_info.value)

    def test_rejects_missing_timestamps(self) -> None:
        """Test UserResponse rejects missing timestamp fields.

        Arrange: User data without timestamps
        Act: Attempt to create UserResponse
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "id": uuid7(),
            "email": "test@example.com",
            "username": "testuser",
            "is_active": True,
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserResponse(**data)

        error_str = str(exc_info.value)
        assert "created_at" in error_str or "updated_at" in error_str


# ============================================================================
# UserListResponse Validation Tests
# ============================================================================


class TestUserListResponseValidation:
    """Test UserListResponse schema validation."""

    def test_creates_list_response_with_items(self) -> None:
        """Test UserListResponse accepts list of users.

        Arrange: List response data with users
        Act: Create UserListResponse
        Assert: All fields are set correctly
        """
        # Arrange
        now = datetime.now()
        user_data = {
            "id": uuid7(),
            "email": "user@example.com",
            "username": "user1",
            "full_name": "User One",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        data = {
            "items": [user_data],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }

        # Act
        response = UserListResponse(**data)

        # Assert
        assert len(response.items) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.page_size == 20
        assert isinstance(response.items[0], UserResponse)

    def test_creates_empty_list_response(self) -> None:
        """Test UserListResponse accepts empty list.

        Arrange: List response with no items
        Act: Create UserListResponse
        Assert: Empty list is accepted
        """
        # Arrange
        data = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }

        # Act
        response = UserListResponse(**data)

        # Assert
        assert len(response.items) == 0
        assert response.total == 0

    def test_creates_list_response_with_multiple_users(self) -> None:
        """Test UserListResponse accepts multiple users.

        Arrange: List response with 3 users
        Act: Create UserListResponse
        Assert: All users are included
        """
        # Arrange
        now = datetime.now()
        users = [
            {
                "id": uuid7(),
                "email": f"user{i}@example.com",
                "username": f"user{i}",
                "full_name": f"User {i}",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for i in range(1, 4)
        ]
        data = {
            "items": users,
            "total": 3,
            "page": 1,
            "page_size": 20,
        }

        # Act
        response = UserListResponse(**data)

        # Assert
        assert len(response.items) == 3
        assert response.total == 3
        assert all(isinstance(user, UserResponse) for user in response.items)


# ============================================================================
# BatchUserCreate Validation Tests
# ============================================================================


class TestBatchUserCreateValidation:
    """Test BatchUserCreate schema validation."""

    def test_creates_batch_with_single_user(self) -> None:
        """Test BatchUserCreate accepts single user.

        Arrange: Batch with 1 user
        Act: Create BatchUserCreate
        Assert: Batch is created
        """
        # Arrange
        data = {
            "users": [
                {
                    "email": "user1@example.com",
                    "username": "user1",
                    "full_name": "User One",
                }
            ]
        }

        # Act
        batch = BatchUserCreate(**data)

        # Assert
        assert len(batch.users) == 1
        assert batch.users[0].email == "user1@example.com"

    def test_creates_batch_with_multiple_users(self) -> None:
        """Test BatchUserCreate accepts multiple users.

        Arrange: Batch with 3 users
        Act: Create BatchUserCreate
        Assert: All users are included
        """
        # Arrange
        data = {
            "users": [
                {
                    "email": f"user{i}@example.com",
                    "username": f"user{i}",
                    "full_name": f"User {i}",
                }
                for i in range(1, 4)
            ]
        }

        # Act
        batch = BatchUserCreate(**data)

        # Assert
        assert len(batch.users) == 3
        assert all(isinstance(user, UserCreate) for user in batch.users)

    def test_creates_batch_at_max_length(self) -> None:
        """Test BatchUserCreate accepts 100 users (max length).

        Arrange: Batch with 100 users
        Act: Create BatchUserCreate
        Assert: All 100 users are included
        """
        # Arrange
        data = {
            "users": [
                {
                    "email": f"user{i}@example.com",
                    "username": f"user{i}",
                }
                for i in range(1, 101)
            ]
        }

        # Act
        batch = BatchUserCreate(**data)

        # Assert
        assert len(batch.users) == 100

    def test_rejects_empty_batch(self) -> None:
        """Test BatchUserCreate rejects empty user list.

        Arrange: Batch with no users
        Act: Attempt to create BatchUserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {"users": []}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            BatchUserCreate(**data)

        assert "users" in str(exc_info.value)

    def test_rejects_batch_exceeding_max_length(self) -> None:
        """Test BatchUserCreate rejects more than 100 users.

        Arrange: Batch with 101 users
        Act: Attempt to create BatchUserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "users": [
                {
                    "email": f"user{i}@example.com",
                    "username": f"user{i}",
                }
                for i in range(1, 102)
            ]
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            BatchUserCreate(**data)


# ============================================================================
# BatchUserCreateResponse Validation Tests
# ============================================================================


class TestBatchUserCreateResponseValidation:
    """Test BatchUserCreateResponse schema validation."""

    def test_creates_batch_response_with_created_users(self) -> None:
        """Test BatchUserCreateResponse with created users.

        Arrange: Batch response data with created users
        Act: Create BatchUserCreateResponse
        Assert: All fields are set correctly
        """
        # Arrange
        now = datetime.now()
        created_users = [
            {
                "id": uuid7(),
                "email": f"user{i}@example.com",
                "username": f"user{i}",
                "full_name": f"User {i}",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for i in range(1, 3)
        ]
        data = {
            "created": created_users,
            "total": 2,
            "message": "Successfully created 2 user(s) in a single transaction",
        }

        # Act
        response = BatchUserCreateResponse(**data)

        # Assert
        assert len(response.created) == 2
        assert response.total == 2
        assert "2 user(s)" in response.message
        assert all(isinstance(user, UserResponse) for user in response.created)

    def test_creates_batch_response_with_empty_list(self) -> None:
        """Test BatchUserCreateResponse with no created users.

        Arrange: Batch response with empty list
        Act: Create BatchUserCreateResponse
        Assert: Empty list is accepted
        """
        # Arrange
        data = {
            "created": [],
            "total": 0,
            "message": "No users created",
        }

        # Act
        response = BatchUserCreateResponse(**data)

        # Assert
        assert len(response.created) == 0
        assert response.total == 0
        assert response.message == "No users created"


# ============================================================================
# Property-Based Tests
# ============================================================================


class TestSchemaPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(username=username_strategy())
    def test_valid_usernames_always_accepted(self, username: str) -> None:
        """Property: All valid usernames from strategy are accepted.

        Arrange: Valid username from strategy
        Act: Create UserCreate with username
        Assert: No validation error
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": username,
        }

        # Act
        user = UserCreate(**data)

        # Assert
        assert user.username == username

    @given(email=email_strategy())
    def test_valid_emails_always_accepted(self, email: str) -> None:
        """Property: All valid emails from strategy are accepted.

        Arrange: Valid email from strategy
        Act: Create UserCreate with email
        Assert: No validation error, email is validated and normalized
        """
        # Arrange
        data = {
            "email": email,
            "username": "testuser",
        }

        # Act
        user = UserCreate(**data)

        # Assert: Email is validated and stored (may be normalized)
        # Pydantic's EmailStr validates and normalizes emails, including IDN domains
        assert "@" in user.email  # Basic email structure preserved
        assert len(user.email) >= 3  # Minimum reasonable email length

    @given(full_name=full_name_with_control_chars_strategy())
    def test_control_chars_always_stripped_from_full_name(self, full_name: str) -> None:
        """Property: Control characters are always stripped from full_name.

        Arrange: Full name with control characters
        Act: Create UserCreate with full_name
        Assert: Result has no control characters
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": full_name,
        }

        # Act
        user = UserCreate(**data)

        # Assert: No control characters in result (all chars have ASCII >= 32)
        if user.full_name:
            assert all(ord(c) >= 32 for c in user.full_name)

    @given(username=invalid_username_strategy())
    def test_invalid_usernames_always_rejected(self, username: str) -> None:
        """Property: All invalid usernames are rejected.

        Arrange: Invalid username from strategy
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": "test@example.com",
            "username": username,
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)

    @given(email=invalid_email_strategy())
    def test_invalid_emails_always_rejected(self, email: str) -> None:
        """Property: All invalid emails are rejected.

        Arrange: Invalid email from strategy
        Act: Attempt to create UserCreate
        Assert: ValidationError raised
        """
        # Arrange
        data = {
            "email": email,
            "username": "testuser",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            UserCreate(**data)
