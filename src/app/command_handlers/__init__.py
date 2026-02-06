"""CQRS Command handlers for processing write operations.

Command handlers are responsible for:
1. Validating business rules
2. Reconstructing aggregates from event store (for updates)
3. Applying commands to aggregates
4. Creating and persisting domain events
5. Publishing events to event bus

The command handlers are the "write side" of CQRS, while query handlers
are the "read side". This separation allows independent scaling and optimization.

Features:
- Event sourcing (state derived from events)
- Optimistic locking (version-based concurrency control)
- Domain event publishing
- Aggregate reconstruction with snapshots
- Full audit trail via event store
"""

from datetime import UTC, datetime
from uuid import UUID

from uuid_extensions import uuid7

from src.app.commands import (
    CreateUserCommand,
    DeleteUserCommand,
    RestoreUserCommand,
    UpdateUserCommand,
)
from src.domain.events import (
    EventBus,
    UserCreatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
    UserUpdatedEvent,
)
from src.domain.events.base import DomainEvent
from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.domain.models.user import User
from src.infrastructure.repositories.event_store_repository import (
    EventStoreRepository,
)


class UserCommandHandler:
    """Handles user commands and produces domain events.

    This handler implements the command side of CQRS. It processes commands,
    validates business rules, and persists events to the event store.

    All state changes go through events - the current state is reconstructed
    by replaying all events for an aggregate.

    Attributes:
        _event_store: Repository for persisting events
        _event_bus: Bus for publishing events to subscribers

    Example:
        >>> handler = UserCommandHandler(event_store, event_bus)
        >>> command = CreateUserCommand(
        ...     email="user@example.com",
        ...     username="john",
        ...     commanded_by=admin_id,
        ...     correlation_id=trace_id,
        ...     idempotency_key=request_id,
        ... )
        >>> user_id = await handler.handle_create_user(command)
    """

    def __init__(
        self,
        event_store: EventStoreRepository,
        event_bus: EventBus,
    ):
        """Initialize command handler.

        Args:
            event_store: Repository for event persistence
            event_bus: Event bus for publishing events
        """
        self._event_store = event_store
        self._event_bus = event_bus

    async def handle_create_user(self, command: CreateUserCommand) -> UUID:
        """Handle CreateUserCommand.

        Creates a new user by:
        1. Validating the command
        2. Creating a new User aggregate
        3. Creating and persisting UserCreatedEvent
        4. Publishing the event to subscribers

        Args:
            command: Create user command

        Returns:
            Created user ID

        Raises:
            ValidationError: If validation fails

        Example:
            >>> command = CreateUserCommand(
            ...     email="user@example.com",
            ...     username="john",
            ...     commanded_by=admin_id,
            ...     correlation_id=trace_id,
            ...     idempotency_key=request_id,
            ... )
            >>> user_id = await handler.handle_create_user(command)
        """
        # Generate user ID
        user_id = uuid7()

        # Create User aggregate (this validates business rules)
        user = User(
            id=user_id,
            email=command.email,
            username=command.username,
            full_name=command.full_name,
            tenant_id=command.tenant_id,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Validate business rules
        user.validate()

        # Create domain event
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            tenant_id=user.tenant_id,
        )

        # Add command metadata to event
        event.metadata = {
            "commanded_by": str(command.commanded_by),
            "correlation_id": str(command.correlation_id),
            "causation_id": str(command.idempotency_key),
        }

        # Persist event to event store
        await self._event_store.append_event(
            event=event,
            aggregate_type="User",
            expected_version=None,  # New aggregate
        )

        # Publish event to subscribers
        await self._event_bus.publish(event)

        return user_id

    async def handle_update_user(self, command: UpdateUserCommand) -> None:
        """Handle UpdateUserCommand.

        Updates a user by:
        1. Reconstructing the User aggregate from event store
        2. Applying the changes
        3. Validating business rules
        4. Creating and persisting UserUpdatedEvent
        5. Publishing the event

        Args:
            command: Update user command

        Raises:
            EntityNotFoundError: If user doesn't exist
            ValidationError: If validation fails
            ConcurrencyError: If version mismatch (optimistic locking)

        Example:
            >>> command = UpdateUserCommand(
            ...     user_id=user_id,
            ...     email="newemail@example.com",
            ...     expected_version=5,
            ...     commanded_by=admin_id,
            ...     correlation_id=trace_id,
            ...     idempotency_key=request_id,
            ... )
            >>> await handler.handle_update_user(command)
        """
        # Reconstruct user from event store
        user = await self._reconstruct_user(command.user_id)

        # Track changes for event
        changed_fields: dict[str, tuple[str, str]] = {}

        # Apply changes
        if command.email and command.email != user.email:
            changed_fields["email"] = (user.email, command.email)
            user.email = command.email

        if command.username and command.username != user.username:
            changed_fields["username"] = (user.username, command.username)
            user.username = command.username

        if command.full_name is not None and command.full_name != user.full_name:
            changed_fields["full_name"] = (user.full_name or "", command.full_name)
            user.full_name = command.full_name

        if command.is_active is not None and command.is_active != user.is_active:
            changed_fields["is_active"] = (str(user.is_active), str(command.is_active))
            user.is_active = command.is_active

        # Validate business rules
        user.validate()

        # Update timestamp
        user.updated_at = datetime.now(UTC)

        # Create domain event
        event = UserUpdatedEvent(
            aggregate_id=command.user_id,
            user_id=command.user_id,
            changed_fields=changed_fields,
        )

        # Add command metadata
        event.metadata = {
            "commanded_by": str(command.commanded_by),
            "correlation_id": str(command.correlation_id),
            "causation_id": str(command.idempotency_key),
        }

        # Persist event (with optimistic locking)
        await self._event_store.append_event(
            event=event,
            aggregate_type="User",
            expected_version=command.expected_version,
        )

        # Publish event
        await self._event_bus.publish(event)

    async def handle_delete_user(self, command: DeleteUserCommand) -> None:
        """Handle DeleteUserCommand.

        Deletes (soft or hard) a user by creating and persisting UserDeletedEvent.

        Args:
            command: Delete user command

        Raises:
            EntityNotFoundError: If user doesn't exist
            ConcurrencyError: If version mismatch

        Example:
            >>> command = DeleteUserCommand(
            ...     user_id=user_id,
            ...     soft_delete=True,
            ...     expected_version=5,
            ...     commanded_by=admin_id,
            ...     correlation_id=trace_id,
            ...     idempotency_key=request_id,
            ... )
            >>> await handler.handle_delete_user(command)
        """
        # Reconstruct user (to verify it exists)
        user = await self._reconstruct_user(command.user_id)

        # Create domain event
        event = UserDeletedEvent(
            aggregate_id=command.user_id,
            user_id=command.user_id,
            email=user.email,
            username=user.username,
            soft_delete=command.soft_delete,
        )

        # Add command metadata
        event.metadata = {
            "commanded_by": str(command.commanded_by),
            "correlation_id": str(command.correlation_id),
            "causation_id": str(command.idempotency_key),
        }

        # Persist event
        await self._event_store.append_event(
            event=event,
            aggregate_type="User",
            expected_version=command.expected_version,
        )

        # Publish event
        await self._event_bus.publish(event)

    async def handle_restore_user(self, command: RestoreUserCommand) -> None:
        """Handle RestoreUserCommand.

        Restores a soft-deleted user by creating and persisting UserRestoredEvent.

        Args:
            command: Restore user command

        Raises:
            EntityNotFoundError: If user doesn't exist
            ValidationError: If user is not deleted
            ConcurrencyError: If version mismatch

        Example:
            >>> command = RestoreUserCommand(
            ...     user_id=user_id,
            ...     expected_version=6,
            ...     commanded_by=admin_id,
            ...     correlation_id=trace_id,
            ...     idempotency_key=request_id,
            ... )
            >>> await handler.handle_restore_user(command)
        """
        # Reconstruct user
        user = await self._reconstruct_user(command.user_id)

        # Validate user is deleted
        if not user.deleted_at:
            raise ValidationError("User is not deleted")

        # Create domain event
        event = UserRestoredEvent(
            aggregate_id=command.user_id,
            user_id=command.user_id,
            email=user.email,
            username=user.username,
        )

        # Add command metadata
        event.metadata = {
            "commanded_by": str(command.commanded_by),
            "correlation_id": str(command.correlation_id),
            "causation_id": str(command.idempotency_key),
        }

        # Persist event
        await self._event_store.append_event(
            event=event,
            aggregate_type="User",
            expected_version=command.expected_version,
        )

        # Publish event
        await self._event_bus.publish(event)

    async def _reconstruct_user(self, user_id: UUID) -> User:
        """Reconstruct user aggregate from event stream.

        Uses snapshot + incremental replay for performance.

        Args:
            user_id: User to reconstruct

        Returns:
            Reconstructed user aggregate

        Raises:
            EntityNotFoundError: If user doesn't exist

        Example:
            >>> user = await handler._reconstruct_user(user_id)
            >>> print(f"User {user.username} at version {user.version}")
        """
        # Try to load snapshot first
        snapshot = await self._event_store.get_snapshot(user_id, "User")

        if snapshot:
            version, snapshot_data = snapshot
            user = User.model_validate(snapshot_data)
            from_version = version
        else:
            user = None
            from_version = 0

        # Replay events since snapshot
        async for event in self._event_store.get_events(
            user_id, "User", from_version=from_version
        ):
            user = self._apply_event(user, event)

        if user is None:
            raise EntityNotFoundError(f"User {user_id} not found")

        return user

    def _apply_event(self, user: User | None, event: DomainEvent) -> User:
        """Apply event to user aggregate.

        This is the "event sourcing" part - we reconstruct state by
        applying all historical events in order.

        Args:
            user: Current user state (or None for first event)
            event: Event to apply

        Returns:
            Updated user state

        Example:
            >>> user = None
            >>> for event in events:
            ...     user = handler._apply_event(user, event)
        """
        if isinstance(event, UserCreatedEvent):
            # First event creates the user
            return User(
                id=event.user_id,
                email=event.email,
                username=event.username,
                full_name=event.full_name,
                tenant_id=event.tenant_id,
                is_active=True,
                created_at=event.occurred_at,
                updated_at=event.occurred_at,
            )

        elif isinstance(event, UserUpdatedEvent):
            # Update events modify fields
            if user is None:
                raise ValueError("Cannot apply UserUpdatedEvent to None")

            for field, (old_value, new_value) in event.changed_fields.items():
                setattr(user, field, new_value)
            user.updated_at = event.occurred_at
            return user

        elif isinstance(event, UserDeletedEvent):
            # Delete event sets deleted_at
            if user is None:
                raise ValueError("Cannot apply UserDeletedEvent to None")

            user.deleted_at = event.occurred_at
            return user

        elif isinstance(event, UserRestoredEvent):
            # Restore event clears deleted_at
            if user is None:
                raise ValueError("Cannot apply UserRestoredEvent to None")

            user.deleted_at = None
            user.updated_at = event.occurred_at
            return user

        # Unknown event type - just return user unchanged
        return user or User(
            id=uuid7(),
            email="unknown@example.com",
            username="unknown",
            is_active=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


__all__ = [
    "UserCommandHandler",
]
