"""Event handlers for domain events.

This module contains event handlers that react to domain events published
by use cases. Handlers are decoupled from business logic, following the
Single Responsibility Principle.

Design Pattern:
    Observer pattern - handlers observe domain events without coupling

Architecture:
    - Use cases publish events (business logic layer)
    - Handlers subscribe to events (infrastructure layer)
    - Clean separation between what happened (event) and what to do (handler)

Example:
    ```python
    # Use case publishes event (doesn't know about email)
    await event_bus.publish(UserCreatedEvent(user_id=user.id, email=user.email))


    # Handler reacts to event (doesn't know about use case)
    @event_bus.subscribe(UserCreatedEvent)
    async def send_welcome_email(event: UserCreatedEvent):
        await email_service.send_email(...)
    ```

Benefits:
    - Decoupled: Use cases don't depend on infrastructure
    - Testable: Can test use cases without email service
    - Extensible: Add new handlers without modifying use cases
    - Resilient: Handler failures don't affect use case success
"""

from .user_event_handlers import (
    log_user_creation_handler,
    send_welcome_email_handler,
    sync_user_to_analytics_handler,
)


__all__ = [
    "log_user_creation_handler",
    "send_welcome_email_handler",
    "sync_user_to_analytics_handler",
]
