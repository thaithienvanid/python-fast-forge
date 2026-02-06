"""Domain events for decoupled communication between aggregates.

This module provides the foundation for domain-driven design event handling,
allowing different parts of the system to react to domain events without
tight coupling.

Features:
- Event registry for event type deserialization
- Type-safe event pub/sub with EventBus
- Support for event sourcing and CQRS

Example:
    >>> from src.domain.events import UserCreatedEvent, EventBus
    >>>
    >>> # Publish event
    >>> event = UserCreatedEvent(user_id=user.id, email=user.email)
    >>> await event_bus.publish(event)
    >>>
    >>> # Subscribe to events
    >>> @event_bus.subscribe(UserCreatedEvent)
    >>> async def send_welcome_email(event: UserCreatedEvent):
    ...     await email_service.send_welcome(event.email)
"""

from typing import Type

from src.domain.events.base import DomainEvent
from src.domain.events.event_bus import EventBus, get_event_bus, reset_event_bus
from src.domain.events.user_events import (
    UserCreatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
    UserUpdatedEvent,
)


# Event type registry for deserialization
# Maps event_type strings to event classes
EVENT_REGISTRY: dict[str, Type[DomainEvent]] = {}


def register_event(event_type: str):
    """Decorator to register event types for deserialization.

    This enables reconstructing domain events from event store entries.

    Args:
        event_type: Fully-qualified event type name (e.g., "user.created")

    Returns:
        Decorator function that registers the event class

    Example:
        >>> @register_event("user.created")
        >>> class UserCreatedEvent(DomainEvent):
        ...     user_id: UUID
        ...     email: str
        ...     username: str
    """

    def decorator(cls: Type[DomainEvent]) -> Type[DomainEvent]:
        EVENT_REGISTRY[event_type] = cls
        # Set event_type as class attribute for convenience
        cls.event_type = event_type  # type: ignore
        return cls

    return decorator


def get_event_class(event_type: str) -> Type[DomainEvent]:
    """Get event class from event type string.

    Args:
        event_type: Fully-qualified event type name

    Returns:
        Event class

    Raises:
        KeyError: If event type is not registered

    Example:
        >>> event_class = get_event_class("user.created")
        >>> event = event_class.model_validate(event_data)
    """
    if event_type not in EVENT_REGISTRY:
        raise KeyError(
            f"Event type '{event_type}' not registered. "
            f"Available types: {list(EVENT_REGISTRY.keys())}"
        )
    return EVENT_REGISTRY[event_type]


# Register built-in events
register_event("user.created")(UserCreatedEvent)
register_event("user.updated")(UserUpdatedEvent)
register_event("user.deleted")(UserDeletedEvent)
register_event("user.restored")(UserRestoredEvent)


__all__ = [
    "DomainEvent",
    "EventBus",
    "UserCreatedEvent",
    "UserDeletedEvent",
    "UserRestoredEvent",
    "UserUpdatedEvent",
    "get_event_bus",
    "reset_event_bus",
    "EVENT_REGISTRY",
    "register_event",
    "get_event_class",
]
