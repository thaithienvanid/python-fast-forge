"""Comprehensive tests for the messaging queue abstractions.

Tests cover Message, MessagePriority, MessageQueue base class (subscribe,
_handle_message, from_url), RabbitMQQueue, and RedisQueue implementations.
"""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.messaging.queue import (
    Message,
    MessagePriority,
    MessageQueue,
)


# ─── MessagePriority ───────────────────────────────────────────────────────────


class TestMessagePriority:
    """Tests for MessagePriority enum."""

    def test_priority_values(self):
        assert MessagePriority.LOW == 0
        assert MessagePriority.NORMAL == 5
        assert MessagePriority.HIGH == 10
        assert MessagePriority.URGENT == 20

    def test_priority_comparison(self):
        assert MessagePriority.LOW < MessagePriority.NORMAL
        assert MessagePriority.NORMAL < MessagePriority.HIGH
        assert MessagePriority.HIGH < MessagePriority.URGENT

    def test_priority_is_int_enum(self):
        assert isinstance(MessagePriority.NORMAL.value, int)


# ─── Message ───────────────────────────────────────────────────────────────────


class TestMessage:
    """Tests for Message dataclass."""

    def test_minimal_creation(self):
        msg = Message(queue="tasks.email", body={"to": "user@example.com"})
        assert msg.queue == "tasks.email"
        assert msg.body == {"to": "user@example.com"}
        assert msg.priority == MessagePriority.NORMAL
        assert msg.retry_count == 0
        assert msg.max_retries == 3
        assert msg.delay == 0
        assert msg.timeout == 300
        assert msg.metadata == {}

    def test_auto_generated_id(self):
        msg = Message(queue="q", body={})
        # UUID format
        assert len(msg.id) == 36
        assert msg.id.count("-") == 4

    def test_unique_ids(self):
        msg1 = Message(queue="q", body={})
        msg2 = Message(queue="q", body={})
        assert msg1.id != msg2.id

    def test_auto_created_at(self):
        before = datetime.now(UTC)
        msg = Message(queue="q", body={})
        after = datetime.now(UTC)
        assert before <= msg.created_at <= after

    def test_custom_priority(self):
        msg = Message(queue="q", body={}, priority=MessagePriority.HIGH)
        assert msg.priority == MessagePriority.HIGH

    def test_custom_retry_count(self):
        msg = Message(queue="q", body={}, retry_count=2, max_retries=5)
        assert msg.retry_count == 2
        assert msg.max_retries == 5

    def test_custom_delay(self):
        msg = Message(queue="q", body={}, delay=60)
        assert msg.delay == 60

    def test_custom_metadata(self):
        msg = Message(queue="q", body={}, metadata={"trace_id": "abc"})
        assert msg.metadata == {"trace_id": "abc"}

    def test_to_dict(self):
        msg = Message(
            queue="tasks.email",
            body={"to": "user@example.com"},
            priority=MessagePriority.HIGH,
        )
        d = msg.to_dict()

        assert d["id"] == msg.id
        assert d["queue"] == "tasks.email"
        assert d["body"] == {"to": "user@example.com"}
        assert d["priority"] == MessagePriority.HIGH.value  # 10
        assert d["retry_count"] == 0
        assert d["max_retries"] == 3
        assert d["delay"] == 0
        assert d["timeout"] == 300
        assert d["metadata"] == {}
        # created_at should be ISO format
        datetime.fromisoformat(d["created_at"])

    def test_from_dict_roundtrip(self):
        original = Message(
            queue="tasks.email",
            body={"to": "user@example.com"},
            priority=MessagePriority.HIGH,
            retry_count=1,
            max_retries=3,
        )
        d = original.to_dict()
        restored = Message.from_dict(d)

        assert restored.id == original.id
        assert restored.queue == original.queue
        assert restored.body == original.body
        assert restored.priority == original.priority
        assert restored.retry_count == original.retry_count
        assert restored.max_retries == original.max_retries

    def test_from_dict_missing_id_generates_new(self):
        d = {"queue": "q", "body": {"x": 1}, "created_at": datetime.now(UTC).isoformat()}
        msg = Message.from_dict(d)
        assert msg.id  # Non-empty id generated

    def test_from_dict_missing_created_at(self):
        d = {"queue": "q", "body": {}}
        msg = Message.from_dict(d)
        assert msg.created_at is not None

    def test_from_dict_defaults(self):
        d = {"queue": "q", "body": {}}
        msg = Message.from_dict(d)
        assert msg.priority == MessagePriority.NORMAL
        assert msg.retry_count == 0
        assert msg.max_retries == 3
        assert msg.delay == 0
        assert msg.timeout == 300
        assert msg.metadata == {}


