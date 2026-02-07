"""Redis message queue implementation.

Redis provides a lightweight queue implementation using:
- LIST data structure for queues (LPUSH/BRPOP)
- Sorted Sets for delayed/scheduled messages
- Pub/Sub for real-time notifications
- Stream API for advanced use cases

Example:
    >>> queue = RedisQueue("redis://localhost:6379/0")
    >>> await queue.connect()
    >>>
    >>> # Publish
    >>> await queue.publish(
    ...     "tasks.send_email",
    ...     {"to": "user@example.com", "subject": "Hello"},
    ... )
    >>>
    >>> # Subscribe
    >>> @queue.subscribe("tasks.send_email")
    >>> async def send_email_task(message: Message):
    ...     print(f"Sending email to {message.body['to']}")
    >>>
    >>> # Start consuming
    >>> await queue.start_consuming()
"""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from src.infrastructure.logging.config import get_logger
from src.infrastructure.messaging.queue import Message, MessagePriority, MessageQueue

logger = get_logger(__name__)


class RedisQueue(MessageQueue):
    """Redis implementation of MessageQueue.

    Uses Redis LIST for queue operations and Sorted Sets for delayed messages.

    Attributes:
        _url: Redis connection URL
        _redis: Redis client
        _delayed_task: Background task for delayed message processing

    Example:
        >>> queue = RedisQueue("redis://localhost:6379/0")
        >>> await queue.connect()
        >>> await queue.publish("tasks.email", {"to": "user@example.com"})
    """

    def __init__(self, url: str, **options: Any):
        """Initialize Redis queue.

        Args:
            url: Redis connection URL (redis://host:port/db)
            **options: Redis connection options
        """
        super().__init__()
        self._url = url
        self._options = options
        self._redis: Redis | None = None
        self._delayed_task: asyncio.Task | None = None
        self._consumer_tasks: dict[str, asyncio.Task] = {}

    async def connect(self) -> None:
        """Connect to Redis server.

        Example:
            >>> await queue.connect()
        """
        try:
            self._redis = Redis.from_url(self._url, **self._options)

            # Test connection
            await self._redis.ping()

            logger.info("redis_queue_connected", url=self._url)

        except Exception as e:
            logger.error("redis_queue_connection_failed", url=self._url, error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis server.

        Example:
            >>> await queue.disconnect()
        """
        try:
            # Stop delayed message task
            if self._delayed_task:
                self._delayed_task.cancel()
                try:
                    await self._delayed_task
                except asyncio.CancelledError:
                    pass

            # Close connection
            if self._redis:
                await self._redis.close()

            logger.info("redis_queue_disconnected")

        except Exception as e:
            logger.error("redis_queue_disconnect_failed", error=str(e))

    async def publish(
        self,
        queue: str,
        body: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        delay: int = 0,
        **kwargs: Any,
    ) -> str:
        """Publish message to Redis queue.

        Args:
            queue: Queue name
            body: Message payload
            priority: Message priority
            delay: Delay before processing (seconds)
            **kwargs: Additional message options

        Returns:
            Message ID

        Example:
            >>> message_id = await queue.publish(
            ...     "tasks.send_email",
            ...     {"to": "user@example.com"},
            ...     delay=60,  # Process in 1 minute
            ... )
        """
        if not self._redis:
            raise RuntimeError("Redis queue not connected")

        # Create message
        message = Message(
            queue=queue,
            body=body,
            priority=priority,
            delay=delay,
            **kwargs,
        )

        try:
            message_data = json.dumps(message.to_dict())

            if delay > 0:
                # Use sorted set for delayed messages
                # Score = timestamp when message should be processed
                process_at = datetime.now(UTC).timestamp() + delay
                await self._redis.zadd(
                    f"delayed:{queue}",
                    {message_data: process_at},
                )

                logger.info(
                    "delayed_message_published",
                    queue=queue,
                    message_id=message.id,
                    delay=delay,
                )

            else:
                # Use list for immediate messages
                # Priority queues use separate lists
                queue_key = f"queue:{queue}:p{priority.value}"

                await self._redis.lpush(queue_key, message_data)

                logger.info(
                    "message_published",
                    queue=queue,
                    message_id=message.id,
                    priority=priority.value,
                )

            return message.id

        except Exception as e:
            logger.error(
                "message_publish_failed",
                queue=queue,
                error=str(e),
            )
            raise

    async def start_consuming(self) -> None:
        """Start consuming messages from subscribed queues.

        Starts consumers for all queues with registered handlers.
        Also starts background task for delayed message processing.

        Example:
            >>> @queue.subscribe("tasks.email")
            >>> async def email_handler(message):
            ...     ...
            >>>
            >>> await queue.start_consuming()  # Blocks
        """
        if not self._redis:
            raise RuntimeError("Redis queue not connected")

        self._consuming = True

        logger.info(
            "redis_queue_consuming_start",
            queues=list(self._handlers.keys()),
        )

        # Start delayed message processor
        self._delayed_task = asyncio.create_task(self._process_delayed_messages())

        # Start consumer for each subscribed queue
        for queue_name in self._handlers.keys():
            task = asyncio.create_task(self._consume_queue(queue_name))
            self._consumer_tasks[queue_name] = task

        # Keep running
        try:
            while self._consuming:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("redis_queue_consuming_cancelled")
            await self.stop_consuming()

    async def _consume_queue(self, queue_name: str) -> None:
        """Consume messages from specific queue.

        Checks priority queues in order: URGENT, HIGH, NORMAL, LOW.

        Args:
            queue_name: Queue to consume from
        """
        if not self._redis:
            return

        # Priority order
        priority_levels = [
            MessagePriority.URGENT,
            MessagePriority.HIGH,
            MessagePriority.NORMAL,
            MessagePriority.LOW,
        ]

        # Build queue keys in priority order
        queue_keys = [f"queue:{queue_name}:p{p.value}" for p in priority_levels]

        logger.info("queue_consumer_started", queue=queue_name)

        while self._consuming:
            try:
                # BRPOP from multiple queues (priority order)
                result = await self._redis.brpop(queue_keys, timeout=1)

                if result:
                    queue_key, message_data = result

                    # Parse message
                    data = json.loads(message_data)
                    message = Message.from_dict(data)

                    # Process message
                    await self._handle_message(queue_name, message)

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error(
                    "consumer_error",
                    queue=queue_name,
                    error=str(e),
                )
                await asyncio.sleep(1)

        logger.info("queue_consumer_stopped", queue=queue_name)

    async def _process_delayed_messages(self) -> None:
        """Background task to process delayed messages.

        Checks sorted sets for messages ready to be processed
        and moves them to immediate queues.
        """
        if not self._redis:
            return

        logger.info("delayed_message_processor_started")

        while self._consuming:
            try:
                # Check all delayed queues
                for queue_name in self._handlers.keys():
                    delayed_key = f"delayed:{queue_name}"

                    # Get messages ready to be processed
                    now = datetime.now(UTC).timestamp()

                    # ZRANGEBYSCORE -inf now
                    messages = await self._redis.zrangebyscore(
                        delayed_key,
                        min=0,
                        max=now,
                        start=0,
                        num=10,  # Process 10 at a time
                    )

                    for message_data in messages:
                        # Parse message
                        data = json.loads(message_data)
                        message = Message.from_dict(data)

                        # Move to immediate queue
                        queue_key = f"queue:{queue_name}:p{message.priority.value}"
                        await self._redis.lpush(queue_key, message_data)

                        # Remove from delayed set
                        await self._redis.zrem(delayed_key, message_data)

                        logger.debug(
                            "delayed_message_moved",
                            queue=queue_name,
                            message_id=message.id,
                        )

                # Sleep before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error("delayed_processor_error", error=str(e))
                await asyncio.sleep(5)

        logger.info("delayed_message_processor_stopped")

    async def stop_consuming(self) -> None:
        """Stop consuming messages.

        Cancels all consumer tasks.

        Example:
            >>> await queue.stop_consuming()
        """
        self._consuming = False

        # Cancel delayed message task
        if self._delayed_task:
            self._delayed_task.cancel()
            try:
                await self._delayed_task
            except asyncio.CancelledError:
                pass

        # Cancel consumer tasks
        for queue_name, task in self._consumer_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._consumer_tasks.clear()

        logger.info("redis_queue_consuming_stopped")

    async def acknowledge(self, message: Message) -> None:
        """Acknowledge message processing.

        For Redis, messages are removed from queue on read,
        so acknowledgment is implicit.

        Args:
            message: Message to acknowledge

        Example:
            >>> await queue.acknowledge(message)
        """
        logger.debug("message_acknowledged", message_id=message.id)

    async def reject(
        self,
        message: Message,
        requeue: bool = False,
    ) -> None:
        """Reject message processing.

        Args:
            message: Message to reject
            requeue: Whether to requeue for retry

        Example:
            >>> await queue.reject(message, requeue=True)
        """
        if not self._redis:
            return

        if requeue:
            # Re-publish to queue
            queue_key = f"queue:{message.queue}:p{message.priority.value}"
            message_data = json.dumps(message.to_dict())
            await self._redis.lpush(queue_key, message_data)

            logger.debug(
                "message_requeued",
                message_id=message.id,
                retry_count=message.retry_count,
            )
        else:
            # Move to dead letter queue
            dlq_key = f"dlq:{message.queue}"
            message_data = json.dumps(message.to_dict())
            await self._redis.lpush(dlq_key, message_data)

            logger.debug(
                "message_moved_to_dlq",
                message_id=message.id,
            )


__all__ = [
    "RedisQueue",
]
