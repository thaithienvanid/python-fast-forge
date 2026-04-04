"""Comprehensive unit tests for WebSocketManager.

Covers missing lines in src/infrastructure/realtime/websocket_manager.py:
- Connection lifecycle (connect/disconnect)
- Room management (join/leave)
- Personal message sending
- User-targeted messaging
- Room broadcasting
- All-connection broadcasting
- Redis pub/sub listener
- Error handling for disconnected clients
- Connection statistics

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- AsyncMock for WebSocket and Redis methods
- Isolated mocking of Redis pub/sub
- Tests for error conditions
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect

from src.infrastructure.realtime.websocket_manager import WebSocketManager


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with pub/sub support."""
    redis = MagicMock()
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    pubsub.listen = AsyncMock()
    redis.pubsub = MagicMock(return_value=pubsub)
    redis.publish = AsyncMock()
    return redis


@pytest.fixture
def manager(mock_redis):
    """Create a WebSocketManager instance with mocked Redis."""
    return WebSocketManager(mock_redis)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def user_id():
    """Return a fixed user UUID."""
    return uuid4()


@pytest.fixture
def connection_id():
    """Return a fixed connection ID string."""
    return "test-connection-001"


# ============================================================================
# Connection Management Tests
# ============================================================================


class TestConnect:
    """Tests for WebSocketManager.connect."""

    async def test_accepts_websocket_connection(self, manager, mock_websocket, connection_id):
        """Test that connect() accepts the WebSocket connection.

        Arrange: Manager with no connections, mock WebSocket
        Act: Call connect()
        Assert: websocket.accept() called
        """
        await manager.connect(mock_websocket, connection_id)

        mock_websocket.accept.assert_called_once()

    async def test_adds_connection_to_connections_dict(
        self, manager, mock_websocket, connection_id
    ):
        """Test that connection is added to _connections dict.

        Arrange: Manager with no connections
        Act: Call connect()
        Assert: connection_id in _connections
        """
        await manager.connect(mock_websocket, connection_id)

        assert connection_id in manager._connections
        assert manager._connections[connection_id] is mock_websocket

    async def test_tracks_user_connection(self, manager, mock_websocket, connection_id, user_id):
        """Test that user_id -> connection_id mapping is tracked.

        Arrange: Manager, WebSocket, user_id
        Act: Call connect() with user_id
        Assert: connection_id in _user_connections[user_id]
        """
        await manager.connect(mock_websocket, connection_id, user_id=user_id)

        assert user_id in manager._user_connections
        assert connection_id in manager._user_connections[user_id]

    async def test_no_user_connection_tracking_without_user_id(
        self, manager, mock_websocket, connection_id
    ):
        """Test that _user_connections not populated when no user_id given.

        Arrange: Manager, WebSocket, no user_id
        Act: Call connect() without user_id
        Assert: _user_connections is empty
        """
        await manager.connect(mock_websocket, connection_id, user_id=None)

        assert len(manager._user_connections) == 0

    async def test_tracks_multiple_connections_for_same_user(
        self, manager, mock_websocket, user_id
    ):
        """Test multiple connections tracked for same user (multiple tabs).

        Arrange: Manager, two WebSocket instances for same user
        Act: Call connect() twice with same user_id
        Assert: Both connection_ids in _user_connections[user_id]
        """
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await manager.connect(mock_websocket, "conn-1", user_id=user_id)
        await manager.connect(ws2, "conn-2", user_id=user_id)

        assert "conn-1" in manager._user_connections[user_id]
        assert "conn-2" in manager._user_connections[user_id]


