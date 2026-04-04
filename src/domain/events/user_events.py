"""User domain events.

These events represent things that happen to users in the domain.
They allow decoupled reactions to user lifecycle events.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from src.domain.events.base import DomainEvent


class UserCreatedEvent(DomainEvent):
    """Event published when a new user is created.

    This event allows other parts of the system to react to user creation
    without tight coupling (e.g., send welcome email, create profile, log audit).

    Example:
        >>> event = UserCreatedEvent(
        ...     aggregate_id=user.id,
        ...     user_id=user.id,
        ...     email=user.email,
        ...     username=user.username,
        ... )
        >>> await event_bus.publish(event)
    """

    user_id: UUID = Field(..., description="ID of the created user")
    email: str = Field(..., description="User's email address")
    username: str = Field(..., description="User's username")
    full_name: str | None = Field(default=None, description="User's full name")
    tenant_id: UUID | None = Field(default=None, description="Tenant ID (multi-tenancy)")


class UserUpdatedEvent(DomainEvent):
    """Event published when a user is updated.

    Allows systems to react to profile changes, synchronize caches, etc.

    Example:
        >>> event = UserUpdatedEvent(
        ...     aggregate_id=user.id,
        ...     user_id=user.id,
        ...     changed_fields=["full_name", "email"],
        ... )
        >>> await event_bus.publish(event)
    """

    user_id: UUID = Field(..., description="ID of the updated user")
    changed_fields: list[str] = Field(
        default_factory=list,
        description="List of fields that were changed",
    )
    previous_values: dict[str, str] | None = Field(
        default=None,
        description="Previous values of changed fields",
    )


class UserDeletedEvent(DomainEvent):
    """Event published when a user is soft-deleted.

    Allows cleanup actions, cache invalidation, audit logging, etc.

    Example:
        >>> event = UserDeletedEvent(
        ...     aggregate_id=user.id,
        ...     user_id=user.id,
        ...     email=user.email,
        ...     deleted_at=datetime.now(UTC),
        ... )
        >>> await event_bus.publish(event)
    """

    user_id: UUID = Field(..., description="ID of the deleted user")
    email: str = Field(..., description="User's email address")
    username: str = Field(..., description="User's username")
    deleted_at: datetime = Field(..., description="When user was deleted")
    soft_delete: bool = Field(
        default=True,
        description="True if soft delete, False if hard delete",
    )


class UserRestoredEvent(DomainEvent):
    """Event published when a soft-deleted user is restored.

    Allows re-activation of related services, cache restoration, etc.

    Example:
        >>> event = UserRestoredEvent(
        ...     aggregate_id=user.id,
        ...     user_id=user.id,
        ...     email=user.email,
        ...     restored_at=datetime.now(UTC),
        ... )
        >>> await event_bus.publish(event)
    """

    user_id: UUID = Field(..., description="ID of the restored user")
    email: str = Field(..., description="User's email address")
    username: str = Field(..., description="User's username")
    restored_at: datetime = Field(..., description="When user was restored")