# ─── MessageQueue - Abstract Base ─────────────────────────────────────────────


class ConcreteMessageQueue(MessageQueue):
    """Concrete implementation for testing the abstract base class."""

    def __init__(self):
        super().__init__()
        self._connected = False
        self._acknowledged = []
        self._rejected = []

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def publish(self, queue, body, priority=MessagePriority.NORMAL, delay=0, **kwargs):
        return "test-message-id"

    async def start_consuming(self) -> None:
        pass

    async def stop_consuming(self) -> None:
        self._consuming = False

    async def acknowledge(self, message: Message) -> None:
        self._acknowledged.append(message.id)

    async def reject(self, message: Message, requeue: bool = False) -> None:
        self._rejected.append((message.id, requeue))


class TestMessageQueueBase:
    """Tests for MessageQueue base class methods."""

    def test_init_empty_handlers(self):
        q = ConcreteMessageQueue()
        assert q._handlers == {}
        assert q._consuming is False

    def test_subscribe_registers_handler(self):
        q = ConcreteMessageQueue()

        @q.subscribe("tasks.email")
        async def email_handler(message):
            pass

        assert "tasks.email" in q._handlers
        assert email_handler in q._handlers["tasks.email"]

    def test_subscribe_returns_original_function(self):
        q = ConcreteMessageQueue()

        async def my_handler(message):
            return "handled"

        result = q.subscribe("tasks.email")(my_handler)
        assert result is my_handler

    def test_subscribe_multiple_handlers_same_queue(self):
        q = ConcreteMessageQueue()

        @q.subscribe("tasks.email")
        async def handler1(message):
            pass

        @q.subscribe("tasks.email")
        async def handler2(message):
            pass

        assert len(q._handlers["tasks.email"]) == 2

    def test_subscribe_multiple_queues(self):
        q = ConcreteMessageQueue()

        @q.subscribe("tasks.email")
        async def email_handler(message):
            pass

        @q.subscribe("tasks.sms")
        async def sms_handler(message):
            pass

        assert "tasks.email" in q._handlers
        assert "tasks.sms" in q._handlers

    @pytest.mark.asyncio
    async def test_handle_message_no_handlers_acknowledges(self):
        """With no handlers, _handle_message should acknowledge the message."""
        q = ConcreteMessageQueue()
        msg = Message(queue="tasks.email", body={})

        await q._handle_message("tasks.email", msg)

        assert msg.id in q._acknowledged

    @pytest.mark.asyncio
    async def test_handle_message_calls_handler(self):
        q = ConcreteMessageQueue()
        called_with = []

        @q.subscribe("tasks.email")
        async def email_handler(message):
            called_with.append(message)

        msg = Message(queue="tasks.email", body={"to": "user@example.com"})
        await q._handle_message("tasks.email", msg)

        assert len(called_with) == 1
        assert called_with[0] is msg

    @pytest.mark.asyncio
    async def test_handle_message_acknowledges_on_success(self):
        q = ConcreteMessageQueue()

        @q.subscribe("tasks.email")
        async def email_handler(message):
            pass

        msg = Message(queue="tasks.email", body={})
        await q._handle_message("tasks.email", msg)

        assert msg.id in q._acknowledged

    @pytest.mark.asyncio
    async def test_handle_message_retries_on_failure(self):
        q = ConcreteMessageQueue()

        @q.subscribe("tasks.email")
        async def failing_handler(message):
            raise ValueError("Processing failed")

        msg = Message(queue="tasks.email", body={}, retry_count=0, max_retries=3)
        await q._handle_message("tasks.email", msg)

        # Should have been requeued
        assert msg.retry_count == 1
        assert (msg.id, True) in q._rejected

    @pytest.mark.asyncio
    async def test_handle_message_dead_letter_at_max_retries(self):
        q = ConcreteMessageQueue()

        @q.subscribe("tasks.email")
        async def failing_handler(message):
            raise ValueError("Processing failed")

        msg = Message(queue="tasks.email", body={}, retry_count=3, max_retries=3)
        await q._handle_message("tasks.email", msg)

        # Should have been rejected without requeue (dead letter)
        assert (msg.id, False) in q._rejected

    @pytest.mark.asyncio
    async def test_handle_message_with_sync_handler(self):
        """Sync handlers (non-coroutine) should also work."""
        q = ConcreteMessageQueue()
        called = []

        @q.subscribe("tasks.sync")
        def sync_handler(message):
            called.append(message.id)

        msg = Message(queue="tasks.sync", body={})
        await q._handle_message("tasks.sync", msg)

        assert msg.id in called

    @pytest.mark.asyncio
    async def test_handle_message_calls_all_handlers(self):
        q = ConcreteMessageQueue()
        call_order = []

        @q.subscribe("tasks.email")
        async def handler1(message):
            call_order.append("handler1")

        @q.subscribe("tasks.email")
        async def handler2(message):
            call_order.append("handler2")

        msg = Message(queue="tasks.email", body={})
        await q._handle_message("tasks.email", msg)

        assert "handler1" in call_order
        assert "handler2" in call_order