class TestDisconnect:
    """Tests for WebSocketManager.disconnect."""

    async def test_removes_connection_from_dict(self, manager, mock_websocket, connection_id):
        """Test that disconnect() removes connection from _connections.

        Arrange: Connected manager
        Act: Call disconnect()
        Assert: connection_id no longer in _connections
        """
        await manager.connect(mock_websocket, connection_id)

        manager.disconnect(connection_id)

        assert connection_id not in manager._connections

    async def test_removes_user_connection_tracking(
        self, manager, mock_websocket, connection_id, user_id
    ):
        """Test that disconnect() removes connection from user tracking.

        Arrange: Connected manager with user_id
        Act: Call disconnect() with user_id
        Assert: user_id removed from _user_connections
        """
        await manager.connect(mock_websocket, connection_id, user_id=user_id)

        manager.disconnect(connection_id, user_id=user_id)

        assert user_id not in manager._user_connections

    async def test_keeps_user_when_other_connections_remain(self, manager, mock_websocket, user_id):
        """Test that user tracking preserved when user has other connections.

        Arrange: User with two connections
        Act: Disconnect one connection
        Assert: Other connection still tracked for user
        """
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        await manager.connect(mock_websocket, "conn-1", user_id=user_id)
        await manager.connect(ws2, "conn-2", user_id=user_id)

        manager.disconnect("conn-1", user_id=user_id)

        assert user_id in manager._user_connections
        assert "conn-2" in manager._user_connections[user_id]
        assert "conn-1" not in manager._user_connections[user_id]

    async def test_removes_from_all_rooms(self, manager, mock_websocket, mock_redis, connection_id):
        """Test that disconnect() removes connection from all rooms.

        Arrange: Connected manager, connection in multiple rooms
        Act: Call disconnect()
        Assert: Connection removed from all room sets
        """
        await manager.connect(mock_websocket, connection_id)
        manager._rooms["room-1"].add(connection_id)
        manager._rooms["room-2"].add(connection_id)

        manager.disconnect(connection_id)

        assert connection_id not in manager._rooms.get("room-1", set())
        assert connection_id not in manager._rooms.get("room-2", set())

    async def test_disconnect_nonexistent_connection_is_safe(self, manager):
        """Test that disconnecting an unknown connection_id is safe (no error).

        Arrange: Manager with no connections
        Act: Call disconnect() with unknown id
        Assert: No exception raised
        """
        # Should not raise any exception
        manager.disconnect("nonexistent-connection-id")


# ============================================================================
# Room Management Tests
# ============================================================================


class TestJoinRoom:
    """Tests for WebSocketManager.join_room."""

    async def test_adds_connection_to_room(
        self, manager, mock_websocket, mock_redis, connection_id
    ):
        """Test join_room adds connection_id to room set.

        Arrange: Connected manager
        Act: Call join_room()
        Assert: connection_id in _rooms["room-1"]
        """
        await manager.connect(mock_websocket, connection_id)
        await manager.join_room(connection_id, "room-1")

        assert connection_id in manager._rooms["room-1"]

    async def test_subscribes_to_redis_channel(
        self, manager, mock_websocket, mock_redis, connection_id
    ):
        """Test join_room subscribes to Redis pub/sub channel.

        Arrange: Connected manager
        Act: Call join_room()
        Assert: _pubsub.subscribe called with correct channel
        """
        await manager.connect(mock_websocket, connection_id)
        await manager.join_room(connection_id, "tenant:123")

        manager._pubsub.subscribe.assert_called_once_with("room:tenant:123")

    async def test_multiple_connections_in_same_room(self, manager, mock_websocket, mock_redis):
        """Test that multiple connections can be in the same room.

        Arrange: Two connected clients
        Act: Both join same room
        Assert: Both in _rooms set
        """
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        await manager.connect(mock_websocket, "conn-1")
        await manager.connect(ws2, "conn-2")

        await manager.join_room("conn-1", "shared-room")
        await manager.join_room("conn-2", "shared-room")

        assert "conn-1" in manager._rooms["shared-room"]
        assert "conn-2" in manager._rooms["shared-room"]


