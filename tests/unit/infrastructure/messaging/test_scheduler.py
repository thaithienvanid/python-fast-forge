"""Comprehensive tests for the job scheduler implementation.

Tests cover ScheduledJob initialization, CRON scheduling, interval scheduling,
job execution, error handling, and the JobScheduler lifecycle management.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.messaging.scheduler import (
    JobScheduler,
    ScheduledJob,
)


# ─── ScheduledJob - Initialization ────────────────────────────────────────────


class TestScheduledJobInit:
    """Tests for ScheduledJob initialization."""

    def test_init_with_cron_schedule(self):
        async def task():
            pass

        job = ScheduledJob(name="test", func=task, schedule="0 0 * * *")
        assert job.name == "test"
        assert job.func is task
        assert job.schedule == "0 0 * * *"
        assert job.interval is None
        assert job.enabled is True
        assert job.error_count == 0
        assert job.last_run is None
        assert job.next_run is not None

    def test_init_with_interval(self):
        def task():
            pass

        job = ScheduledJob(name="health_check", func=task, interval=300)
        assert job.interval == 300
        assert job.schedule is None
        assert job.next_run is not None

    def test_init_requires_schedule_or_interval(self):
        with pytest.raises(ValueError, match="Either schedule or interval must be provided"):
            ScheduledJob(name="bad", func=lambda: None)

    def test_init_auto_generates_id(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        assert len(job.id) == 36
        assert job.id.count("-") == 4

    def test_init_unique_ids(self):
        job1 = ScheduledJob(name="j1", func=lambda: None, interval=60)
        job2 = ScheduledJob(name="j2", func=lambda: None, interval=60)
        assert job1.id != job2.id

    def test_init_disabled_job(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60, enabled=False)
        assert job.enabled is False

    def test_init_with_timezone(self):
        job = ScheduledJob(
            name="test",
            func=lambda: None,
            schedule="0 9 * * *",
            timezone="America/New_York",
        )
        assert job.timezone == "America/New_York"


# ─── ScheduledJob - next_run calculation ──────────────────────────────────────


class TestScheduledJobNextRun:
    """Tests for next_run calculation."""

    def test_cron_next_run_is_in_future(self):
        job = ScheduledJob(name="test", func=lambda: None, schedule="0 0 * * *")
        assert job.next_run is not None
        assert job.next_run > datetime.now(UTC)

    def test_interval_next_run_is_in_future(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=300)
        assert job.next_run is not None
        assert job.next_run > datetime.now(UTC)

    def test_interval_next_run_uses_interval_offset(self):
        before = datetime.now(UTC)
        job = ScheduledJob(name="test", func=lambda: None, interval=300)
        after = datetime.now(UTC)

        # next_run should be approximately now + 300 seconds
        expected_min = before + timedelta(seconds=299)
        expected_max = after + timedelta(seconds=301)
        assert expected_min <= job.next_run <= expected_max

    def test_interval_next_run_after_last_run(self):
        """After execution, next_run should be last_run + interval."""
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        last_run = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        job.last_run = last_run
        job._calculate_next_run()

        assert job.next_run == last_run + timedelta(seconds=60)


# ─── ScheduledJob - should_run ─────────────────────────────────────────────────


class TestScheduledJobShouldRun:
    """Tests for should_run method."""

    def test_should_run_when_next_run_in_past(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        job.next_run = datetime.now(UTC) - timedelta(seconds=1)
        assert job.should_run() is True

    def test_should_not_run_when_next_run_in_future(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        job.next_run = datetime.now(UTC) + timedelta(hours=1)
        assert job.should_run() is False

    def test_should_not_run_when_disabled(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60, enabled=False)
        job.next_run = datetime.now(UTC) - timedelta(seconds=1)
        assert job.should_run() is False

    def test_should_not_run_when_no_next_run(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        job.next_run = None
        assert job.should_run() is False


# ─── ScheduledJob - execute ────────────────────────────────────────────────────


class TestScheduledJobExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_execute_sync_function(self):
        called = []

        def sync_task():
            called.append(True)

        job = ScheduledJob(name="test", func=sync_task, interval=60)
        result = await job.execute()

        assert result is True
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_execute_async_function(self):
        called = []

        async def async_task():
            called.append(True)

        job = ScheduledJob(name="test", func=async_task, interval=60)
        result = await job.execute()

        assert result is True
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_execute_updates_last_run(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        assert job.last_run is None

        before = datetime.now(UTC)
        await job.execute()
        after = datetime.now(UTC)

        assert job.last_run is not None
        assert before <= job.last_run <= after

    @pytest.mark.asyncio
    async def test_execute_resets_error_count(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        job.error_count = 3

        await job.execute()

        assert job.error_count == 0

    @pytest.mark.asyncio
    async def test_execute_updates_next_run(self):
        job = ScheduledJob(name="test", func=lambda: None, interval=60)
        old_next_run = job.next_run

        await job.execute()

        assert job.next_run != old_next_run

    @pytest.mark.asyncio
    async def test_execute_failure_returns_false(self):
        def failing_task():
            raise ValueError("Task failed")

        job = ScheduledJob(name="test", func=failing_task, interval=60)
        result = await job.execute()

        assert result is False
        assert job.error_count == 1

    @pytest.mark.asyncio
    async def test_execute_failure_increments_error_count(self):
        def failing_task():
            raise ValueError("Task failed")

        job = ScheduledJob(name="test", func=failing_task, interval=60)

        for i in range(3):
            await job.execute()

        assert job.error_count == 3

    @pytest.mark.asyncio
    async def test_execute_disables_after_max_errors(self):
        def failing_task():
            raise ValueError("Task failed")

        job = ScheduledJob(name="test", func=failing_task, interval=60)

        for _ in range(5):
            await job.execute()

        assert job.enabled is False
        assert job.error_count == 5

    @pytest.mark.asyncio
    async def test_execute_stays_enabled_below_max_errors(self):
        def failing_task():
            raise ValueError("Task failed")

        job = ScheduledJob(name="test", func=failing_task, interval=60)

        for _ in range(4):
            await job.execute()

        assert job.enabled is True

    @pytest.mark.asyncio
    async def test_execute_with_async_failure(self):
        async def failing_async_task():
            raise RuntimeError("Async failure")

        job = ScheduledJob(name="test", func=failing_async_task, interval=60)
        result = await job.execute()

        assert result is False
        assert job.error_count == 1


# ─── JobScheduler - Initialization ────────────────────────────────────────────


class TestJobSchedulerInit:
    """Tests for JobScheduler initialization."""

    def test_default_init(self):
        scheduler = JobScheduler()
        assert scheduler._jobs == {}
        assert scheduler._running is False
        assert scheduler._task is None
        assert scheduler._queue is None
        assert scheduler._redis is None

    def test_init_with_queue(self):
        mock_queue = MagicMock()
        scheduler = JobScheduler(queue=mock_queue)
        assert scheduler._queue is mock_queue

    def test_init_with_redis(self):
        mock_redis = MagicMock()
        scheduler = JobScheduler(redis_client=mock_redis)
        assert scheduler._redis is mock_redis


# ─── JobScheduler - schedule decorator ───────────────────────────────────────


class TestJobSchedulerScheduleDecorator:
    """Tests for schedule() decorator."""

    def test_schedule_with_cron(self):
        scheduler = JobScheduler()

        @scheduler.schedule("0 0 * * *")
        async def daily_task():
            pass

        assert "daily_task" in scheduler._jobs

    def test_schedule_with_interval(self):
        scheduler = JobScheduler()

        @scheduler.schedule(interval=300)
        async def periodic_task():
            pass

        assert "periodic_task" in scheduler._jobs

    def test_schedule_with_custom_name(self):
        scheduler = JobScheduler()

        @scheduler.schedule("0 0 * * *", name="my_custom_job")
        async def task():
            pass

        assert "my_custom_job" in scheduler._jobs
        assert "task" not in scheduler._jobs

    def test_schedule_returns_original_function(self):
        scheduler = JobScheduler()

        async def original_task():
            return 42

        result = scheduler.schedule(interval=60)(original_task)
        assert result is original_task

    def test_schedule_disabled_job(self):
        scheduler = JobScheduler()

        @scheduler.schedule(interval=60, enabled=False)
        async def disabled_task():
            pass

        job = scheduler._jobs["disabled_task"]
        assert job.enabled is False

    def test_schedule_with_timezone(self):
        scheduler = JobScheduler()

        @scheduler.schedule("0 9 * * *", timezone="US/Eastern")
        async def morning_task():
            pass

        job = scheduler._jobs["morning_task"]
        assert job.timezone == "US/Eastern"


# ─── JobScheduler - add_job ────────────────────────────────────────────────────


class TestJobSchedulerAddJob:
    """Tests for add_job() method."""

    def test_add_job_cron(self):
        scheduler = JobScheduler()

        async def task():
            pass

        job = scheduler.add_job("backup", task, schedule="0 0 * * *")
        assert isinstance(job, ScheduledJob)
        assert "backup" in scheduler._jobs
        assert scheduler._jobs["backup"] is job

    def test_add_job_interval(self):
        scheduler = JobScheduler()

        async def task():
            pass

        job = scheduler.add_job("health", task, interval=60)
        assert job.interval == 60

    def test_add_job_with_extra_kwargs(self):
        scheduler = JobScheduler()

        async def task():
            pass

        job = scheduler.add_job("task", task, interval=60, enabled=False)
        assert job.enabled is False


# ─── JobScheduler - remove_job ────────────────────────────────────────────────


class TestJobSchedulerRemoveJob:
    """Tests for remove_job() method."""

    def test_remove_existing_job(self):
        scheduler = JobScheduler()
        scheduler.add_job("test", lambda: None, interval=60)
        assert "test" in scheduler._jobs

        scheduler.remove_job("test")
        assert "test" not in scheduler._jobs

    def test_remove_non_existing_job_no_error(self):
        scheduler = JobScheduler()
        # Should not raise
        scheduler.remove_job("nonexistent")


# ─── JobScheduler - get_job ────────────────────────────────────────────────────


class TestJobSchedulerGetJob:
    """Tests for get_job() method."""

    def test_get_existing_job(self):
        scheduler = JobScheduler()
        job = scheduler.add_job("test", lambda: None, interval=60)

        result = scheduler.get_job("test")
        assert result is job

    def test_get_nonexistent_job_returns_none(self):
        scheduler = JobScheduler()
        result = scheduler.get_job("nonexistent")
        assert result is None


# ─── JobScheduler - list_jobs ─────────────────────────────────────────────────


class TestJobSchedulerListJobs:
    """Tests for list_jobs() method."""

    def test_list_jobs_empty(self):
        scheduler = JobScheduler()
        result = scheduler.list_jobs()
        assert result == []

    def test_list_jobs_returns_all_jobs(self):
        scheduler = JobScheduler()
        scheduler.add_job("job1", lambda: None, interval=60)
        scheduler.add_job("job2", lambda: None, schedule="0 0 * * *")

        result = scheduler.list_jobs()
        assert len(result) == 2

    def test_list_jobs_contains_expected_fields(self):
        scheduler = JobScheduler()
        scheduler.add_job("backup", lambda: None, interval=3600)

        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        job_info = jobs[0]

        expected_fields = [
            "id",
            "name",
            "schedule",
            "interval",
            "enabled",
            "last_run",
            "next_run",
            "error_count",
        ]
        for field in expected_fields:
            assert field in job_info

    def test_list_jobs_last_run_none_initially(self):
        scheduler = JobScheduler()
        scheduler.add_job("test", lambda: None, interval=60)

        jobs = scheduler.list_jobs()
        assert jobs[0]["last_run"] is None

    def test_list_jobs_next_run_is_iso_string(self):
        scheduler = JobScheduler()
        scheduler.add_job("test", lambda: None, interval=60)

        jobs = scheduler.list_jobs()
        next_run_str = jobs[0]["next_run"]
        assert next_run_str is not None
        # Should be parseable as ISO datetime
        datetime.fromisoformat(next_run_str)


# ─── JobScheduler - start/stop ────────────────────────────────────────────────


class TestJobSchedulerStartStop:
    """Tests for start() and stop() methods."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        scheduler = JobScheduler()
        # Should not raise
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        scheduler = JobScheduler()
        scheduler._running = True
        scheduler._task = None

        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        scheduler = JobScheduler()

        # Start in background and immediately stop
        async def start_and_stop():
            task = asyncio.create_task(scheduler.start())
            await asyncio.sleep(0.01)
            await scheduler.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except TimeoutError:
                task.cancel()

        await start_and_stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_running_task(self):
        scheduler = JobScheduler()

        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        mock_task.__await__ = lambda self: (yield from asyncio.sleep(0).__await__())
        scheduler._task = asyncio.ensure_future(asyncio.sleep(100))
        scheduler._running = True

        await scheduler.stop()
        assert scheduler._running is False