# ─── MessageQueue.from_url ─────────────────────────────────────────────────────


class TestMessageQueueFromUrl:
    """Tests for MessageQueue.from_url() factory method."""

    def test_amqp_returns_rabbitmq_queue(self):
        queue = MessageQueue.from_url("amqp://localhost:5672")
        from src.infrastructure.messaging.rabbitmq import RabbitMQQueue

        assert isinstance(queue, RabbitMQQueue)

    def test_amqps_returns_rabbitmq_queue(self):
        queue = MessageQueue.from_url("amqps://localhost:5671")
        from src.infrastructure.messaging.rabbitmq import RabbitMQQueue

        assert isinstance(queue, RabbitMQQueue)

    def test_redis_returns_redis_queue(self):
        queue = MessageQueue.from_url("redis://localhost:6379/0")
        from src.infrastructure.messaging.redis_queue import RedisQueue

        assert isinstance(queue, RedisQueue)

    def test_sqs_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="SQS queue not yet implemented"):
            MessageQueue.from_url("sqs://us-east-1")

    def test_unknown_scheme_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported queue URL scheme"):
            MessageQueue.from_url("kafka://localhost:9092")

    def test_url_passed_to_rabbitmq(self):
        url = "amqp://user:pass@localhost:5672/vhost"
        queue = MessageQueue.from_url(url)
        assert queue._url == url

    def test_url_passed_to_redis(self):
        url = "redis://localhost:6379/1"
        queue = MessageQueue.from_url(url)
        assert queue._url == url

    def test_kwargs_passed_to_rabbitmq(self):
        queue = MessageQueue.from_url("amqp://localhost", heartbeat=60)
        assert queue._options.get("heartbeat") == 60

    def test_kwargs_passed_to_redis(self):
        queue = MessageQueue.from_url("redis://localhost", decode_responses=True)
        assert queue._options.get("decode_responses") is True


# ─── RabbitMQQueue ─────────────────────────────────────────────────────────────