class TestLeaveRoom:
    """Tests for WebSocketManager.leave_room."""

    async def test_removes_connection_from_room(
        self, manager, mock_websocket, mock_redis, connection_id
    ):
        """Test leave_room removes connection from room.

        Arrange: Connection in a room
        Act: Call leave_room()
        Assert: connection_id no longer in room
        """
        await manager.connect(mock_websocket, connection_id)
        await manager.join_room(connection_id, "test-room")

        await manager.leave_room(connection_id, "test-room")

        assert connection_id not in manager._rooms.get("test-room", set())

    async def test_unsubscribes_from_redis_when_room_empty(
        self, manager, mock_websocket, mock_redis, connection_id
    ):
        """Test Redis unsubscribe called when room has no more connections.

        Arrange: Connection in room
        Act: Leave room (last connection)
        Assert: _pubsub.unsubscribe called
        """
        await manager.connect(mock_websocket, connection_id)
        await manager.join_room(connection_id, "test-room")

        await manager.leave_room(connection_id, "test-room")

        manager._pubsub.unsubscribe.assert_called_once_with("room:test-room")

    async def test_does_not_unsubscribe_when_other_connections_remain(
        self, manager, mock_websocket, mock_redis
    ):
        """Test Redis unsubscribe NOT called when other connections remain in room.

        Arrange: Two connections in room
        Act: One connection leaves
        Assert: _pubsub.unsubscribe NOT called
        """
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        await manager.connect(mock_websocket, "conn-1")
        await manager.connect(ws2, "conn-2")
        await manager.join_room("conn-1", "test-room")
        await manager.join_room("conn-2", "test-room")

        await manager.leave_room("conn-1", "test-room")

        manager._pubsub.unsubscribe.assert_not_called()

    async def test_leave_nonexistent_room_is_safe(self, manager, connection_id):
        """Test leaving a room you're not in is safe (no error).

        Arrange: Connection not in any room
        Act: Call leave_room()
        Assert: No exception raised
        """
        # Should not raise any exception
        await manager.leave_room(connection_id, "nonexistent-room")


# ============================================================================
# Messaging Tests
# ============================================================================


class TestSendPersonalMessage:
    """Tests for WebSocketManager.send_personal_message."""

    async def test_sends_message_to_connected_client(self, manager, mock_websocket, connection_id):
        """Test sends JSON message to connected WebSocket.

        Arrange: Connected client
        Act: Call send_personal_message()
        Assert: websocket.send_json called with message
        """
        await manager.connect(mock_websocket, connection_id)
        message = {"type": "notification", "data": {"text": "Hello!"}}

        await manager.send_personal_message(connection_id, message)

        mock_websocket.send_json.assert_called_once_with(message)

    async def test_disconnects_on_websocket_disconnect_error(
        self, manager, mock_websocket, connection_id
    ):
        """Test handles WebSocketDisconnect by calling disconnect.

        Arrange: Connected client that raises WebSocketDisconnect on send
        Act: Call send_personal_message()
        Assert: Connection removed from manager
        """
        mock_websocket.send_json = AsyncMock(side_effect=WebSocketDisconnect())
        await manager.connect(mock_websocket, connection_id)

        await manager.send_personal_message(connection_id, {"type": "test"})

        # Connection should have been removed
        assert connection_id not in manager._connections

    async def test_logs_error_on_unexpected_exception(self, manager, mock_websocket, connection_id):
        """Test logs error when unexpected exception occurs during send.

        Arrange: Connected client that raises generic Exception
        Act: Call send_personal_message()
        Assert: No re-raise, connection still present (error logged)
        """
        mock_websocket.send_json = AsyncMock(side_effect=RuntimeError("Network error"))
        await manager.connect(mock_websocket, connection_id)

        # Should not raise
        with patch("src.infrastructure.realtime.websocket_manager.logger") as mock_logger:
            await manager.send_personal_message(connection_id, {"type": "test"})
            mock_logger.error.assert_called_once()

    async def test_ignores_unknown_connection_id(self, manager):
        """Test send to unknown connection_id is a no-op.

        Arrange: Manager with no connections
        Act: Call send_personal_message() with unknown id
        Assert: No exception raised
        """
        # Should not raise
        await manager.send_personal_message("unknown-conn", {"type": "test"})