# ─── JobScheduler - run_now ────────────────────────────────────────────────────


class TestJobSchedulerRunNow:
    """Tests for run_now() method."""

    @pytest.mark.asyncio
    async def test_run_now_existing_job(self):
        called = []

        async def task():
            called.append(True)

        scheduler = JobScheduler()
        scheduler.add_job("test", task, interval=60)

        result = await scheduler.run_now("test")
        assert result is True
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_run_now_nonexistent_job(self):
        scheduler = JobScheduler()
        result = await scheduler.run_now("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_run_now_failing_job_returns_false(self):
        async def failing_task():
            raise RuntimeError("Failed")

        scheduler = JobScheduler()
        scheduler.add_job("failing", failing_task, interval=60)

        result = await scheduler.run_now("failing")
        assert result is False


# ─── JobScheduler - _run_scheduler ────────────────────────────────────────────


class TestJobSchedulerRunScheduler:
    """Tests for the internal _run_scheduler method."""

    @pytest.mark.asyncio
    async def test_run_scheduler_executes_due_jobs(self):
        executed = []

        async def task():
            executed.append(True)

        scheduler = JobScheduler()
        job = scheduler.add_job("test", task, interval=60)

        # Set next_run to past to trigger immediate execution
        job.next_run = datetime.now(UTC) - timedelta(seconds=1)

        # Run scheduler for one iteration
        scheduler._running = True

        async def one_iteration():
            original_sleep = asyncio.sleep

            call_count = 0

            async def mock_sleep(seconds):
                nonlocal call_count
                call_count += 1
                scheduler._running = False

            with patch("src.infrastructure.messaging.scheduler.asyncio.sleep", mock_sleep):
                await scheduler._run_scheduler()

        await one_iteration()

        # Job should have been executed (as a task)
        await asyncio.sleep(0.01)  # Let tasks complete
        assert len(executed) >= 1

    @pytest.mark.asyncio
    async def test_run_scheduler_with_redis_lock(self):
        """When Redis is configured, should acquire lock before executing."""
        executed = []

        async def task():
            executed.append(True)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)  # Lock acquired

        scheduler = JobScheduler(redis_client=mock_redis)
        job = scheduler.add_job("test", task, interval=60)
        job.next_run = datetime.now(UTC) - timedelta(seconds=1)
        scheduler._running = True

        async def mock_sleep(seconds):
            scheduler._running = False

        with patch("src.infrastructure.messaging.scheduler.asyncio.sleep", mock_sleep):
            await scheduler._run_scheduler()

        # Lock should have been attempted
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scheduler_skips_locked_jobs(self):
        """Jobs where lock acquisition fails should be skipped."""
        executed = []

        async def task():
            executed.append(True)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=False)  # Lock NOT acquired

        scheduler = JobScheduler(redis_client=mock_redis)
        job = scheduler.add_job("test", task, interval=60)
        job.next_run = datetime.now(UTC) - timedelta(seconds=1)
        scheduler._running = True

        async def mock_sleep(seconds):
            scheduler._running = False

        with patch("src.infrastructure.messaging.scheduler.asyncio.sleep", mock_sleep):
            await scheduler._run_scheduler()

        # Job should NOT have been executed (lock not acquired)
        await asyncio.sleep(0.01)
        assert len(executed) == 0

    @pytest.mark.asyncio
    async def test_run_scheduler_handles_exception_gracefully(self):
        """Exceptions in the scheduler loop should be caught and continue."""
        scheduler = JobScheduler()

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scheduler._running = False

        # Add a job that will raise during should_run check
        mock_job = MagicMock()
        mock_job.should_run = MagicMock(side_effect=[RuntimeError("scheduler error"), False])
        scheduler._jobs["bad_job"] = mock_job
        scheduler._running = True

        with patch("src.infrastructure.messaging.scheduler.asyncio.sleep", mock_sleep):
            await scheduler._run_scheduler()

        # Scheduler should continue running despite exception
        assert call_count >= 1
