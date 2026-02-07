"""Server-Sent Events (SSE) endpoints for real-time streaming.

SSE provides unidirectional server → client streaming over HTTP.
It's simpler than WebSocket and perfect for:
- Live notifications
- Progress updates
- Live dashboards
- Real-time feeds
- Event streams

SSE vs WebSocket:
- SSE: Unidirectional (server → client), HTTP-based, automatic reconnection
- WebSocket: Bidirectional (full-duplex), custom protocol, manual reconnection

Benefits:
- Built-in browser support (EventSource API)
- Automatic reconnection
- Simpler than WebSocket
- Works through HTTP (no special ports)
- Text-based protocol

Use Cases:
- Notifications
- Live status updates
- Progress bars
- Live metrics
- News feeds

Example Client (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/v1/stream?token=JWT_TOKEN');

    eventSource.addEventListener('notification', (event) => {
        const data = JSON.parse(event.data);
        showNotification(data.message);
    });

    eventSource.addEventListener('domain_event', (event) => {
        const data = JSON.parse(event.data);
        console.log('Event:', data.event_type);
    });

    eventSource.addEventListener('heartbeat', (event) => {
        console.log('Server alive');
    });

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        // Automatic reconnection handled by browser
    });
    ```
"""

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)
router = APIRouter()


# Placeholder for dependencies
# TODO: Replace with actual DI container injection
async def get_redis_client() -> Redis:
    """Get Redis client for pub/sub."""
    return Redis.from_url("redis://localhost:6379")


async def get_current_user_id(token: str) -> UUID:
    """Get authenticated user ID from JWT token.

    Args:
        token: JWT token string

    Returns:
        User ID

    TODO: Implement actual JWT validation
    """
    # TODO: Implement JWT validation
    return UUID("00000000-0000-0000-0000-000000000001")


async def get_tenant_id(token: str) -> UUID:
    """Get tenant ID from JWT token.

    Args:
        token: JWT token string

    Returns:
        Tenant ID

    TODO: Implement actual JWT/tenant validation
    """
    # TODO: Implement tenant ID extraction
    return UUID("00000000-0000-0000-0000-000000000002")


@router.get("/stream")
async def sse_stream(
    request: Request,
    token: str = Query(..., description="JWT authentication token"),
    redis: Redis = Depends(get_redis_client),
):
    """Server-Sent Events endpoint for real-time updates.

    This endpoint provides unidirectional server → client streaming
    using the Server-Sent Events (SSE) protocol. Clients receive
    real-time updates without needing to poll.

    Event Types:
        - connected: Initial connection event
        - notification: User notifications
        - domain_event: Domain events (user.created, etc.)
        - heartbeat: Keep-alive ping (every 30 seconds)

    Args:
        request: FastAPI request (for disconnect detection)
        token: JWT token for authentication
        redis: Redis client for pub/sub

    Returns:
        EventSourceResponse with event stream

    Example Client:
        ```javascript
        const eventSource = new EventSource('/api/v1/stream?token=JWT_TOKEN');

        eventSource.addEventListener('notification', (event) => {
            const data = JSON.parse(event.data);
            showNotification(data.message);
        });

        eventSource.addEventListener('domain_event', (event) => {
            const data = JSON.parse(event.data);
            handleDomainEvent(data);
        });
        ```
    """
    # Authenticate user
    user_id = await get_current_user_id(token)
    tenant_id = await get_tenant_id(token)

    logger.info(
        "sse_connected",
        user_id=str(user_id),
        tenant_id=str(tenant_id),
    )

    async def event_generator():
        """Generate SSE events.

        Yields events in Server-Sent Events format:
            event: <event_type>
            id: <event_id>
            data: <json_data>
        """
        # Create Redis subscriber for user-specific events
        pubsub = redis.pubsub()

        try:
            # Subscribe to user-specific and tenant-specific channels
            await pubsub.subscribe(
                f"user:{user_id}",
                f"tenant:{tenant_id}",
            )

            # Send initial connection event
            yield {
                "event": "connected",
                "id": str(datetime.now(UTC).timestamp()),
                "data": json.dumps(
                    {
                        "user_id": str(user_id),
                        "tenant_id": str(tenant_id),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
            }

            last_heartbeat = datetime.now(UTC)

            # Stream events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("sse_client_disconnected", user_id=str(user_id))
                    break

                # Get message from Redis (non-blocking with timeout)
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )

                if message and message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])

                        yield {
                            "event": event_data.get("event_type", "message"),
                            "id": event_data.get("event_id", str(datetime.now(UTC).timestamp())),
                            "data": json.dumps(event_data),
                        }

                    except json.JSONDecodeError as e:
                        logger.error("sse_json_decode_error", error=str(e))

                else:
                    # Send heartbeat every 30 seconds
                    now = datetime.now(UTC)
                    if (now - last_heartbeat).total_seconds() >= 30:
                        yield {
                            "event": "heartbeat",
                            "id": str(now.timestamp()),
                            "data": json.dumps({"timestamp": now.isoformat()}),
                        }
                        last_heartbeat = now

                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("sse_cancelled", user_id=str(user_id))
            raise

        except Exception as e:
            logger.error("sse_error", user_id=str(user_id), error=str(e))
            raise

        finally:
            # Cleanup
            await pubsub.unsubscribe()
            await pubsub.close()
            logger.info("sse_closed", user_id=str(user_id))

    return EventSourceResponse(event_generator())


