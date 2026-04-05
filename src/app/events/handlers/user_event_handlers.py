"""Event handlers for user-related domain events.

This module contains handlers that react to user lifecycle events (creation,
update, deletion) in a decoupled manner, following event-driven architecture
principles.

Design Pattern:
    - Observer/Pub-Sub: Handlers subscribe to events
    - Single Responsibility: Each handler has one purpose
    - Dependency Inversion: Handlers depend on interfaces, not implementations

SOLID Principles:
    - S: Each handler has one reason to change
    - O: New handlers can be added without modifying use cases
    - D: Handlers depend on event abstractions, not concrete implementations
"""

from src.domain.events import UserCreatedEvent, UserDeletedEvent, UserUpdatedEvent
from src.domain.events.event_bus import get_event_bus
from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)


@get_event_bus().subscribe(UserCreatedEvent)
async def send_welcome_email_handler(event: UserCreatedEvent) -> None:
    """Send welcome email when user is created.

    This handler is triggered asynchronously after user creation succeeds.
    It handles the infrastructure concern of sending emails, keeping the
    business logic (user creation) decoupled from delivery mechanisms.

    Args:
        event: UserCreatedEvent containing user details

    Design Pattern:
        Event-driven architecture - handler reacts to domain event

    Error Handling:
        Failures are logged but don't affect the user creation transaction.
        This is acceptable because:
        - User creation already succeeded
        - Email is a notification, not critical business logic
        - Failed emails can be retried via background job

    Example:
        ```python
        # Triggered automatically when:
        await event_bus.publish(
            UserCreatedEvent(user_id=user.id, email=user.email, username=user.username)
        )
        ```

    Note:
        Uses Temporal workflow for reliability, retries, and observability.
        If Temporal is unavailable, gracefully degrades (logs error).
    """
    try:
        # Import here to avoid circular dependencies and make Temporal optional
        from src.app.tasks.user_tasks import SendWelcomeEmailWorkflow  # noqa: PLC0415
        from src.infrastructure.temporal_client import get_temporal_client  # noqa: PLC0415

        logger.info(
            "sending_welcome_email",
            user_id=str(event.user_id),
            email=event.email,
            username=event.username,
        )

        # Get Temporal client
        client = await get_temporal_client()

        # Start workflow asynchronously
        workflow_id = f"welcome-email-{event.user_id}"
        await client.start_workflow(
            SendWelcomeEmailWorkflow.run,
            args=[str(event.user_id), event.email],
            id=workflow_id,
            task_queue="user-tasks",
        )

        logger.info(
            "welcome_email_workflow_started",
            user_id=str(event.user_id),
            workflow_id=workflow_id,
        )

    except (ConnectionError, TimeoutError, OSError) as e:
        # Temporal connection issues - expected in some environments
        logger.warning(
            "failed_to_start_welcome_email_workflow_connection_error",
            user_id=str(event.user_id),
            error=str(e),
            error_type=type(e).__name__,
            message="Could not connect to Temporal server - email will not be sent",
        )

    except ImportError as e:
        # Temporal not installed - acceptable for non-production environments
        logger.info(
            "temporal_not_available",
            user_id=str(event.user_id),
            error=str(e),
            message="Temporal workflow client not available - skipping welcome email",
        )

    except Exception as e:
        # Unexpected error - log for investigation but don't fail
        logger.exception(
            "failed_to_start_welcome_email_workflow_unexpected",
            user_id=str(event.user_id),
            error=str(e),
            error_type=type(e).__name__,
        )


@get_event_bus().subscribe(UserCreatedEvent)
async def log_user_creation_handler(event: UserCreatedEvent) -> None:
    """Log structured event for user creation audit trail.

    Creates audit log entry for compliance, analytics, and debugging.

    Args:
        event: UserCreatedEvent containing user details

    Design Pattern:
        Audit logging via event-driven architecture

    Benefits:
        - Centralized audit logging
        - Decoupled from business logic
        - Easy to add/remove without changing use cases
    """
    logger.info(
        "user_created_audit",
        user_id=str(event.user_id),
        email=event.email,
        username=event.username,
        timestamp=event.occurred_at.isoformat(),
        event_type="user.created",
        message="New user successfully created",
    )


@get_event_bus().subscribe(UserCreatedEvent)
async def sync_user_to_analytics_handler(event: UserCreatedEvent) -> None:
    """Sync user creation to analytics platform.

    Sends user creation event to analytics service (e.g., Segment, Amplitude)
    for product analytics and user tracking.

    Args:
        event: UserCreatedEvent containing user details

    Design Pattern:
        Event-driven analytics integration

    Note:
        This is a placeholder. Implement actual analytics integration
        based on your analytics provider (Segment, Amplitude, Mixpanel, etc.)

    Example Integration:
        ```python
        import analytics

        analytics.identify(
            user_id=str(event.user_id),
            traits={
                "email": event.email,
                "username": event.username,
                "created_at": event.occurred_at.isoformat(),
            },
        )
        ```
    """
    try:
        logger.debug(
            "user_analytics_sync",
            user_id=str(event.user_id),
            email=event.email,
            message="User creation synced to analytics (placeholder)",
        )

        # TODO: Implement actual analytics integration
        # Example: await analytics_service.track_user_created(...)  # noqa: ERA001

    except Exception as e:
        # Analytics failures should not affect user creation
        logger.warning(
            "analytics_sync_failed",
            user_id=str(event.user_id),
            error=str(e),
            message="Failed to sync user to analytics - non-critical",
        )


@get_event_bus().subscribe(UserUpdatedEvent)
async def log_user_update_handler(event: UserUpdatedEvent) -> None:
    """Log user update events for audit trail.

    Args:
        event: UserUpdatedEvent containing update details

    Design Pattern:
        Audit logging for compliance

    Use Case:
        - GDPR compliance requires audit trail of user data changes
        - Security investigations need change history
        - Analytics needs user profile update tracking
    """
    logger.info(
        "user_updated_audit",
        user_id=str(event.user_id),
        timestamp=event.occurred_at.isoformat(),
        event_type="user.updated",
        message="User profile updated",
    )


@get_event_bus().subscribe(UserDeletedEvent)
async def log_user_deletion_handler(event: UserDeletedEvent) -> None:
    """Log user deletion events for audit trail.

    Args:
        event: UserDeletedEvent containing deletion details

    Design Pattern:
        Audit logging for compliance

    Use Case:
        - GDPR compliance requires audit trail of user deletions
        - Security investigations need deletion history
        - Compliance reports need deletion tracking
    """
    logger.info(
        "user_deleted_audit",
        user_id=str(event.user_id),
        timestamp=event.occurred_at.isoformat(),
        event_type="user.deleted",
        soft_delete=True,  # Assuming soft delete
        message="User soft deleted",
    )


# Export all handlers for easy registration
__all__ = [
    "log_user_creation_handler",
    "log_user_deletion_handler",
    "log_user_update_handler",
    "send_welcome_email_handler",
    "sync_user_to_analytics_handler",
]