class TestSendToUser:
    """Tests for WebSocketManager.send_to_user."""

    async def test_sends_message_to_all_user_connections(self, manager, mock_redis, user_id):
        """Test sends message to all connections of a user.

        Arrange: User with two connections
        Act: Call send_to_user()
        Assert: Both WebSockets receive the message
        """
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "conn-1", user_id=user_id)
        await manager.connect(ws2, "conn-2", user_id=user_id)
        message = {"type": "notification", "data": "Hello!"}

        await manager.send_to_user(user_id, message)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    async def test_ignores_unknown_user(self, manager, user_id):
        """Test send to unknown user_id is a no-op.

        Arrange: Manager with no connected users
        Act: Call send_to_user()
        Assert: No exception raised
        """
        # Should not raise
        await manager.send_to_user(user_id, {"type": "test"})


class TestBroadcastToRoom:
    """Tests for WebSocketManager.broadcast_to_room."""

    async def test_broadcasts_to_all_room_members(self, manager, mock_redis):
        """Test broadcasts message to all connections in a room.

        Arrange: Two connections in a room
        Act: Call broadcast_to_room()
        Assert: Both connections receive the message
        """
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "conn-1")
        await manager.connect(ws2, "conn-2")
        await manager.join_room("conn-1", "test-room")
        await manager.join_room("conn-2", "test-room")

        message = {"type": "event", "data": "broadcast"}
        await manager.broadcast_to_room("test-room", message)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    async def test_excludes_specified_connection(self, manager, mock_redis):
        """Test broadcast excludes the specified connection.

        Arrange: Two connections in a room
        Act: Call broadcast_to_room() with exclude=conn-1
        Assert: conn-1 does NOT receive the message, conn-2 does
        """
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "conn-1")
        await manager.connect(ws2, "conn-2")
        await manager.join_room("conn-1", "test-room")
        await manager.join_room("conn-2", "test-room")

        message = {"type": "event"}
        await manager.broadcast_to_room("test-room", message, exclude="conn-1")

        ws1.send_json.assert_not_called()
        ws2.send_json.assert_called_once_with(message)

    async def test_publishes_to_redis(self, manager, mock_redis, mock_websocket, connection_id):
        """Test that broadcast publishes to Redis pub/sub.

        Arrange: Connection in a room
        Act: Call broadcast_to_room()
        Assert: redis.publish called with room channel
        """
        await manager.connect(mock_websocket, connection_id)
        await manager.join_room(connection_id, "tenant:123")

        message = {"type": "event"}
        await manager.broadcast_to_room("tenant:123", message)

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args.args[0] if call_args.args else call_args.kwargs.get("channel")
        assert channel == "room:tenant:123"

    async def test_broadcast_to_empty_room_only_publishes_to_redis(self, manager, mock_redis):
        """Test that broadcast to empty room still publishes to Redis.

        Arrange: Room exists but is empty (no local connections)
        Act: Call broadcast_to_room()
        Assert: redis.publish still called
        """
        message = {"type": "event"}
        await manager.broadcast_to_room("empty-room", message)

        mock_redis.publish.assert_called_once()


class TestBroadcastAll:
    """Tests for WebSocketManager.broadcast_all."""

    async def test_broadcasts_to_all_connections(self, manager, mock_redis):
        """Test broadcasts message to all connected clients.

        Arrange: Three connections
        Act: Call broadcast_all()
        Assert: All three receive the message
        """
        ws_list = []
        for i in range(3):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            ws_list.append(ws)
            await manager.connect(ws, f"conn-{i}")

        message = {"type": "system", "data": "maintenance"}
        await manager.broadcast_all(message)

        for ws in ws_list:
            ws.send_json.assert_called_once_with(message)

    async def test_excludes_specified_connection_in_broadcast_all(self, manager, mock_redis):
        """Test broadcast_all excludes the specified connection.

        Arrange: Two connections
        Act: Call broadcast_all() with exclude=conn-1
        Assert: conn-1 does NOT receive, conn-2 does
        """
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "conn-1")
        await manager.connect(ws2, "conn-2")

        message = {"type": "system"}
        await manager.broadcast_all(message, exclude="conn-1")

        ws1.send_json.assert_not_called()
        ws2.send_json.assert_called_once_with(message)

    async def test_broadcast_all_with_no_connections(self, manager):
        """Test broadcast_all with no connections is a no-op.

        Arrange: Manager with no connections
        Act: Call broadcast_all()
        Assert: No exception raised
        """
        # Should not raise
        await manager.broadcast_all({"type": "test"})


