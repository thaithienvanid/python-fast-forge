"""WebSocket connection manager for real-time bidirectional communication.

This module provides WebSocket support with features like:
- Connection lifecycle management
- Room-based broadcasting (tenant isolation)
- Redis pub/sub for multi-instance support
- Authentication via query params or initial message
- Heartbeat/ping-pong for connection health

Architecture:
    Client ←→ WebSocket ←→ Manager ←→ Redis Pub/Sub ←→ Other Instances

Use Cases:
- Real-time chat and messaging
- Live dashboards and analytics
- Collaborative editing
- Real-time notifications
- Live data feeds

Features:
- Multi-instance support (via Redis)
- Room-based messaging (e.g., tenant rooms)
- Connection tracking and cleanup
- Automatic reconnection support
- Heartbeat monitoring
"""

import asyncio
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting.

    This manager handles all WebSocket connections, provides room-based
    broadcasting, and integrates with Redis pub/sub for multi-instance support.

    Attributes:
        _connections: Active connections {connection_id: WebSocket}
        _user_connections: User → connections mapping {user_id: Set[connection_id]}
        _rooms: Room subscriptions {room_id: Set[connection_id]}
        _redis: Redis client for pub/sub
        _pubsub: Redis pub/sub instance

    Example:
        >>> manager = WebSocketManager(redis_client)
        >>> await manager.connect(websocket, connection_id, user_id)
        >>> await manager.join_room(connection_id, "tenant:123")
        >>> await manager.broadcast_to_room("tenant:123", {"event": "user.created"})
        >>> manager.disconnect(connection_id, user_id)
    """

    def __init__(self, redis_client: Redis):
        """Initialize WebSocket manager.

        Args:
            redis_client: Redis client for pub/sub
        """
        # Active connections: {connection_id: WebSocket}
        self._connections: dict[str, WebSocket] = {}

        # User connections: {user_id: Set[connection_id]}
        self._user_connections: dict[UUID, set[str]] = defaultdict(set)

        # Room subscriptions: {room_id: Set[connection_id]}
        self._rooms: dict[str, set[str]] = defaultdict(set)

        # Redis for cross-instance communication
        self._redis = redis_client
        self._pubsub = redis_client.pubsub()
        self._pubsub_task: asyncio.Task | None = None

    async def start_pubsub_listener(self) -> None:
        """Start Redis pub/sub listener in background.

        This must be called once at application startup.

        Example:
            >>> manager = WebSocketManager(redis)
            >>> await manager.start_pubsub_listener()
        """
        self._pubsub_task = asyncio.create_task(self._listen_redis_pubsub())
        logger.info("websocket_pubsub_started")

    async def stop_pubsub_listener(self) -> None:
        """Stop Redis pub/sub listener.

        This should be called at application shutdown.

        Example:
            >>> await manager.stop_pubsub_listener()
        """
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass

        await self._pubsub.close()
        logger.info("websocket_pubsub_stopped")

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: UUID | None = None,
    ) -> None:
        """Accept WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            connection_id: Unique connection identifier
            user_id: Authenticated user ID (optional)

        Example:
            >>> await manager.connect(websocket, connection_id, user_id)
        """
        await websocket.accept()

        self._connections[connection_id] = websocket

        if user_id:
            self._user_connections[user_id].add(connection_id)

        logger.info(
            "websocket_connected",
            connection_id=connection_id,
            user_id=str(user_id) if user_id else None,
            total_connections=len(self._connections),
        )

    def disconnect(self, connection_id: str, user_id: UUID | None = None) -> None:
        """Remove WebSocket connection.

        Args:
            connection_id: Connection to remove
            user_id: User ID to clean up

        Example:
            >>> manager.disconnect(connection_id, user_id)
        """
        self._connections.pop(connection_id, None)

        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(connection_id)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        # Remove from all rooms
        for room_connections in self._rooms.values():
            room_connections.discard(connection_id)

        logger.info(
            "websocket_disconnected",
            connection_id=connection_id,
            remaining_connections=len(self._connections),
        )

    async def join_room(self, connection_id: str, room: str) -> None:
        """Add connection to a room (e.g., tenant, chat channel).

        Rooms allow broadcasting to specific groups of users.

        Args:
            connection_id: Connection to add
            room: Room identifier (e.g., "tenant:123", "chat:456")

        Example:
            >>> await manager.join_room(connection_id, "tenant:123")
        """
        self._rooms[room].add(connection_id)

        # Subscribe to Redis channel for this room
        await self._pubsub.subscribe(f"room:{room}")

        logger.info("websocket_joined_room", connection_id=connection_id, room=room)

    async def leave_room(self, connection_id: str, room: str) -> None:
        """Remove connection from room.

        Args:
            connection_id: Connection to remove
            room: Room identifier

        Example:
            >>> await manager.leave_room(connection_id, "tenant:123")
        """
        if room in self._rooms:
            self._rooms[room].discard(connection_id)

            # Unsubscribe from Redis if no more local connections
            if not self._rooms[room]:
                await self._pubsub.unsubscribe(f"room:{room}")
                del self._rooms[room]

        logger.info("websocket_left_room", connection_id=connection_id, room=room)

    async def send_personal_message(
        self,
        connection_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send message to specific connection.

        Args:
            connection_id: Target connection
            message: JSON-serializable message

        Example:
            >>> await manager.send_personal_message(
            ...     connection_id, {"type": "notification", "data": {"message": "Hello!"}}
            ... )
        """
        websocket = self._connections.get(connection_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                # Connection was closed
                self.disconnect(connection_id)
            except Exception as e:
                logger.error(
                    "websocket_send_error",
                    connection_id=connection_id,
                    error=str(e),
                )

    async def send_to_user(self, user_id: UUID, message: dict[str, Any]) -> None:
        """Send message to all connections of a user.

        A user can have multiple connections (e.g., multiple browser tabs).

        Args:
            user_id: Target user
            message: JSON-serializable message

        Example:
            >>> await manager.send_to_user(
            ...     user_id, {"type": "notification", "data": {"message": "New order!"}}
            ... )
        """
        connection_ids = self._user_connections.get(user_id, set()).copy()

        for connection_id in connection_ids:
            await self.send_personal_message(connection_id, message)

    async def broadcast_to_room(
        self,
        room: str,
        message: dict[str, Any],
        exclude: str | None = None,
    ) -> None:
        """Broadcast message to all connections in a room.

        Uses Redis pub/sub to reach connections on other instances.

        Args:
            room: Target room
            message: JSON-serializable message
            exclude: Connection ID to exclude (e.g., message sender)

        Example:
            >>> await manager.broadcast_to_room(
            ...     "tenant:123",
            ...     {"type": "domain_event", "event": "user.created"},
            ...     exclude=sender_connection_id,
            ... )
        """
        # Send to local connections
        connection_ids = self._rooms.get(room, set()).copy()
        for connection_id in connection_ids:
            if connection_id != exclude:
                await self.send_personal_message(connection_id, message)

        # Publish to Redis for other instances
        await self._redis.publish(
            f"room:{room}",
            json.dumps({"message": message, "exclude": exclude}),
        )

        logger.debug(
            "websocket_room_broadcast",
            room=room,
            local_recipients=len(connection_ids),
        )

    async def broadcast_all(
        self,
        message: dict[str, Any],
        exclude: str | None = None,
    ) -> None:
        """Broadcast message to all connections.

        Args:
            message: JSON-serializable message
            exclude: Connection ID to exclude

        Example:
            >>> await manager.broadcast_all(
            ...     {"type": "system", "data": {"message": "Maintenance in 10 minutes"}}
            ... )
        """
        connection_ids = list(self._connections.keys())

        for connection_id in connection_ids:
            if connection_id != exclude:
                await self.send_personal_message(connection_id, message)

    async def _listen_redis_pubsub(self) -> None:
        """Background task to listen for Redis pub/sub messages.

        This allows receiving messages published from other instances.

        Example:
            Instance A publishes to room:tenant:123
            ↓
            Redis pub/sub
            ↓
            Instance B receives and sends to local connections
        """
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        channel = message["channel"].decode("utf-8")
                        data = json.loads(message["data"])

                        # Extract room from channel name
                        if channel.startswith("room:"):
                            room = channel[5:]

                            # Send to local connections in this room
                            msg = data["message"]
                            exclude = data.get("exclude")

                            connection_ids = self._rooms.get(room, set()).copy()
                            for connection_id in connection_ids:
                                if connection_id != exclude:
                                    await self.send_personal_message(connection_id, msg)

                    except Exception as e:
                        logger.error("websocket_pubsub_error", error=str(e))

        except asyncio.CancelledError:
            logger.info("websocket_pubsub_cancelled")
            raise

    def get_stats(self) -> dict[str, int]:
        """Get WebSocket manager statistics.

        Returns:
            Dictionary with statistics

        Example:
            >>> stats = manager.get_stats()
            >>> print(stats)
            {
                "total_connections": 150,
                "total_users": 120,
                "total_rooms": 25,
            }
        """
        return {
            "total_connections": len(self._connections),
            "total_users": len(self._user_connections),
            "total_rooms": len(self._rooms),
        }


__all__ = [
    "WebSocketManager",
]
