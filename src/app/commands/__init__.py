"""CQRS Command models for the write side.

Commands represent intentions to change system state. They are processed
by command handlers which validate business rules, produce domain events,
and persist them to the event store.

Command vs Event:
- Command: "Please create a user" (imperative, can fail)
- Event: "User was created" (past tense, already happened)

Features:
- Explicit command metadata (commanded_by, correlation_id, idempotency_key)
- Immutable commands (frozen=True)
- Type-safe with Pydantic validation
- Support for optimistic locking (expected_version)
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateUserCommand(BaseModel):
    """Command to create a new user.

    This command represents the intention to create a user. It will be
    processed by the UserCommandHandler which validates the request,
    creates domain events, and persists them to the event store.

    Attributes:
        email: User email address (validated)
        username: Unique username (3-100 chars, alphanumeric + _-)
        full_name: Optional full name
        tenant_id: Optional tenant identifier for multi-tenancy
        commanded_by: User who issued this command (for audit)
        correlation_id: Trace ID for cross-service tracking
        idempotency_key: Unique key to prevent duplicate processing

    Example:
        >>> command = CreateUserCommand(
        ...     email="user@example.com",
        ...     username="john",
        ...     full_name="John Doe",
        ...     commanded_by=admin_id,
        ...     correlation_id=trace_id,
        ...     idempotency_key=request_id,
        ... )
        >>> user_id = await command_handler.handle_create_user(command)
    """

    # User data
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=100, description="Unique username")
    full_name: str | None = Field(None, max_length=255, description="Full name")
    tenant_id: UUID | None = Field(None, description="Tenant identifier")

    # Command metadata
    commanded_by: UUID = Field(..., description="User who issued this command")
    correlation_id: UUID = Field(..., description="Correlation ID for tracing")
    idempotency_key: UUID = Field(..., description="Idempotency key (prevents duplicates)")

    class Config:
        """Pydantic configuration."""

        frozen = True  # Commands are immutable


class UpdateUserCommand(BaseModel):
    """Command to update an existing user.

    Supports partial updates - only provide fields that should be changed.
    Uses optimistic locking to prevent concurrent modification conflicts.

    Attributes:
        user_id: User to update
        email: New email (optional)
        username: New username (optional)
        full_name: New full name (optional)
        is_active: New active status (optional)
        expected_version: Current version (for optimistic locking)
        commanded_by: User who issued this command
        correlation_id: Trace ID for tracking
        idempotency_key: Unique key for idempotency

    Example:
        >>> command = UpdateUserCommand(
        ...     user_id=user_id,
        ...     email="newemail@example.com",
        ...     expected_version=5,  # Must match current version
        ...     commanded_by=admin_id,
        ...     correlation_id=trace_id,
        ...     idempotency_key=request_id,
        ... )
        >>> await command_handler.handle_update_user(command)
    """

    # Identity
    user_id: UUID = Field(..., description="User to update")

    # Updateable fields (all optional for partial updates)
    email: EmailStr | None = Field(None, description="New email address")
    username: str | None = Field(None, min_length=3, max_length=100, description="New username")
    full_name: str | None = Field(None, max_length=255, description="New full name")
    is_active: bool | None = Field(None, description="New active status")

    # Optimistic locking
    expected_version: int = Field(..., description="Expected current version")

    # Command metadata
    commanded_by: UUID = Field(..., description="User who issued this command")
    correlation_id: UUID = Field(..., description="Correlation ID for tracing")
    idempotency_key: UUID = Field(..., description="Idempotency key")

    class Config:
        """Pydantic configuration."""

        frozen = True


class DeleteUserCommand(BaseModel):
    """Command to soft-delete a user.

    Soft delete preserves the user record but marks it as deleted.
    The user can be restored later with RestoreUserCommand.

    Attributes:
        user_id: User to delete
        soft_delete: Whether to soft delete (default: True)
        expected_version: Current version (for optimistic locking)
        commanded_by: User who issued this command
        correlation_id: Trace ID for tracking
        idempotency_key: Unique key for idempotency

    Example:
        >>> command = DeleteUserCommand(
        ...     user_id=user_id,
        ...     soft_delete=True,
        ...     expected_version=5,
        ...     commanded_by=admin_id,
        ...     correlation_id=trace_id,
        ...     idempotency_key=request_id,
        ... )
        >>> await command_handler.handle_delete_user(command)
    """

    # Identity
    user_id: UUID = Field(..., description="User to delete")

    # Delete options
    soft_delete: bool = Field(True, description="Soft delete (recoverable) vs hard delete")

    # Optimistic locking
    expected_version: int = Field(..., description="Expected current version")

    # Command metadata
    commanded_by: UUID = Field(..., description="User who issued this command")
    correlation_id: UUID = Field(..., description="Correlation ID for tracing")
    idempotency_key: UUID = Field(..., description="Idempotency key")

    class Config:
        """Pydantic configuration."""

        frozen = True


class RestoreUserCommand(BaseModel):
    """Command to restore a soft-deleted user.

    Restores a user that was previously soft-deleted, making them active again.

    Attributes:
        user_id: User to restore
        expected_version: Current version (for optimistic locking)
        commanded_by: User who issued this command
        correlation_id: Trace ID for tracking
        idempotency_key: Unique key for idempotency

    Example:
        >>> command = RestoreUserCommand(
        ...     user_id=user_id,
        ...     expected_version=6,
        ...     commanded_by=admin_id,
        ...     correlation_id=trace_id,
        ...     idempotency_key=request_id,
        ... )
        >>> await command_handler.handle_restore_user(command)
    """

    # Identity
    user_id: UUID = Field(..., description="User to restore")

    # Optimistic locking
    expected_version: int = Field(..., description="Expected current version")

    # Command metadata
    commanded_by: UUID = Field(..., description="User who issued this command")
    correlation_id: UUID = Field(..., description="Correlation ID for tracing")
    idempotency_key: UUID = Field(..., description="Idempotency key")

    class Config:
        """Pydantic configuration."""

        frozen = True


__all__ = [
    "CreateUserCommand",
    "DeleteUserCommand",
    "RestoreUserCommand",
    "UpdateUserCommand",
]
