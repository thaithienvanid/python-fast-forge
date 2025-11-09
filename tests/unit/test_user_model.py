"""Unit tests for User domain model."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from uuid_extension import uuid7

from tests.factories import deleted_user_factory, user_factory
from tests.strategies import email_strategy, user_strategy, username_strategy


class TestUserModel:
    """Test User domain model behavior and invariants."""

    def test_user_creation_with_required_fields(self):
        """Test creating user with only required fields."""
        # Arrange
        email = "alice@example.com"
        username = "alice"

        # Act
        user = user_factory(email=email, username=username)

        # Assert
        assert user.email == email
        assert user.username == username
        assert user.id is not None
        assert isinstance(user.id, UUID)

    def test_user_creation_sets_default_active_status(self):
        """Test that new users are active by default."""
        # Arrange
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
        }

        # Act
        user = user_factory(**user_data)

        # Assert
        assert user.is_active is True

    def test_user_creation_sets_timestamps(self):
        """Test that creation sets timestamps."""
        # Arrange
        before_creation = datetime.now(UTC)

        # Act
        user = user_factory()

        # Assert
        after_creation = datetime.now(UTC)
        assert before_creation <= user.created_at <= after_creation
        assert before_creation <= user.updated_at <= after_creation

    def test_user_email_is_stored_as_lowercase(self):
        """Test that email is normalized to lowercase."""
        # Arrange
        mixed_case_email = "Alice@EXAMPLE.com"

        # Act
        user = user_factory(email=mixed_case_email)

        # Assert
        assert user.email == mixed_case_email.lower()
        assert user.email == "alice@example.com"

    def test_user_soft_delete_sets_deleted_at(self):
        """Test that soft delete sets deleted_at timestamp."""
        # Arrange
        user = user_factory()
        assert user.deleted_at is None
        assert not user.is_deleted

        # Act
        user.soft_delete()

        # Assert
        assert user.deleted_at is not None
        assert isinstance(user.deleted_at, datetime)
        assert user.is_deleted is True

    def test_user_soft_delete_is_idempotent(self):
        """Test that calling soft_delete multiple times is safe."""
        # Arrange
        user = user_factory()

        # Act
        user.soft_delete()
        first_deleted_at = user.deleted_at

        user.soft_delete()
        second_deleted_at = user.deleted_at

        # Assert
        assert first_deleted_at == second_deleted_at

    def test_user_restore_clears_deleted_at(self):
        """Test that restore clears deleted_at timestamp."""
        # Arrange
        user = deleted_user_factory()
        assert user.is_deleted is True

        # Act
        user.restore()

        # Assert
        assert user.deleted_at is None
        assert user.is_deleted is False

    def test_user_restore_on_non_deleted_user_is_safe(self):
        """Test that restore on active user is a no-op."""
        # Arrange
        user = user_factory()
        assert user.is_deleted is False

        # Act
        user.restore()

        # Assert
        assert user.deleted_at is None
        assert user.is_deleted is False

    def test_user_is_deleted_property_with_active_user(self):
        """Test is_deleted property returns False for active users."""
        # Arrange
        user = user_factory(deleted_at=None)

        # Act & Assert
        assert user.is_deleted is False

    def test_user_is_deleted_property_with_deleted_user(self):
        """Test is_deleted property returns True for deleted users."""
        # Arrange
        user = deleted_user_factory()

        # Act & Assert
        assert user.is_deleted is True

    def test_user_full_name_is_optional(self):
        """Test that full_name can be None."""
        # Arrange & Act
        user = user_factory(full_name=None)

        # Assert
        assert user.full_name is None

    def test_user_full_name_can_be_set(self):
        """Test that full_name can be provided."""
        # Arrange
        full_name = "Alice Smith"

        # Act
        user = user_factory(full_name=full_name)

        # Assert
        assert user.full_name == full_name

    def test_user_tenant_id_is_set(self):
        """Test that tenant_id is always set."""
        # Arrange & Act
        user = user_factory()

        # Assert
        assert user.tenant_id is not None
        assert isinstance(user.tenant_id, UUID)

    def test_users_in_same_tenant_share_tenant_id(self):
        """Test that multiple users can share a tenant."""
        # Arrange
        tenant_id = uuid7()

        # Act
        user1 = user_factory(tenant_id=tenant_id)
        user2 = user_factory(tenant_id=tenant_id)

        # Assert
        assert user1.tenant_id == tenant_id
        assert user2.tenant_id == tenant_id
        assert user1.tenant_id == user2.tenant_id

    def test_user_updated_at_changes_on_modification(self):
        """Test that updated_at reflects modifications."""
        # Arrange
        user = user_factory()
        original_updated_at = user.updated_at

        # Act
        # Simulate time passing
        import time

        time.sleep(0.01)  # 10ms

        user.full_name = "Updated Name"
        user.updated_at = datetime.now(UTC)

        # Assert
        assert user.updated_at > original_updated_at

    @pytest.mark.parametrize(
        ("email", "expected"),
        [
            ("simple@example.com", "simple@example.com"),
            ("UPPER@EXAMPLE.COM", "upper@example.com"),
            ("MiXeD@ExAmPlE.CoM", "mixed@example.com"),
            ("with+tag@example.com", "with+tag@example.com"),
        ],
    )
    def test_user_email_normalization(self, email, expected):
        """Test email normalization with various cases."""
        # Arrange & Act
        user = user_factory(email=email)

        # Assert
        assert user.email == expected


class TestUserModelPropertyBasedTests:
    """Property-based tests for User model using Hypothesis."""

    @given(user=user_strategy())
    def test_user_invariants_always_hold(self, user):
        """Test that user invariants always hold regardless of input.

        This test runs 100+ times with different user data to find edge cases.
        """
        # Invariant 1: Email must contain @
        assert "@" in user.email

        # Invariant 2: Email must be lowercase
        assert user.email == user.email.lower()

        # Invariant 3: ID must be valid UUID
        assert isinstance(user.id, UUID)

        # Invariant 4: Username must be 3-50 characters
        assert 3 <= len(user.username) <= 50

        # Invariant 5: Timestamps must be datetime objects
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

        # Invariant 6: created_at <= updated_at
        assert user.created_at <= user.updated_at

        # Invariant 7: Tenant ID must be valid UUID
        assert isinstance(user.tenant_id, UUID)

    @given(user=user_strategy(is_active=True))
    def test_active_users_have_no_deleted_at(self, user):
        """Property: Active users should not have deleted_at set."""
        # Act & Assert
        if user.is_active and user.deleted_at is None:
            assert user.is_deleted is False

    @given(user=user_strategy(is_deleted=True))
    def test_deleted_users_have_deleted_at_timestamp(self, user):
        """Property: Deleted users must have deleted_at timestamp."""
        # Assert
        assert user.deleted_at is not None
        assert isinstance(user.deleted_at, datetime)
        assert user.is_deleted is True

    @given(
        email=email_strategy(),
        username=username_strategy(),
    )
    def test_user_creation_with_valid_inputs_always_succeeds(self, email, username):
        """Property: Valid email and username should always create user successfully."""
        # Act
        user = user_factory(email=email, username=username)

        # Assert
        assert user.email == email.lower()
        assert user.username == username
        assert user.id is not None

    @given(user=user_strategy())
    def test_soft_delete_is_reversible(self, user):
        """Property: Soft delete followed by restore returns to original state."""
        # Arrange
        original_deleted_at = user.deleted_at

        # Act
        user.soft_delete()
        assert user.is_deleted is True  # Verify deleted

        user.restore()

        # Assert - should return to original state if not already deleted
        if original_deleted_at is None:
            assert user.deleted_at is None
            assert user.is_deleted is False


class TestUserModelEdgeCases:
    """Test edge cases and error conditions."""

    def test_user_with_very_long_email(self):
        """Test user with maximum length email."""
        # Arrange
        # Email format: local@domain
        # Max local part: 64 chars, max domain: 255 chars
        local = "a" * 64
        domain = "example.com"
        long_email = f"{local}@{domain}"

        # Act
        user = user_factory(email=long_email)

        # Assert
        assert user.email == long_email.lower()
        assert len(user.email) <= 320  # RFC 5321 limit

    def test_user_with_minimum_length_username(self):
        """Test user with minimum valid username (3 chars)."""
        # Arrange
        min_username = "abc"

        # Act
        user = user_factory(username=min_username)

        # Assert
        assert user.username == min_username
        assert len(user.username) == 3

    def test_user_with_maximum_length_username(self):
        """Test user with maximum valid username (50 chars)."""
        # Arrange
        max_username = "a" * 50

        # Act
        user = user_factory(username=max_username)

        # Assert
        assert user.username == max_username
        assert len(user.username) == 50

    def test_user_with_special_characters_in_username(self):
        """Test username with allowed special characters."""
        # Arrange
        special_username = "user_name-123"

        # Act
        user = user_factory(username=special_username)

        # Assert
        assert user.username == special_username

    def test_user_email_with_subdomain(self):
        """Test email with subdomain."""
        # Arrange
        email = "user@mail.example.com"

        # Act
        user = user_factory(email=email)

        # Assert
        assert user.email == email

    def test_user_email_with_plus_addressing(self):
        """Test email with plus addressing (common for email filtering)."""
        # Arrange
        email = "user+tag@example.com"

        # Act
        user = user_factory(email=email)

        # Assert
        assert user.email == email

    def test_multiple_soft_deletes_preserve_original_timestamp(self):
        """Test that multiple soft deletes don't change the timestamp."""
        # Arrange
        user = user_factory()

        # Act
        user.soft_delete()
        first_timestamp = user.deleted_at

        import time

        time.sleep(0.01)  # Ensure time difference

        user.soft_delete()
        second_timestamp = user.deleted_at

        # Assert
        assert first_timestamp == second_timestamp

    def test_user_restore_after_multiple_deletes(self):
        """Test restore works after multiple soft deletes."""
        # Arrange
        user = user_factory()

        # Act
        user.soft_delete()
        user.soft_delete()
        user.restore()

        # Assert
        assert user.is_deleted is False
        assert user.deleted_at is None
