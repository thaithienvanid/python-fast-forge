"""Event bus for publishing and subscribing to domain events.

The event bus implements the pub/sub pattern for domain events, allowing
loose coupling between different parts of the system.
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from src.domain.events.base import DomainEvent
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class EventBus:
    """Event bus for domain event pub/sub.

    The event bus allows components to publish domain events and subscribe
    to events they're interested in, without tight coupling.

    Features:
    - Type-safe event subscriptions
    - Async event handlers
    - Error isolation (one handler failure doesn't affect others)
    - Event history tracking (optional)
    - Metrics tracking (published/handled/failed)

    Example:
        >>> bus = EventBus()
        >>>
        >>> # Subscribe to events
        >>> @bus.subscribe(UserCreatedEvent)
        >>> async def send_welcome_email(event: UserCreatedEvent):
        ...     await email_service.send(event.email, "Welcome!")
        >>>
        >>> # Publish events
        >>> event = UserCreatedEvent(user_id=user.id, email=user.email)
        >>> await bus.publish(event)
    """

    def __init__(self, track_history: bool = False) -> None:
        """Initialize event bus.

        Args:
            track_history: Whether to keep history of published events
        """
        self._handlers: dict[type[DomainEvent], list[Callable]] = defaultdict(list)
        self._track_history = track_history
        self._event_history: list[DomainEvent] = []

        # Metrics
        self._metrics = {
            "published": 0,
            "handled": 0,
            "failed": 0,
        }

    def subscribe(
        self,
        event_type: type[DomainEvent],
    ) -> Callable[[Callable], Callable]:
        """Subscribe to a specific event type.

        Can be used as a decorator or function.

        Args:
            event_type: The event class to subscribe to

        Returns:
            Decorator function that registers the handler

        Example:
            >>> # As decorator
            >>> @bus.subscribe(UserCreatedEvent)
            >>> async def handler(event: UserCreatedEvent):
            ...     print(f"User created: {event.user_id}")
            >>>
            >>> # As function
            >>> bus.subscribe(UserCreatedEvent)(handler)
        """

        def decorator(handler: Callable) -> Callable:
            self._handlers[event_type].append(handler)
            logger.info(
                "event_handler_registered",
                event_type=event_type.__name__,
                handler=handler.__name__,
            )
            return handler

        return decorator

    def unsubscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable,
    ) -> bool:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The event class
            handler: The handler function to remove

        Returns:
            True if handler was removed, False if not found

        Example:
            >>> bus.unsubscribe(UserCreatedEvent, send_welcome_email)
            True
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.info(
                "event_handler_unregistered",
                event_type=event_type.__name__,
                handler=handler.__name__,
            )
            return True
        return False

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all subscribed handlers.

        Handlers are called asynchronously and errors in one handler
        don't affect others.

        Args:
            event: The domain event to publish

        Example:
            >>> event = UserCreatedEvent(user_id=user.id, email=user.email)
            >>> await bus.publish(event)
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        self._metrics["published"] += 1

        # Track event history if enabled
        if self._track_history:
            self._event_history.append(event)

        logger.info(
            "domain_event_published",
            event_type=event.event_type,
            event_id=str(event.event_id),
            aggregate_id=str(event.aggregate_id),
            handler_count=len(handlers),
        )

        # If no handlers, that's ok - events can be published without subscribers
        if not handlers:
            logger.debug(
                "no_handlers_for_event",
                event_type=event.event_type,
            )
            return

        # Call all handlers concurrently
        tasks = [self._call_handler(handler, event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_handler(
        self,
        handler: Callable,
        event: DomainEvent,
    ) -> None:
        """Call a single event handler with error handling.

        Args:
            handler: The handler function to call
            event: The event to pass to the handler
        """
        try:
            result = handler(event)
            # Handle both sync and async handlers
            if asyncio.iscoroutine(result):
                await result

            self._metrics["handled"] += 1

            logger.debug(
                "event_handler_completed",
                handler=handler.__name__,
                event_type=event.event_type,
            )

        except Exception as e:
            self._metrics["failed"] += 1

            logger.error(
                "event_handler_failed",
                handler=handler.__name__,
                event_type=event.event_type,
                event_id=str(event.event_id),
                error=str(e),
                error_type=type(e).__name__,
            )

    def clear_handlers(self, event_type: type[DomainEvent] | None = None) -> None:
        """Clear all handlers for an event type, or all handlers.

        Args:
            event_type: Specific event type to clear, or None for all

        Example:
            >>> bus.clear_handlers(UserCreatedEvent)  # Clear specific
            >>> bus.clear_handlers()  # Clear all
        """
        if event_type:
            self._handlers[event_type].clear()
            logger.info("event_handlers_cleared", event_type=event_type.__name__)
        else:
            self._handlers.clear()
            logger.info("all_event_handlers_cleared")

    def get_handlers(self, event_type: type[DomainEvent]) -> list[Callable]:
        """Get all handlers for a specific event type.

        Args:
            event_type: The event class

        Returns:
            List of handler functions

        Example:
            >>> handlers = bus.get_handlers(UserCreatedEvent)
            >>> len(handlers)
            2
        """
        return self._handlers.get(event_type, [])

    def get_metrics(self) -> dict[str, Any]:
        """Get event bus metrics.

        Returns:
            Dictionary with published/handled/failed counts

        Example:
            >>> metrics = bus.get_metrics()
            >>> metrics["published"]
            42
        """
        return {
            **self._metrics,
            "handler_count": sum(len(handlers) for handlers in self._handlers.values()),
            "event_types": len(self._handlers),
        }

    def get_event_history(self) -> list[DomainEvent]:
        """Get history of published events (if tracking enabled).

        Returns:
            List of events in order published

        Example:
            >>> bus = EventBus(track_history=True)
            >>> await bus.publish(event)
            >>> history = bus.get_event_history()
            >>> len(history)
            1
        """
        if not self._track_history:
            logger.warning("event_history_not_enabled")
        return self._event_history.copy()

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
        logger.info("event_history_cleared")


# Global event bus instance
_global_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Creates the instance on first call (singleton pattern).

    Returns:
        The global EventBus instance

    Example:
        >>> bus = get_event_bus()
        >>> await bus.publish(event)
    """
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus(track_history=False)
    return _global_event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (mainly for testing).

    Example:
        >>> reset_event_bus()  # Get fresh bus for next test
    """
    global _global_event_bus
    _global_event_bus = None