class TestRabbitMQQueue:
    """Tests for RabbitMQQueue implementation."""

    def _make_queue(self):
        from src.infrastructure.messaging.rabbitmq import RabbitMQQueue

        return RabbitMQQueue("amqp://localhost:5672")

    def test_init(self):
        q = self._make_queue()
        assert q._url == "amqp://localhost:5672"
        assert q._connection is None
        assert q._channel is None
        assert q._queues == {}
        assert q._consumer_tags == {}

    @pytest.mark.asyncio
    async def test_connect_import_error_graceful(self):
        """When aio_pika is not installed, connect should not raise."""
        q = self._make_queue()
        with patch.dict("sys.modules", {"aio_pika": None}):
            # When import fails, should continue in degraded mode
            await q.connect()
        # Both should be None (degraded mode)
        assert q._connection is None
        assert q._channel is None

    @pytest.mark.asyncio
    async def test_connect_success(self):
        q = self._make_queue()
        mock_aio_pika = MagicMock()
        mock_connection = AsyncMock()
        mock_channel = AsyncMock()
        mock_aio_pika.connect_robust = AsyncMock(return_value=mock_connection)
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_aio_pika.ExchangeType = MagicMock()

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            await q.connect()

        mock_aio_pika.connect_robust.assert_called_once()
        mock_connection.channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_error_raises(self):
        q = self._make_queue()
        mock_aio_pika = MagicMock()
        mock_aio_pika.connect_robust = AsyncMock(side_effect=ConnectionError("refused"))

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}), pytest.raises(ConnectionError):
            await q.connect()

    @pytest.mark.asyncio
    async def test_disconnect_with_no_connection(self):
        """Disconnect should not raise when not connected."""
        q = self._make_queue()
        await q.disconnect()  # Should not raise

    @pytest.mark.asyncio
    async def test_disconnect_closes_channel_and_connection(self):
        q = self._make_queue()
        mock_channel = AsyncMock()
        mock_connection = AsyncMock()
        q._channel = mock_channel
        q._connection = mock_connection

        await q.disconnect()

        mock_channel.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_declare_queue_returns_cached(self):
        q = self._make_queue()
        mock_queue = MagicMock()
        q._queues["tasks.email"] = mock_queue

        result = await q._declare_queue("tasks.email")
        assert result is mock_queue

    @pytest.mark.asyncio
    async def test_declare_queue_no_channel(self):
        """Without channel, declare_queue should handle gracefully."""
        q = self._make_queue()
        q._channel = None

        result = await q._declare_queue("tasks.email")
        assert result is None
        assert q._queues["tasks.email"] is None

    @pytest.mark.asyncio
    async def test_declare_queue_with_channel(self):
        q = self._make_queue()
        mock_channel = AsyncMock()
        mock_queue = AsyncMock()
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
        q._channel = mock_channel

        result = await q._declare_queue("tasks.email")
        assert result is mock_queue
        assert q._queues["tasks.email"] is mock_queue

    @pytest.mark.asyncio
    async def test_publish_no_channel(self):
        """When no channel, publish should return message ID (degraded mode)."""
        q = self._make_queue()
        q._channel = None
        # Seed the queue cache so _declare_queue returns None
        q._queues["tasks.email"] = None

        message_id = await q.publish("tasks.email", {"to": "user@example.com"})
        assert message_id  # Should return some ID

    @pytest.mark.asyncio
    async def test_publish_with_channel(self):
        q = self._make_queue()
        mock_aio_pika = MagicMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        mock_channel.default_exchange = mock_exchange
        mock_aio_pika.Message = MagicMock(return_value=MagicMock())
        mock_aio_pika.DeliveryMode = MagicMock()
        q._channel = mock_channel
        q._queues["tasks.email"] = MagicMock()

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            message_id = await q.publish("tasks.email", {"to": "user@example.com"})

        assert message_id  # Should return valid ID
        mock_exchange.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_with_delay(self):
        q = self._make_queue()
        mock_aio_pika = MagicMock()
        mock_channel = AsyncMock()
        mock_exchange = AsyncMock()
        mock_amqp_msg = MagicMock()
        mock_channel.default_exchange = mock_exchange
        mock_aio_pika.Message = MagicMock(return_value=mock_amqp_msg)
        mock_aio_pika.DeliveryMode = MagicMock()
        q._channel = mock_channel
        q._queues["tasks.email"] = MagicMock()

        with patch.dict("sys.modules", {"aio_pika": mock_aio_pika}):
            await q.publish("tasks.email", {}, delay=60)

        # expiration should be set
        assert mock_amqp_msg.expiration == str(60 * 1000)

    @pytest.mark.asyncio
    async def test_acknowledge_logs(self):
        q = self._make_queue()
        msg = Message(queue="q", body={})
        # Should not raise
        await q.acknowledge(msg)

    @pytest.mark.asyncio
    async def test_reject_logs(self):
        q = self._make_queue()
        msg = Message(queue="q", body={})
        # Should not raise
        await q.reject(msg, requeue=True)
        await q.reject(msg, requeue=False)

    @pytest.mark.asyncio
    async def test_stop_consuming(self):
        q = self._make_queue()
        q._consuming = True
        await q.stop_consuming()
        assert q._consuming is False

    @pytest.mark.asyncio
    async def test_stop_consuming_cancels_consumer_tags(self):
        q = self._make_queue()
        mock_queue = AsyncMock()
        mock_channel = AsyncMock()
        q._queues["tasks.email"] = mock_queue
        q._channel = mock_channel
        q._consumer_tags["tasks.email"] = "ctag-1"

        await q.stop_consuming()

        mock_queue.cancel.assert_called_once_with("ctag-1")


