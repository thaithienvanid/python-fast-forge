"""Message queue and job scheduling infrastructure.

This package provides message queue abstractions and job scheduling
capabilities for asynchronous task processing.

Features:
- Message queues (RabbitMQ, Redis, SQS)
- Priority-based message processing
- Delayed message delivery
- Job scheduling with CRON expressions
- Distributed coordination
- Retry logic and dead letter queues

Example:
    >>> from src.infrastructure.messaging import MessageQueue, JobScheduler
    >>>
    >>> # Message Queue
    >>> queue = MessageQueue.from_url("amqp://localhost:5672")
    >>> await queue.connect()
    >>>
    >>> @queue.subscribe("tasks.send_email")
    >>> async def send_email_task(message):
    ...     await send_email(**message.body)
    >>>
    >>> await queue.publish("tasks.send_email", {"to": "user@example.com"})
    >>> await queue.start_consuming()
    >>>
    >>> # Job Scheduler
    >>> scheduler = JobScheduler()
    >>>
    >>> @scheduler.schedule("0 0 * * *")  # Daily at midnight
    >>> async def daily_backup():
    ...     await backup_database()
    >>>
    >>> await scheduler.start()
"""

from src.infrastructure.messaging.queue import (
    Message,
    MessagePriority,
    MessageQueue,
)
from src.infrastructure.messaging.scheduler import JobScheduler, ScheduledJob

__all__ = [
    # Message Queue
    "MessageQueue",
    "Message",
    "MessagePriority",
    # Job Scheduler
    "JobScheduler",
    "ScheduledJob",
]