# ============================================================================
# Pub/Sub Tests
# ============================================================================


class TestStartStopPubSubListener:
    """Tests for WebSocketManager.start_pubsub_listener and stop_pubsub_listener."""

    async def test_start_pubsub_listener_creates_task(self, manager):
        """Test start_pubsub_listener creates a background asyncio task.

        Arrange: Manager with mocked pubsub
        Act: Call start_pubsub_listener()
        Assert: _pubsub_task is set
        """

        async def fake_listen():
            return
            yield

        manager._pubsub.listen = MagicMock(return_value=fake_listen())

        await manager.start_pubsub_listener()

        assert manager._pubsub_task is not None
        # Cancel the task to clean up
        manager._pubsub_task.cancel()
        try:
            await manager._pubsub_task
        except asyncio.CancelledError:
            pass

    async def test_stop_pubsub_listener_cancels_task(self, manager):
        """Test stop_pubsub_listener cancels the background task.

        Arrange: Running pubsub listener
        Act: Call stop_pubsub_listener()
        Assert: Task is cancelled, pubsub is closed
        """

        async def fake_listen():
            while True:  # noqa: ASYNC110
                await asyncio.sleep(10)
            yield

        manager._pubsub.listen = MagicMock(return_value=fake_listen())

        await manager.start_pubsub_listener()
        await manager.stop_pubsub_listener()

        manager._pubsub.close.assert_called_once()

    async def test_stop_pubsub_listener_when_no_task(self, manager):
        """Test stop_pubsub_listener when no task is running is safe.

        Arrange: Manager with no pubsub task started
        Act: Call stop_pubsub_listener()
        Assert: No exception, pubsub.close called
        """
        assert manager._pubsub_task is None

        await manager.stop_pubsub_listener()

        manager._pubsub.close.assert_called_once()


# ============================================================================
# Statistics Tests
# ============================================================================


class TestGetStats:
    """Tests for WebSocketManager.get_stats."""

    async def test_returns_zeros_when_empty(self, manager):
        """Test get_stats returns zero counts when manager is empty.

        Arrange: Manager with no connections
        Act: Call get_stats()
        Assert: All counts are 0
        """
        stats = manager.get_stats()

        assert stats["total_connections"] == 0
        assert stats["total_users"] == 0
        assert stats["total_rooms"] == 0

    async def test_returns_correct_connection_count(self, manager, mock_redis, mock_websocket):
        """Test get_stats returns correct connection count.

        Arrange: Manager with 2 connections
        Act: Call get_stats()
        Assert: total_connections is 2
        """
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        await manager.connect(mock_websocket, "conn-1")
        await manager.connect(ws2, "conn-2")

        stats = manager.get_stats()

        assert stats["total_connections"] == 2

    async def test_returns_correct_user_count(self, manager, mock_redis, mock_websocket, user_id):
        """Test get_stats returns correct user count.

        Arrange: Manager with 1 user having 2 connections
        Act: Call get_stats()
        Assert: total_users is 1 (one unique user)
        """
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        await manager.connect(mock_websocket, "conn-1", user_id=user_id)
        await manager.connect(ws2, "conn-2", user_id=user_id)

        stats = manager.get_stats()

        assert stats["total_users"] == 1

    async def test_returns_correct_room_count(
        self, manager, mock_redis, mock_websocket, connection_id
    ):
        """Test get_stats returns correct room count.

        Arrange: Manager with connections in 2 rooms
        Act: Call get_stats()
        Assert: total_rooms is 2
        """
        await manager.connect(mock_websocket, connection_id)
        await manager.join_room(connection_id, "room-1")
        await manager.join_room(connection_id, "room-2")

        stats = manager.get_stats()

        assert stats["total_rooms"] == 2

    def test_stats_has_required_keys(self, manager):
        """Test that stats dict has all required keys.

        Arrange: Any manager state
        Act: Call get_stats()
        Assert: Dict contains total_connections, total_users, total_rooms
        """
        stats = manager.get_stats()

        assert "total_connections" in stats
        assert "total_users" in stats
        assert "total_rooms" in stats