# SSE Event Publisher (used by backend services)
class SSEPublisher:
    """Publishes events to SSE clients via Redis pub/sub.

    This class is used by backend services to send events to
    connected SSE clients. Events are published to Redis channels,
    and the SSE endpoint delivers them to subscribed clients.

    Example:
        >>> publisher = SSEPublisher(redis_client)
        >>> await publisher.publish_to_user(
        ...     user_id,
        ...     "notification",
        ...     {"message": "New order received!"}
        ... )
    """

    def __init__(self, redis_client: Redis):
        """Initialize SSE publisher.

        Args:
            redis_client: Redis client for publishing
        """
        self._redis = redis_client

    async def publish_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: dict,
        event_id: str | None = None,
    ) -> None:
        """Publish event to specific user's SSE stream.

        Args:
            user_id: Target user
            event_type: Event type (e.g., "notification", "domain_event")
            data: Event payload
            event_id: Optional event ID (generated if not provided)

        Example:
            >>> await publisher.publish_to_user(
            ...     user_id,
            ...     "notification",
            ...     {"message": "Hello!", "level": "info"}
            ... )
        """
        message = {
            "event_type": event_type,
            "event_id": event_id or str(datetime.now(UTC).timestamp()),
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish(f"user:{user_id}", json.dumps(message))

        logger.debug(
            "sse_published_to_user",
            user_id=str(user_id),
            event_type=event_type,
        )

    async def publish_to_tenant(
        self,
        tenant_id: UUID,
        event_type: str,
        data: dict,
        event_id: str | None = None,
    ) -> None:
        """Publish event to all users in a tenant.

        Args:
            tenant_id: Target tenant
            event_type: Event type
            data: Event payload
            event_id: Optional event ID

        Example:
            >>> await publisher.publish_to_tenant(
            ...     tenant_id,
            ...     "system_notification",
            ...     {"message": "Maintenance scheduled for tonight"}
            ... )
        """
        message = {
            "event_type": event_type,
            "event_id": event_id or str(datetime.now(UTC).timestamp()),
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish(f"tenant:{tenant_id}", json.dumps(message))

        logger.debug(
            "sse_published_to_tenant",
            tenant_id=str(tenant_id),
            event_type=event_type,
        )

    async def publish_notification(
        self,
        user_id: UUID,
        message: str,
        level: str = "info",
        action_url: str | None = None,
    ) -> None:
        """Publish notification to user.

        Convenience method for sending user notifications.

        Args:
            user_id: Target user
            message: Notification message
            level: Notification level (info, success, warning, error)
            action_url: Optional URL for notification action

        Example:
            >>> await publisher.publish_notification(
            ...     user_id,
            ...     "Your order has been shipped!",
            ...     level="success",
            ...     action_url="/orders/123"
            ... )
        """
        data = {
            "message": message,
            "level": level,
            "action_url": action_url,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self.publish_to_user(user_id, "notification", data)


__all__ = [
    "SSEPublisher",
]
