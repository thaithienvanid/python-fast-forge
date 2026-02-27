"""Unit tests for CQRS command models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.app.commands import (
    CreateUserCommand,
    DeleteUserCommand,
    RestoreUserCommand,
    UpdateUserCommand,
)


class TestCreateUserCommand:
    """Tests for CreateUserCommand validation and behavior."""

    def test_creates_command_with_all_required_fields(self):
        """Command creation succeeds with all required fields."""
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            full_name="Test User",
            tenant_id=uuid4(),
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.email == "user@example.com"
        assert command.username == "testuser"
        assert command.full_name == "Test User"
        assert command.tenant_id is not None
        assert command.commanded_by is not None
        assert command.correlation_id is not None
        assert command.idempotency_key is not None

    def test_creates_command_without_optional_fields(self):
        """Command creation succeeds without optional fields."""
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.email == "user@example.com"
        assert command.username == "testuser"
        assert command.full_name is None
        assert command.tenant_id is None

    def test_rejects_invalid_email(self):
        """Rejects command with invalid email address."""
        with pytest.raises(ValidationError) as exc_info:
            CreateUserCommand(
                email="not-an-email",
                username="testuser",
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "email" in str(exc_info.value)

    def test_rejects_short_username(self):
        """Rejects command with username shorter than 3 chars."""
        with pytest.raises(ValidationError) as exc_info:
            CreateUserCommand(
                email="user@example.com",
                username="ab",
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "username" in str(exc_info.value)

    def test_rejects_long_username(self):
        """Rejects command with username longer than 100 chars."""
        with pytest.raises(ValidationError) as exc_info:
            CreateUserCommand(
                email="user@example.com",
                username="a" * 101,
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "username" in str(exc_info.value)

    def test_rejects_missing_commanded_by(self):
        """Rejects command without commanded_by field."""
        with pytest.raises(ValidationError) as exc_info:
            CreateUserCommand(
                email="user@example.com",
                username="testuser",
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "commanded_by" in str(exc_info.value)

    def test_command_is_immutable(self):
        """Command cannot be modified after creation (frozen)."""
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        with pytest.raises((ValidationError, AttributeError)):
            command.username = "newusername"


class TestUpdateUserCommand:
    """Tests for UpdateUserCommand validation and behavior."""

    def test_creates_command_with_all_fields(self):
        """Command creation succeeds with all fields."""
        user_id = uuid4()
        command = UpdateUserCommand(
            user_id=user_id,
            email="newemail@example.com",
            username="newusername",
            full_name="New Name",
            is_active=False,
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.user_id == user_id
        assert command.email == "newemail@example.com"
        assert command.username == "newusername"
        assert command.full_name == "New Name"
        assert command.is_active is False
        assert command.expected_version == 5

    def test_creates_command_with_partial_update(self):
        """Command supports partial updates (only some fields)."""
        user_id = uuid4()
        command = UpdateUserCommand(
            user_id=user_id,
            email="newemail@example.com",
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.user_id == user_id
        assert command.email == "newemail@example.com"
        assert command.username is None
        assert command.full_name is None
        assert command.is_active is None

    def test_requires_expected_version(self):
        """Command requires expected_version for optimistic locking."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateUserCommand(
                user_id=uuid4(),
                email="newemail@example.com",
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "expected_version" in str(exc_info.value)

    def test_rejects_invalid_email_in_update(self):
        """Rejects command with invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateUserCommand(
                user_id=uuid4(),
                email="not-an-email",
                expected_version=5,
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "email" in str(exc_info.value)

    def test_command_is_immutable(self):
        """Command cannot be modified after creation."""
        command = UpdateUserCommand(
            user_id=uuid4(),
            email="newemail@example.com",
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        with pytest.raises((ValidationError, AttributeError)):
            command.email = "different@example.com"


class TestDeleteUserCommand:
    """Tests for DeleteUserCommand validation and behavior."""

    def test_creates_command_with_soft_delete(self):
        """Command creation succeeds with soft_delete=True."""
        user_id = uuid4()
        command = DeleteUserCommand(
            user_id=user_id,
            soft_delete=True,
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.user_id == user_id
        assert command.soft_delete is True
        assert command.expected_version == 5

    def test_creates_command_with_hard_delete(self):
        """Command creation succeeds with soft_delete=False."""
        user_id = uuid4()
        command = DeleteUserCommand(
            user_id=user_id,
            soft_delete=False,
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.user_id == user_id
        assert command.soft_delete is False

    def test_defaults_to_soft_delete(self):
        """Command defaults to soft_delete=True when not specified."""
        user_id = uuid4()
        command = DeleteUserCommand(
            user_id=user_id,
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.soft_delete is True

    def test_requires_expected_version(self):
        """Command requires expected_version for optimistic locking."""
        with pytest.raises(ValidationError) as exc_info:
            DeleteUserCommand(
                user_id=uuid4(),
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "expected_version" in str(exc_info.value)

    def test_command_is_immutable(self):
        """Command cannot be modified after creation."""
        command = DeleteUserCommand(
            user_id=uuid4(),
            expected_version=5,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        with pytest.raises((ValidationError, AttributeError)):
            command.soft_delete = False


class TestRestoreUserCommand:
    """Tests for RestoreUserCommand validation and behavior."""

    def test_creates_command_successfully(self):
        """Command creation succeeds with all required fields."""
        user_id = uuid4()
        command = RestoreUserCommand(
            user_id=user_id,
            expected_version=6,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        assert command.user_id == user_id
        assert command.expected_version == 6

    def test_requires_expected_version(self):
        """Command requires expected_version for optimistic locking."""
        with pytest.raises(ValidationError) as exc_info:
            RestoreUserCommand(
                user_id=uuid4(),
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "expected_version" in str(exc_info.value)

    def test_requires_user_id(self):
        """Command requires user_id."""
        with pytest.raises(ValidationError) as exc_info:
            RestoreUserCommand(
                expected_version=6,
                commanded_by=uuid4(),
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            )

        assert "user_id" in str(exc_info.value)

    def test_command_is_immutable(self):
        """Command cannot be modified after creation."""
        command = RestoreUserCommand(
            user_id=uuid4(),
            expected_version=6,
            commanded_by=uuid4(),
            correlation_id=uuid4(),
            idempotency_key=uuid4(),
        )

        with pytest.raises((ValidationError, AttributeError)):
            command.expected_version = 7


class TestCommandMetadata:
    """Tests for common command metadata fields."""

    def test_all_commands_require_commanded_by(self):
        """All commands require commanded_by field."""
        commands = [
            lambda: CreateUserCommand(
                email="user@example.com",
                username="testuser",
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            ),
            lambda: UpdateUserCommand(
                user_id=uuid4(),
                expected_version=5,
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            ),
            lambda: DeleteUserCommand(
                user_id=uuid4(),
                expected_version=5,
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            ),
            lambda: RestoreUserCommand(
                user_id=uuid4(),
                expected_version=6,
                correlation_id=uuid4(),
                idempotency_key=uuid4(),
            ),
        ]

        for command_factory in commands:
            with pytest.raises(ValidationError) as exc_info:
                command_factory()
            assert "commanded_by" in str(exc_info.value)

    def test_all_commands_require_correlation_id(self):
        """All commands require correlation_id field."""
        commands = [
            lambda: CreateUserCommand(
                email="user@example.com",
                username="testuser",
                commanded_by=uuid4(),
                idempotency_key=uuid4(),
            ),
            lambda: UpdateUserCommand(
                user_id=uuid4(),
                expected_version=5,
                commanded_by=uuid4(),
                idempotency_key=uuid4(),
            ),
            lambda: DeleteUserCommand(
                user_id=uuid4(),
                expected_version=5,
                commanded_by=uuid4(),
                idempotency_key=uuid4(),
            ),
            lambda: RestoreUserCommand(
                user_id=uuid4(),
                expected_version=6,
                commanded_by=uuid4(),
                idempotency_key=uuid4(),
            ),
        ]

        for command_factory in commands:
            with pytest.raises(ValidationError) as exc_info:
                command_factory()
            assert "correlation_id" in str(exc_info.value)

    def test_all_commands_require_idempotency_key(self):
        """All commands require idempotency_key field."""
        commands = [
            lambda: CreateUserCommand(
                email="user@example.com",
                username="testuser",
                commanded_by=uuid4(),
                correlation_id=uuid4(),
            ),
            lambda: UpdateUserCommand(
                user_id=uuid4(),
                expected_version=5,
                commanded_by=uuid4(),
                correlation_id=uuid4(),
            ),
            lambda: DeleteUserCommand(
                user_id=uuid4(),
                expected_version=5,
                commanded_by=uuid4(),
                correlation_id=uuid4(),
            ),
            lambda: RestoreUserCommand(
                user_id=uuid4(),
                expected_version=6,
                commanded_by=uuid4(),
                correlation_id=uuid4(),
            ),
        ]

        for command_factory in commands:
            with pytest.raises(ValidationError) as exc_info:
                command_factory()
            assert "idempotency_key" in str(exc_info.value)