# ─── RedisQueue ─────────────────────────────────────────────────────────────────


class TestRedisQueue:
    """Tests for RedisQueue implementation."""

    def _make_queue(self):
        from src.infrastructure.messaging.redis_queue import RedisQueue

        return RedisQueue("redis://localhost:6379/0")

    def test_init(self):
        q = self._make_queue()
        assert q._url == "redis://localhost:6379/0"
        assert q._redis is None
        assert q._delayed_task is None
        assert q._consumer_tasks == {}

    @pytest.mark.asyncio
    async def test_connect_success(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with patch("src.infrastructure.messaging.redis_queue.Redis") as mock_cls:
            mock_cls.from_url.return_value = mock_redis
            await q.connect()

        mock_redis.ping.assert_called_once()
        assert q._redis is mock_redis

    @pytest.mark.asyncio
    async def test_connect_failure_raises(self):
        q = self._make_queue()
        with patch("src.infrastructure.messaging.redis_queue.Redis") as mock_cls:
            mock_cls.from_url.side_effect = ConnectionError("refused")
            with pytest.raises(ConnectionError):
                await q.connect()

    @pytest.mark.asyncio
    async def test_disconnect_without_connection(self):
        q = self._make_queue()
        await q.disconnect()  # Should not raise

    @pytest.mark.asyncio
    async def test_disconnect_closes_redis(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        q._redis = mock_redis

        await q.disconnect()
        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_cancels_delayed_task(self):
        q = self._make_queue()
        mock_task = AsyncMock()
        mock_task.cancel = MagicMock()
        q._delayed_task = mock_task
        q._redis = AsyncMock()

        await q.disconnect()
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_not_connected_raises(self):
        q = self._make_queue()
        with pytest.raises(RuntimeError, match="Redis queue not connected"):
            await q.publish("tasks.email", {})

    @pytest.mark.asyncio
    async def test_publish_immediate_uses_lpush(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        q._redis = mock_redis

        msg_id = await q.publish("tasks.email", {"to": "user@example.com"})

        mock_redis.lpush.assert_called_once()
        assert msg_id  # Returns message ID

    @pytest.mark.asyncio
    async def test_publish_with_priority(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        q._redis = mock_redis

        await q.publish("tasks.email", {}, priority=MessagePriority.HIGH)

        call_args = mock_redis.lpush.call_args[0]
        # Queue key should include priority value
        assert f"p{MessagePriority.HIGH.value}" in call_args[0]

    @pytest.mark.asyncio
    async def test_publish_with_delay_uses_zadd(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        q._redis = mock_redis

        await q.publish("tasks.email", {}, delay=60)

        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args[0]
        assert call_args[0] == "delayed:tasks.email"

    @pytest.mark.asyncio
    async def test_publish_failure_raises(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        mock_redis.lpush = AsyncMock(side_effect=RuntimeError("Redis error"))
        q._redis = mock_redis

        with pytest.raises(RuntimeError, match="Redis error"):
            await q.publish("tasks.email", {})

    @pytest.mark.asyncio
    async def test_start_consuming_not_connected_raises(self):
        q = self._make_queue()
        with pytest.raises(RuntimeError, match="Redis queue not connected"):
            await q.start_consuming()

    @pytest.mark.asyncio
    async def test_stop_consuming(self):
        q = self._make_queue()
        q._consuming = True
        q._delayed_task = None
        q._consumer_tasks = {}

        await q.stop_consuming()
        assert q._consuming is False

    @pytest.mark.asyncio
    async def test_stop_consuming_cancels_tasks(self):
        q = self._make_queue()

        # Use a real asyncio task to simulate consumer task
        async def noop():
            await asyncio.sleep(100)

        task = asyncio.create_task(noop())
        q._consumer_tasks["tasks.email"] = task

        await q.stop_consuming()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_acknowledge_logs(self):
        q = self._make_queue()
        msg = Message(queue="q", body={})
        await q.acknowledge(msg)  # Should not raise

    @pytest.mark.asyncio
    async def test_reject_requeue_true(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        q._redis = mock_redis
        msg = Message(queue="tasks.email", body={}, priority=MessagePriority.NORMAL)

        await q.reject(msg, requeue=True)

        mock_redis.lpush.assert_called_once()
        call_args = mock_redis.lpush.call_args[0]
        assert "queue:tasks.email" in call_args[0]

    @pytest.mark.asyncio
    async def test_reject_requeue_false_dlq(self):
        q = self._make_queue()
        mock_redis = AsyncMock()
        q._redis = mock_redis
        msg = Message(queue="tasks.email", body={})

        await q.reject(msg, requeue=False)

        mock_redis.lpush.assert_called_once()
        call_args = mock_redis.lpush.call_args[0]
        assert call_args[0] == "dlq:tasks.email"

    @pytest.mark.asyncio
    async def test_reject_without_redis_is_noop(self):
        q = self._make_queue()
        q._redis = None
        msg = Message(queue="tasks.email", body={})
        await q.reject(msg, requeue=True)  # Should not raise

    @pytest.mark.asyncio
    async def test_consume_queue_cancellation(self):
        """_consume_queue should stop on CancelledError."""
        q = self._make_queue()
        mock_redis = AsyncMock()
        mock_redis.brpop = AsyncMock(side_effect=asyncio.CancelledError())
        q._redis = mock_redis
        q._consuming = True

        # Should return without raising
        await q._consume_queue("tasks.email")

    @pytest.mark.asyncio
    async def test_consume_queue_processes_message(self):
        q = self._make_queue()
        mock_redis = AsyncMock()

        # First call returns a message, second call returns None to stop
        msg = Message(queue="tasks.email", body={"key": "value"})
        msg_data = json.dumps(msg.to_dict()).encode()

        call_count = 0

        async def brpop_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (b"queue:tasks.email:p5", msg_data)
            q._consuming = False
            return None

        mock_redis.brpop = brpop_side_effect
        q._redis = mock_redis
        q._consuming = True

        processed = []

        @q.subscribe("tasks.email")
        async def handler(message):
            processed.append(message.id)

        await q._consume_queue("tasks.email")
        assert msg.id in processed

    @pytest.mark.asyncio
    async def test_process_delayed_messages_no_redis(self):
        q = self._make_queue()
        q._redis = None
        # Should return immediately
        await q._process_delayed_messages()

    @pytest.mark.asyncio
    async def test_process_delayed_messages_moves_ready(self):
        q = self._make_queue()
        mock_redis = AsyncMock()

        msg = Message(queue="tasks.email", body={})
        msg_data = json.dumps(msg.to_dict()).encode()

        call_count = 0

        async def zrangebyscore_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [msg_data]
            return []

        mock_redis.zrangebyscore = zrangebyscore_side_effect

        async def sleep_side_effect(seconds):
            q._consuming = False

        q._redis = mock_redis
        q._consuming = True
        q._handlers["tasks.email"] = []

        with patch("asyncio.sleep", side_effect=sleep_side_effect):
            await q._process_delayed_messages()

        mock_redis.lpush.assert_called_once()
        mock_redis.zrem.assert_called_once()
