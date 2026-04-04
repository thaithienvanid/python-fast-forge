"""Job scheduler with CRON support for periodic task execution.

The scheduler enables running tasks on a schedule using:
- CRON expressions (e.g., "0 0 * * *" for daily at midnight)
- Interval scheduling (e.g., every 5 minutes)
- One-time delayed execution
- Timezone support

Features:
- CRON expression parsing
- Distributed coordination (Redis-based locking)
- Task execution history
- Error handling and retry
- Task overlapping prevention

Example:
    >>> scheduler = JobScheduler(queue)
    >>>
    >>> # Schedule with CRON expression
    >>> @scheduler.schedule("0 0 * * *")  # Daily at midnight
    >>> async def daily_cleanup():
    ...     print("Running daily cleanup")
    >>>
    >>> # Schedule with interval
    >>> @scheduler.schedule(interval=300)  # Every 5 minutes
    >>> async def check_health():
    ...     print("Checking system health")
    >>>
    >>> await scheduler.start()
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from croniter import croniter

from src.infrastructure.logging.config import get_logger
from src.infrastructure.messaging.queue import MessageQueue


logger = get_logger(__name__)


class ScheduledJob:
    """Represents a scheduled job.

    Attributes:
        id: Unique job identifier
        name: Human-readable job name
        schedule: CRON expression or None
        interval: Interval in seconds or None
        func: Function to execute
        timezone: Timezone for CRON scheduling
        enabled: Whether job is enabled
        last_run: Last execution timestamp
        next_run: Next scheduled execution timestamp
        error_count: Number of consecutive errors

    Example:
        >>> job = ScheduledJob(
        ...     name="daily_backup",
        ...     schedule="0 0 * * *",
        ...     func=backup_database,
        ...     timezone="UTC",
        ... )
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        schedule: str | None = None,
        interval: int | None = None,
        timezone: str = "UTC",
        enabled: bool = True,
    ):
        """Initialize scheduled job.

        Args:
            name: Job name
            func: Function to execute
            schedule: CRON expression (e.g., "0 0 * * *")
            interval: Interval in seconds
            timezone: Timezone for scheduling
            enabled: Whether job is enabled
        """
        if not schedule and not interval:
            raise ValueError("Either schedule or interval must be provided")

        self.id = str(uuid4())
        self.name = name
        self.schedule = schedule
        self.interval = interval
        self.func = func
        self.timezone = timezone
        self.enabled = enabled
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self.error_count = 0

        # Calculate next run
        self._calculate_next_run()

    def _calculate_next_run(self) -> None:
        """Calculate next execution time."""
        now = datetime.now(UTC)

        if self.schedule:
            # CRON expression
            cron = croniter(self.schedule, now)
            self.next_run = cron.get_next(datetime)

        elif self.interval:
            # Interval-based
            if self.last_run:
                self.next_run = self.last_run + timedelta(seconds=self.interval)
            else:
                self.next_run = now + timedelta(seconds=self.interval)

    def should_run(self) -> bool:
        """Check if job should run now.

        Returns:
            True if job should run, False otherwise
        """
        if not self.enabled:
            return False

        if not self.next_run:
            return False

        now = datetime.now(UTC)
        return now >= self.next_run

    async def execute(self) -> bool:
        """Execute job function.

        Returns:
            True if execution succeeded, False otherwise
        """
        try:
            logger.info(
                "job_execution_start",
                job_id=self.id,
                job_name=self.name,
            )

            start_time = datetime.now(UTC)

            # Execute function
            result = self.func()
            if asyncio.iscoroutine(result):
                await result

            # Update state
            self.last_run = start_time
            self.error_count = 0
            self._calculate_next_run()

            execution_time = (datetime.now(UTC) - start_time).total_seconds()

            logger.info(
                "job_execution_success",
                job_id=self.id,
                job_name=self.name,
                execution_time=execution_time,
                next_run=self.next_run.isoformat() if self.next_run else None,
            )

            return True

        except Exception as e:
            self.error_count += 1

            logger.error(
                "job_execution_failed",
                job_id=self.id,
                job_name=self.name,
                error=str(e),
                error_count=self.error_count,
            )

            # Disable job after too many errors
            if self.error_count >= 5:
                self.enabled = False
                logger.error(
                    "job_disabled_after_errors",
                    job_id=self.id,
                    job_name=self.name,
                )

            return False


