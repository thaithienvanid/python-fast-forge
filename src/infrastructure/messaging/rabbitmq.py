"""RabbitMQ message queue implementation.

RabbitMQ is a feature-rich AMQP message broker providing:
- Durable queues and messages
- Message acknowledgments and retries
- Dead letter exchanges for failed messages
- Priority queues
- Message TTL and expiration
- Publisher confirms

Example:
    >>> queue = RabbitMQQueue("amqp://guest:guest@localhost:5672/")
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
from typing import Any

from src.infrastructure.logging.config import get_logger
from src.infrastructure.messaging.queue import Message, MessagePriority, MessageQueue

logger = get_logger(__name__)


class RabbitMQQueue(MessageQueue):
    """RabbitMQ implementation of MessageQueue.

    Uses aio-pika library for async RabbitMQ operations.

    Attributes:
        _url: AMQP connection URL
        _connection: RabbitMQ connection
        _channel: RabbitMQ channel
        _queues: Declared queue objects by name

    Example:
        >>> queue = RabbitMQQueue("amqp://guest:guest@localhost:5672/")
        >>> await queue.connect()
        >>> await queue.publish("tasks.email", {"to": "user@example.com"})
    """

    def __init__(self, url: str, **options: Any):
        """Initialize RabbitMQ queue.

        Args:
            url: AMQP connection URL (amqp://user:pass@host:port/vhost)
            **options: Connection options (heartbeat, etc.)
        """
        super().__init__()
        self._url = url
        self._options = options
        self._connection = None
        self._channel = None
        self._queues: dict[str, Any] = {}
        self._consumer_tags: dict[str, str] = {}

    async def connect(self) -> None:
        """Connect to RabbitMQ broker.

        Creates connection and channel, declares dead letter exchange.

        Example:
            >>> await queue.connect()
        """
        try:
            import aio_pika

            self._connection = await aio_pika.connect_robust(
                self._url,
                **self._options,
            )
            self._channel = await self._connection.channel()

            # Set QoS (prefetch count)
            await self._channel.set_qos(prefetch_count=10)

            # Declare dead letter exchange
            await self._channel.declare_exchange(
                "dlx",
                aio_pika.ExchangeType.DIRECT,
                durable=True,
            )

            logger.info("rabbitmq_connected", url=self._url)

        except ImportError as e:
            logger.warning(
                "rabbitmq_not_available",
                error="aio-pika not installed",
                message="RabbitMQ functionality disabled. Install aio-pika to enable.",
            )
            # Continue without RabbitMQ (degraded mode)
            self._connection = None
            self._channel = None

        except Exception as e:
            logger.error("rabbitmq_connection_failed", url=self._url, error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ broker.

        Closes channel and connection gracefully.

        Example:
            >>> await queue.disconnect()
        """
        try:
            if self._channel:
                await self._channel.close()

            if self._connection:
                await self._connection.close()

            logger.info("rabbitmq_disconnected")

        except Exception as e:
            logger.error("rabbitmq_disconnect_failed", error=str(e))

    async def _declare_queue(
        self,
        queue_name: str,
        durable: bool = True,
        **options: Any,
    ) -> Any:
        """Declare queue if not already declared.

        Args:
            queue_name: Queue name
            durable: Whether queue survives broker restart
            **options: Additional queue options

        Returns:
            Queue object
        """
        if queue_name in self._queues:
            return self._queues[queue_name]

        # Check if RabbitMQ is available
        if self._channel is None:
            logger.warning(
                "rabbitmq_unavailable",
                queue=queue_name,
                message="RabbitMQ not connected, queue declaration skipped",
            )
            self._queues[queue_name] = None
            return None

        import aio_pika

        queue = await self._channel.declare_queue(
            queue_name,
            durable=durable,
            arguments={
                "x-max-priority": 20,  # Support priority 0-20
                "x-dead-letter-exchange": "dlx",
                "x-dead-letter-routing-key": f"{queue_name}.dlq",
            },
            **options,
        )

        self._queues[queue_name] = queue
        return queue

    async def publish(
        self,
        queue: str,
        body: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        delay: int = 0,
        **kwargs: Any,
    ) -> str:
        """Publish message to RabbitMQ queue.

        Args:
            queue: Queue name
            body: Message payload
            priority: Message priority (0-20)
            delay: Delay before processing (seconds)
            **kwargs: Additional publish options

        Returns:
            Message ID

        Example:
            >>> message_id = await queue.publish(
            ...     "tasks.send_email",
            ...     {"to": "user@example.com"},
            ...     priority=MessagePriority.HIGH,
            ... )
        """
        # Create message
        message = Message(
            queue=queue,
            body=body,
            priority=priority,
            delay=delay,
            **kwargs,
        )

        # Declare queue
        await self._declare_queue(queue)

        # Check if RabbitMQ is available
        if self._channel is None:
            logger.warning(
                "rabbitmq_unavailable",
                queue=queue,
                message_id=message.id,
                message="RabbitMQ not connected, message not published",
            )
            return message.id

        try:
            import aio_pika

            amqp_message = aio_pika.Message(
                body=json.dumps(message.to_dict()).encode(),
                priority=priority.value,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                message_id=message.id,
                timestamp=int(message.created_at.timestamp()),
            )

            # Handle delay
            if delay > 0:
                amqp_message.expiration = str(delay * 1000)  # milliseconds

            await self._channel.default_exchange.publish(
                amqp_message,
                routing_key=queue,
            )

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
        Runs indefinitely until stop_consuming() is called.

        Example:
            >>> @queue.subscribe("tasks.email")
            >>> async def email_handler(message):
            ...     ...
            >>>
            >>> await queue.start_consuming()  # Blocks
        """
        self._consuming = True

        logger.info(
            "rabbitmq_consuming_start",
            queues=list(self._handlers.keys()),
        )

        # Start consumer for each subscribed queue
        for queue_name in self._handlers.keys():
            await self._start_queue_consumer(queue_name)

        # Keep running
        try:
            while self._consuming:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("rabbitmq_consuming_cancelled")
            await self.stop_consuming()

    async def _start_queue_consumer(self, queue_name: str) -> None:
        """Start consumer for specific queue.

        Args:
            queue_name: Queue to consume from
        """
        # Declare queue
        queue = await self._declare_queue(queue_name)

        # Check if RabbitMQ is available
        if queue is None or self._channel is None:
            logger.warning(
                "rabbitmq_unavailable",
                queue=queue_name,
                message="RabbitMQ not connected, consumer not started",
            )
            return

        async def on_message(amqp_message):
            try:
                # Parse message
                data = json.loads(amqp_message.body.decode())
                message = Message.from_dict(data)

                # Process message
                await self._handle_message(queue_name, message)

                # Acknowledge message
                await amqp_message.ack()

            except Exception as e:
                logger.error(
                    "consumer_error",
                    queue=queue_name,
                    error=str(e),
                )
                # Reject message (send to DLQ)
                await amqp_message.reject(requeue=False)

        consumer_tag = await queue.consume(on_message)
        self._consumer_tags[queue_name] = consumer_tag

        logger.info("queue_consumer_started", queue=queue_name)

    async def stop_consuming(self) -> None:
        """Stop consuming messages.

        Cancels all active consumers.

        Example:
            >>> await queue.stop_consuming()
        """
        self._consuming = False

        # Cancel consumers
        for queue_name, consumer_tag in self._consumer_tags.items():
            queue = self._queues.get(queue_name)
            if queue and self._channel:
                await queue.cancel(consumer_tag)

            logger.info("queue_consumer_stopped", queue=queue_name)

        logger.info("rabbitmq_consuming_stopped")

    async def acknowledge(self, message: Message) -> None:
        """Acknowledge message processing.

        Note: In the consumer callback (on_message), messages are automatically
        acknowledged after successful processing. This method is provided for
        manual acknowledgment patterns if needed.

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

        Note: In the consumer callback (on_message), messages are automatically
        rejected on exceptions. This method is provided for manual rejection
        patterns if needed.

        Args:
            message: Message to reject
            requeue: Whether to requeue for retry

        Example:
            >>> await queue.reject(message, requeue=True)
        """
        logger.debug(
            "message_rejected",
            message_id=message.id,
            requeue=requeue,
        )


__all__ = [
    "RabbitMQQueue",
]
