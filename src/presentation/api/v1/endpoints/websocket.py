"""WebSocket endpoints for real-time bidirectional communication.

This module provides WebSocket endpoints for real-time features like:
- Live notifications
- Chat and messaging
- Real-time dashboards
- Collaborative editing
- Live data feeds

Protocol:
    Client → Server:
        {"type": "subscribe", "room": "tenant:123"}
        {"type": "unsubscribe", "room": "tenant:123"}
        {"type": "ping"}
        {"type": "message", "room": "chat:456", "data": {...}}

    Server → Client:
        {"type": "connected", "connection_id": "...", "user_id": "..."}
        {"type": "subscribed", "room": "..."}
        {"type": "message", "data": {...}}
        {"type": "domain_event", "event": {...}}
        {"type": "notification", "data": {...}}
        {"type": "pong"}
        {"type": "error", "message": "..."}

Authentication:
    - JWT token via query parameter: ?token=JWT_TOKEN
    - Validates token and extracts user_id
    - Unauthenticated connections rejected

Example Client (JavaScript):
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/ws?token=JWT_TOKEN');

    ws.onopen = () => {
        // Subscribe to tenant room
        ws.send(JSON.stringify({type: 'subscribe', room: 'tenant:123'}));
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'domain_event') {
            console.log('Event:', data.event);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket closed');
    };
    ```
"""

from uuid import UUID, uuid4

from authlib.jose import JoseError
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from src.infrastructure.config import get_settings
from src.infrastructure.logging.config import get_logger
from src.infrastructure.realtime.websocket_manager import WebSocketManager
from src.utils.tenant_auth import decode_tenant_token

logger = get_logger(__name__)
router = APIRouter()

# Global Redis connection pool for WebSocket manager
_redis_pool: Redis | None = None


async def get_redis() -> Redis:
    """Get Redis connection from pool.

    Returns:
        Redis connection instance
    """
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = Redis.from_url(
            settings.redis_url,
            max_connections=settings.cache.redis_max_connections,
            decode_responses=False,  # WebSocket manager handles encoding
        )
    return _redis_pool


async def get_websocket_manager(redis: Redis = Depends(get_redis)) -> WebSocketManager:
    """Get WebSocket manager from dependency injection.

    Args:
        redis: Redis connection (injected)

    Returns:
        WebSocketManager instance
    """
    return WebSocketManager(redis)


async def authenticate_websocket(token: str) -> tuple[UUID, UUID]:
    """Authenticate WebSocket connection via JWT token.

    Args:
        token: JWT token string

    Returns:
        Tuple of (user_id, tenant_id) extracted from token

    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Decode and validate JWT token using authlib
        claims = decode_tenant_token(token)

        # Extract user_id from subject claim (standard JWT claim)
        # The sub claim contains the user_id in UUID format
        user_id = UUID(claims.sub) if claims.sub else None
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID",
            )

        tenant_id = claims.tenant_id

        logger.info(
            "websocket_authenticated",
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )

        return user_id, tenant_id

    except (JoseError, ValueError) as e:
        logger.warning(
            "websocket_authentication_failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}",
        )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """WebSocket endpoint for real-time communication.

    This endpoint provides bidirectional real-time communication using WebSocket.
    Clients can subscribe to rooms and receive real-time updates.

    Protocol:
        Client → Server:
            {"type": "subscribe", "room": "tenant:123"}
            {"type": "unsubscribe", "room": "tenant:123"}
            {"type": "ping"}

        Server → Client:
            {"type": "connected", "connection_id": "...", "user_id": "..."}
            {"type": "message", "data": {...}}
            {"type": "domain_event", "event": {...}}
            {"type": "pong"}
            {"type": "error", "message": "..."}

    Args:
        websocket: FastAPI WebSocket instance
        token: JWT token for authentication
        ws_manager: WebSocket manager (injected)

    Example:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/api/v1/ws?token=JWT_TOKEN');

        ws.onopen = () => {
            ws.send(JSON.stringify({type: 'subscribe', room: 'tenant:123'}));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
        };
        ```
    """
    connection_id = str(uuid4())
    user_id = None
    tenant_id = None

    try:
        # Authenticate user from token
        user_id, tenant_id = await authenticate_websocket(token)

        # Accept connection
        await ws_manager.connect(websocket, connection_id, user_id)

        # Auto-subscribe to tenant room for tenant-specific events
        tenant_room = f"tenant:{tenant_id}"
        await ws_manager.join_room(connection_id, tenant_room)

        # Send welcome message
        await ws_manager.send_personal_message(
            connection_id,
            {
                "type": "connected",
                "connection_id": connection_id,
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "auto_subscribed": [tenant_room],
            },
        )

        # Message loop
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            message_type = data.get("type")

            if message_type == "subscribe":
                # Subscribe to room with tenant isolation validation
                room = data.get("room")
                if room:
                    # Validate tenant isolation: users can only subscribe to their tenant's rooms
                    # Rooms should be namespaced: "tenant:<tenant_id>:..." or "user:<user_id>"
                    allowed = False
                    if room.startswith(f"tenant:{tenant_id}"):
                        allowed = True
                    elif room.startswith(f"user:{user_id}"):
                        allowed = True
                    elif room.startswith("public:"):
                        # Allow public rooms
                        allowed = True

                    if allowed:
                        await ws_manager.join_room(connection_id, room)
                        await ws_manager.send_personal_message(
                            connection_id, {"type": "subscribed", "room": room}
                        )
                    else:
                        await ws_manager.send_personal_message(
                            connection_id,
                            {
                                "type": "error",
                                "message": f"Access denied: cannot subscribe to room '{room}' (tenant isolation)",
                            },
                        )
                else:
                    await ws_manager.send_personal_message(
                        connection_id,
                        {"type": "error", "message": "Room name required"},
                    )

            elif message_type == "unsubscribe":
                # Unsubscribe from room
                room = data.get("room")
                if room:
                    await ws_manager.leave_room(connection_id, room)
                    await ws_manager.send_personal_message(
                        connection_id, {"type": "unsubscribed", "room": room}
                    )

            elif message_type == "ping":
                # Heartbeat
                await ws_manager.send_personal_message(
                    connection_id, {"type": "pong"}
                )

            elif message_type == "message":
                # Broadcast message to room
                room = data.get("room")
                message_data = data.get("data")

                if room and message_data:
                    await ws_manager.broadcast_to_room(
                        room,
                        {
                            "type": "message",
                            "from": str(user_id),
                            "data": message_data,
                        },
                        exclude=connection_id,  # Don't send back to sender
                    )
                else:
                    await ws_manager.send_personal_message(
                        connection_id,
                        {"type": "error", "message": "Room and data required"},
                    )

            else:
                await ws_manager.send_personal_message(
                    connection_id,
                    {"type": "error", "message": f"Unknown message type: {message_type}"},
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id, user_id)
        logger.info(
            "websocket_client_disconnected",
            connection_id=connection_id,
            user_id=str(user_id) if user_id else None,
        )

    except Exception as e:
        logger.error(
            "websocket_error",
            connection_id=connection_id,
            user_id=str(user_id) if user_id else None,
            error=str(e),
        )
        ws_manager.disconnect(connection_id, user_id)


@router.get("/ws/stats")
async def websocket_stats(
    ws_manager: WebSocketManager = Depends(get_websocket_manager),
) -> dict[str, int]:
    """Get WebSocket connection statistics.

    Returns:
        Statistics about active connections

    Example:
        GET /api/v1/ws/stats
        {
            "total_connections": 150,
            "total_users": 120,
            "total_rooms": 25
        }
    """
    return ws_manager.get_stats()