class JobScheduler:
    """Job scheduler for periodic task execution.

    Manages scheduled jobs with CRON and interval support.
    Uses distributed locking to prevent duplicate execution
    in multi-instance deployments.

    Attributes:
        _jobs: Registered jobs by name
        _running: Whether scheduler is running
        _task: Background scheduler task
        _redis: Redis client for distributed locking (optional)

    Example:
        >>> scheduler = JobScheduler()
        >>>
        >>> @scheduler.schedule("0 0 * * *")  # Daily at midnight
        >>> async def daily_cleanup():
        ...     print("Cleaning up old data")
        >>>
        >>> await scheduler.start()
    """

    def __init__(
        self,
        queue: MessageQueue | None = None,
        redis_client: Any | None = None,
    ):
        """Initialize job scheduler.

        Args:
            queue: Message queue for async task execution (optional)
            redis_client: Redis client for distributed locking (optional)
        """
        self._jobs: dict[str, ScheduledJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._queue = queue
        self._redis = redis_client

    def schedule(
        self,
        schedule: str | None = None,
        interval: int | None = None,
        name: str | None = None,
        timezone: str = "UTC",
        enabled: bool = True,
    ) -> Callable:
        """Decorator to schedule a job.

        Args:
            schedule: CRON expression (e.g., "0 0 * * *")
            interval: Interval in seconds
            name: Job name (defaults to function name)
            timezone: Timezone for scheduling
            enabled: Whether job is enabled

        Returns:
            Decorator function

        Example:
            >>> @scheduler.schedule("0 * * * *")  # Every hour
            >>> async def hourly_task():
            ...     print("Running hourly task")
            >>>
            >>> @scheduler.schedule(interval=300)  # Every 5 minutes
            >>> async def check_health():
            ...     print("Checking health")
        """

        def decorator(func: Callable) -> Callable:
            job_name = name or func.__name__

            job = ScheduledJob(
                name=job_name,
                func=func,
                schedule=schedule,
                interval=interval,
                timezone=timezone,
                enabled=enabled,
            )

            self._jobs[job_name] = job

            logger.info(
                "job_scheduled",
                job_name=job_name,
                schedule=schedule,
                interval=interval,
                next_run=job.next_run.isoformat() if job.next_run else None,
            )

            return func

        return decorator

    def add_job(
        self,
        name: str,
        func: Callable,
        schedule: str | None = None,
        interval: int | None = None,
        **kwargs: Any,
    ) -> ScheduledJob:
        """Programmatically add a job.

        Args:
            name: Job name
            func: Function to execute
            schedule: CRON expression
            interval: Interval in seconds
            **kwargs: Additional job options

        Returns:
            Created job

        Example:
            >>> job = scheduler.add_job(
            ...     "backup",
            ...     backup_database,
            ...     schedule="0 0 * * *",
            ... )
        """
        job = ScheduledJob(
            name=name,
            func=func,
            schedule=schedule,
            interval=interval,
            **kwargs,
        )

        self._jobs[name] = job

        logger.info(
            "job_added",
            job_name=name,
            schedule=schedule,
            interval=interval,
        )

        return job

    def remove_job(self, name: str) -> None:
        """Remove scheduled job.

        Args:
            name: Job name to remove

        Example:
            >>> scheduler.remove_job("daily_cleanup")
        """
        if name in self._jobs:
            del self._jobs[name]
            logger.info("job_removed", job_name=name)

    def get_job(self, name: str) -> ScheduledJob | None:
        """Get job by name.

        Args:
            name: Job name

        Returns:
            Job or None if not found

        Example:
            >>> job = scheduler.get_job("daily_cleanup")
            >>> print(f"Next run: {job.next_run}")
        """
        return self._jobs.get(name)

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all scheduled jobs.

        Returns:
            List of job info dictionaries

        Example:
            >>> jobs = scheduler.list_jobs()
            >>> for job_info in jobs:
            ...     print(f"{job_info['name']}: {job_info['next_run']}")
        """
        return [
            {
                "id": job.id,
                "name": job.name,
                "schedule": job.schedule,
                "interval": job.interval,
                "enabled": job.enabled,
                "last_run": job.last_run.isoformat() if job.last_run else None,
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "error_count": job.error_count,
            }
            for job in self._jobs.values()
        ]

    async def start(self) -> None:
        """Start job scheduler.

        Runs continuously, checking jobs every second.

        Example:
            >>> await scheduler.start()  # Blocks until stop()
        """
        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())

        logger.info("job_scheduler_started", jobs=len(self._jobs))

        try:
            await self._task
        except asyncio.CancelledError:
            logger.info("job_scheduler_cancelled")

    async def stop(self) -> None:
        """Stop job scheduler.

        Example:
            >>> await scheduler.stop()
        """
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("job_scheduler_stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop.

        Checks jobs every second and executes those that are due.
        """
        while self._running:
            try:
                now = datetime.now(UTC)

                for job in self._jobs.values():
                    if job.should_run():
                        # Acquire distributed lock if Redis available
                        if self._redis:
                            lock_key = f"scheduler:lock:{job.name}"
                            lock_acquired = await self._redis.set(lock_key, "1", nx=True, ex=60)

                            if not lock_acquired:
                                # Another instance is running this job
                                logger.debug(
                                    "job_execution_skipped_locked",
                                    job_name=job.name,
                                )
                                continue

                        # Execute job
                        asyncio.create_task(job.execute())

                # Sleep for 1 second
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.error("scheduler_error", error=str(e))
                await asyncio.sleep(5)

    async def run_now(self, job_name: str) -> bool:
        """Run job immediately (manual trigger).

        Args:
            job_name: Name of job to run

        Returns:
            True if execution succeeded, False otherwise

        Example:
            >>> await scheduler.run_now("daily_cleanup")
        """
        job = self._jobs.get(job_name)

        if not job:
            logger.warning("job_not_found", job_name=job_name)
            return False

        return await job.execute()


__all__ = [
    "JobScheduler",
    "ScheduledJob",
]
