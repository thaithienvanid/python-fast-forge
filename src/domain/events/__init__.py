"""Domain events for decoupled communication between aggregates.

This module provides the foundation for domain-driven design event handling,
allowing different parts of the system to react to domain events without
tight coupling.

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

from src.domain.events.base import DomainEvent
from src.domain.events.event_bus import EventBus, get_event_bus, reset_event_bus
from src.domain.events.user_events import (
    UserCreatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
    UserUpdatedEvent,
)


__all__ = [
    "DomainEvent",
    "EventBus",
    "UserCreatedEvent",
    "UserDeletedEvent",
    "UserRestoredEvent",
    "UserUpdatedEvent",
    "get_event_bus",
    "reset_event_bus",
]
