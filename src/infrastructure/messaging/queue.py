"""Message queue abstraction for asynchronous task processing.

Message queues enable decoupling producers from consumers, allowing:
- Asynchronous task processing
- Load leveling and buffering
- Horizontal scaling of workers
- Fault tolerance and retry logic
- Priority-based processing

Supported Backends:
- RabbitMQ: Feature-rich AMQP message broker
- Redis: Fast in-memory queue with pub/sub
- Amazon SQS: Managed cloud queue service

Example:
    >>> # Producer
    >>> queue = MessageQueue.from_url("amqp://localhost:5672")
    >>> await queue.publish(
    ...     "tasks.send_email",
    ...     {"to": "user@example.com", "subject": "Hello"},
    ... )
    >>>
    >>> # Consumer
    >>> @queue.subscribe("tasks.send_email")
    >>> async def send_email_task(message: Message):
    ...     await send_email(**message.body)
    >>>
    >>> await queue.start_consuming()
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)


class MessagePriority(int, Enum):
    """Message priority levels.

    Higher priority messages are processed first.

    Attributes:
        LOW: Low priority (batch jobs, cleanup)
        NORMAL: Normal priority (default)
        HIGH: High priority (user-facing tasks)
        URGENT: Urgent priority (alerts, critical notifications)
    """

    LOW = 0
    NORMAL = 5
    HIGH = 10
    URGENT = 20


@dataclass
class Message:
    """Message structure for queue operations.

    Attributes:
        id: Unique message identifier
        queue: Queue name (e.g., "tasks.send_email")
        body: Message payload (JSON-serializable dict)
        priority: Message priority
        created_at: Message creation timestamp
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts
        delay: Delay before processing (seconds)
        timeout: Processing timeout (seconds)
        metadata: Custom metadata

    Example:
        >>> message = Message(
        ...     queue="tasks.send_email",
        ...     body={"to": "user@example.com", "subject": "Hello"},
        ...     priority=MessagePriority.HIGH,
        ...     max_retries=3,
        ... )
    """

    queue: str
    body: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    retry_count: int = 0
    max_retries: int = 3
    delay: int = 0
    timeout: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            "id": self.id,
            "queue": self.queue,
            "body": self.body,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "delay": self.delay,
            "timeout": self.timeout,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            queue=data["queue"],
            body=data["body"],
            priority=MessagePriority(data.get("priority", MessagePriority.NORMAL.value)),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(UTC),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            delay=data.get("delay", 0),
            timeout=data.get("timeout", 300),
            metadata=data.get("metadata", {}),
        )


class MessageQueue(ABC):
    """Abstract base class for message queue implementations.

    Provides a consistent interface across different queue backends
    (RabbitMQ, Redis, SQS, etc.).

    Methods:
        connect: Connect to message broker
        disconnect: Disconnect from broker
        publish: Publish message to queue
        subscribe: Subscribe handler to queue
        start_consuming: Start consuming messages
        stop_consuming: Stop consuming messages
        acknowledge: Acknowledge message processing
        reject: Reject message (with optional requeue)
    """

    def __init__(self):
        """Initialize message queue."""
        self._handlers: dict[str, list[Callable]] = {}
        self._consuming = False

    @abstractmethod
    async def connect(self) -> None:
        """Connect to message broker.

        Example:
            >>> await queue.connect()
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from message broker.

        Example:
            >>> await queue.disconnect()
        """

    @abstractmethod
    async def publish(
        self,
        queue: str,
        body: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        delay: int = 0,
        **kwargs: Any,
    ) -> str:
        """Publish message to queue.

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
            ...     {"to": "user@example.com", "subject": "Hello"},
            ...     priority=MessagePriority.HIGH,
            ... )
        """

    def subscribe(
        self,
        queue: str,
        **options: Any,
    ) -> Callable:
        """Decorator to subscribe handler to queue.

        Args:
            queue: Queue name to subscribe to
            **options: Subscription options (prefetch_count, etc.)

        Returns:
            Decorator function

        Example:
            >>> @queue.subscribe("tasks.send_email")
            >>> async def send_email_handler(message: Message):
            ...     await send_email(**message.body)
        """

        def decorator(handler: Callable) -> Callable:
            if queue not in self._handlers:
                self._handlers[queue] = []
            self._handlers[queue].append(handler)
            logger.info("handler_subscribed", queue=queue, handler=handler.__name__)
            return handler

        return decorator

    @abstractmethod
    async def start_consuming(self) -> None:
        """Start consuming messages from subscribed queues.

        This method runs indefinitely, processing messages as they arrive.

        Example:
            >>> await queue.start_consuming()  # Blocks until stop_consuming()
        """

    @abstractmethod
    async def stop_consuming(self) -> None:
        """Stop consuming messages.

        Example:
            >>> await queue.stop_consuming()
        """

    @abstractmethod
    async def acknowledge(self, message: Message) -> None:
        """Acknowledge successful message processing.

        Args:
            message: Message to acknowledge

        Example:
            >>> await queue.acknowledge(message)
        """

    @abstractmethod
    async def reject(
        self,
        message: Message,
        requeue: bool = False,
    ) -> None:
        """Reject message processing.

        Args:
            message: Message to reject
            requeue: Whether to requeue message for retry

        Example:
            >>> await queue.reject(message, requeue=True)
        """

    async def _handle_message(
        self,
        queue: str,
        message: Message,
    ) -> None:
        """Internal method to handle message processing.

        Args:
            queue: Queue name
            message: Message to process
        """
        handlers = self._handlers.get(queue, [])

        if not handlers:
            logger.warning("no_handlers_for_queue", queue=queue)
            await self.acknowledge(message)
            return

        for handler in handlers:
            try:
                # Call handler
                result = handler(message)
                if asyncio.iscoroutine(result):
                    await result

                # Acknowledge success
                await self.acknowledge(message)

                logger.info(
                    "message_processed",
                    queue=queue,
                    message_id=message.id,
                    handler=handler.__name__,
                )

            except Exception as e:
                logger.error(
                    "message_processing_failed",
                    queue=queue,
                    message_id=message.id,
                    error=str(e),
                    retry_count=message.retry_count,
                )

                # Retry logic
                if message.retry_count < message.max_retries:
                    message.retry_count += 1
                    await self.reject(message, requeue=True)
                else:
                    # Move to dead letter queue
                    logger.error(
                        "message_max_retries_exceeded",
                        queue=queue,
                        message_id=message.id,
                    )
                    await self.reject(message, requeue=False)

    @staticmethod
    def from_url(url: str, **kwargs: Any) -> "MessageQueue":
        """Create message queue from connection URL.

        Args:
            url: Connection URL (amqp://, redis://, sqs://)
            **kwargs: Additional connection options

        Returns:
            MessageQueue implementation for the URL scheme

        Example:
            >>> # RabbitMQ
            >>> queue = MessageQueue.from_url("amqp://localhost:5672")
            >>>
            >>> # Redis
            >>> queue = MessageQueue.from_url("redis://localhost:6379/0")
            >>>
            >>> # Amazon SQS
            >>> queue = MessageQueue.from_url("sqs://us-east-1")
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        scheme = parsed.scheme

        if scheme in ("amqp", "amqps"):
            from src.infrastructure.messaging.rabbitmq import RabbitMQQueue

            return RabbitMQQueue(url, **kwargs)

        if scheme == "redis":
            from src.infrastructure.messaging.redis_queue import RedisQueue

            return RedisQueue(url, **kwargs)

        if scheme == "sqs":
            raise NotImplementedError("SQS queue not yet implemented")

        raise ValueError(f"Unsupported queue URL scheme: {scheme}")


__all__ = [
    "Message",
    "MessagePriority",
    "MessageQueue",
]
