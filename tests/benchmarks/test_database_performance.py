"""Database performance benchmarks.

This module contains performance benchmarks for database operations
to ensure they meet performance targets.

Target Metrics:
- Single row queries: < 10ms p95
- Bulk queries: < 50ms p95
- Inserts: < 20ms p95
- Updates: < 15ms p95
"""

import asyncio
import time
from statistics import median, quantiles

import pytest

from src.domain.models.user import User
from src.infrastructure.repositories.user_repository import UserRepository


@pytest.mark.benchmark
@pytest.mark.asyncio
class TestDatabaseReadPerformance:
    """Benchmarks for database read operations."""

    async def test_get_by_id_performance(self, db_session) -> None:
        """Benchmark get_by_id query performance.

        Single row lookups by primary key should be very fast (< 10ms).
        """
        repository = UserRepository(db_session)

        # Create test user
        user = User(
            email="perf_test@example.com",
            username="perf_test",
            full_name="Performance Test",
        )
        user = await repository.create(user)
        await db_session.commit()
        user_id = user.id

        # Benchmark get_by_id
        iterations = 100
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await repository.get_by_id(user_id)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

            assert result is not None
            assert result.id == user_id

        # Calculate percentiles
        p50 = median(times)
        p95, p99 = quantiles(times, n=100)[94], quantiles(times, n=100)[98]


        # Assert performance targets
        assert p50 < 5, f"p50 should be < 5ms, got {p50:.2f}ms"
        assert p95 < 10, f"p95 should be < 10ms, got {p95:.2f}ms"
        assert p99 < 20, f"p99 should be < 20ms, got {p99:.2f}ms"

    async def test_get_by_email_performance(self, db_session) -> None:
        """Benchmark get_by_email query performance.

        Email lookups should be fast due to unique index (< 15ms p95).
        """
        repository = UserRepository(db_session)

        # Create test user
        user = User(
            email="email_perf@example.com",
            username="email_perf",
            full_name="Email Performance",
        )
        user = await repository.create(user)
        await db_session.commit()
        email = user.email

        # Benchmark get_by_email
        iterations = 100
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = await repository.get_by_email(email)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

            assert result is not None
            assert result.email == email

        # Calculate percentiles
        p50 = median(times)
        p95 = quantiles(times, n=100)[94]


        assert p50 < 8, f"p50 should be < 8ms, got {p50:.2f}ms"
        assert p95 < 15, f"p95 should be < 15ms, got {p95:.2f}ms"

    async def test_bulk_find_by_emails_performance(self, db_session) -> None:
        """Benchmark bulk find_by_emails query performance.

        Bulk queries should be efficient even with many emails (< 50ms p95).
        """
        repository = UserRepository(db_session)

        # Create test users
        test_count = 50
        emails = []
        for i in range(test_count):
            user = User(
                email=f"bulk{i}@example.com",
                username=f"bulk{i}",
                full_name=f"Bulk User {i}",
            )
            await repository.create(user)
            emails.append(user.email)

        await db_session.commit()

        # Benchmark find_by_emails with different batch sizes
        batch_sizes = [10, 25, 50]

        for batch_size in batch_sizes:
            times = []
            iterations = 20
            email_batch = emails[:batch_size]

            for _ in range(iterations):
                start = time.perf_counter()
                results = await repository.find_by_emails(email_batch)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)

                assert len(results) == batch_size

            median(times)
            p95 = quantiles(times, n=100)[94] if len(times) >= 20 else max(times)


            # Performance should scale reasonably with batch size
            expected_p95 = 20 + (batch_size / 10) * 5  # ~20ms + 5ms per 10 items
            assert p95 < expected_p95, (
                f"p95 should be < {expected_p95:.0f}ms for batch size {batch_size}, got {p95:.2f}ms"
            )


@pytest.mark.benchmark
@pytest.mark.asyncio
class TestDatabaseWritePerformance:
    """Benchmarks for database write operations."""

    async def test_create_user_performance(self, db_session) -> None:
        """Benchmark user creation performance.

        Single inserts should be fast (< 20ms p95).
        """
        repository = UserRepository(db_session)

        iterations = 50
        times = []

        for i in range(iterations):
            user = User(
                email=f"create_perf{i}_{time.time()}@example.com",
                username=f"create_perf{i}_{int(time.time())}",
                full_name=f"Create Perf {i}",
            )

            start = time.perf_counter()
            await repository.create(user)
            await db_session.flush()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        # Calculate percentiles
        p50 = median(times)
        p95 = quantiles(times, n=100)[94] if len(times) >= 20 else max(times)


        assert p50 < 10, f"p50 should be < 10ms, got {p50:.2f}ms"
        assert p95 < 20, f"p95 should be < 20ms, got {p95:.2f}ms"

    async def test_update_user_performance(self, db_session) -> None:
        """Benchmark user update performance.

        Updates should be fast (< 15ms p95).
        """
        repository = UserRepository(db_session)

        # Create test user
        user = User(
            email="update_perf@example.com",
            username="update_perf",
            full_name="Update Performance",
        )
        user = await repository.create(user)
        await db_session.commit()

        iterations = 50
        times = []

        for i in range(iterations):
            # Re-fetch to get fresh instance
            user = await repository.get_by_id(user.id)
            assert user is not None

            user.full_name = f"Updated {i}"

            start = time.perf_counter()
            await db_session.flush()
            await db_session.refresh(user)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        # Calculate percentiles
        p50 = median(times)
        p95 = quantiles(times, n=100)[94] if len(times) >= 20 else max(times)


        assert p50 < 8, f"p50 should be < 8ms, got {p50:.2f}ms"
        assert p95 < 15, f"p95 should be < 15ms, got {p95:.2f}ms"

    async def test_soft_delete_performance(self, db_session) -> None:
        """Benchmark soft delete performance.

        Soft deletes (update deleted_at) should be fast (< 15ms p95).
        """
        repository = UserRepository(db_session)

        # Create test users
        user_ids = []
        for i in range(50):
            user = User(
                email=f"delete_perf{i}@example.com",
                username=f"delete_perf{i}",
                full_name=f"Delete Perf {i}",
            )
            user = await repository.create(user)
            user_ids.append(user.id)

        await db_session.commit()

        # Benchmark soft deletes
        times = []

        for user_id in user_ids:
            start = time.perf_counter()
            await repository.delete(user_id)
            await db_session.flush()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        # Calculate percentiles
        p50 = median(times)
        p95 = quantiles(times, n=100)[94] if len(times) >= 20 else max(times)


        assert p50 < 8, f"p50 should be < 8ms, got {p50:.2f}ms"
        assert p95 < 15, f"p95 should be < 15ms, got {p95:.2f}ms"


@pytest.mark.benchmark
@pytest.mark.asyncio
class TestDatabaseConcurrentPerformance:
    """Benchmarks for concurrent database operations."""

    async def test_concurrent_reads_performance(self, db_session) -> None:
        """Benchmark concurrent read performance.

        Concurrent reads should maintain good performance.
        """
        repository = UserRepository(db_session)

        # Create test user
        user = User(
            email="concurrent_read@example.com",
            username="concurrent_read",
            full_name="Concurrent Read",
        )
        user = await repository.create(user)
        await db_session.commit()
        user_id = user.id

        # Benchmark concurrent reads
        concurrency = 20
        iterations = 5
        all_times = []

        for _ in range(iterations):

            async def single_read() -> float:
                start = time.perf_counter()
                result = await repository.get_by_id(user_id)
                elapsed = (time.perf_counter() - start) * 1000
                assert result is not None
                return elapsed

            tasks = [single_read() for _ in range(concurrency)]
            times = await asyncio.gather(*tasks)
            all_times.extend(times)

        # Calculate percentiles
        p50 = median(all_times)
        p95 = quantiles(all_times, n=100)[94]


        # Under concurrency, allow slightly higher latency
        assert p50 < 15, f"p50 should be < 15ms under concurrency, got {p50:.2f}ms"
        assert p95 < 30, f"p95 should be < 30ms under concurrency, got {p95:.2f}ms"

    async def test_bulk_insert_performance(self, db_session) -> None:
        """Benchmark bulk insert performance.

        Bulk inserts should be efficient with batch processing.
        """
        repository = UserRepository(db_session)

        batch_sizes = [10, 25, 50]

        for batch_size in batch_sizes:
            users = [
                User(
                    email=f"bulk_insert{i}_{time.time()}@example.com",
                    username=f"bulk_insert{i}_{int(time.time())}",
                    full_name=f"Bulk Insert {i}",
                )
                for i in range(batch_size)
            ]

            start = time.perf_counter()
            for user in users:
                await repository.create(user)
            await db_session.flush()
            elapsed = (time.perf_counter() - start) * 1000

            per_item_time = elapsed / batch_size


            # Per-item time should be reasonable even for large batches
            assert per_item_time < 5, f"Per-item time should be < 5ms, got {per_item_time:.2f}ms"

            await db_session.rollback()  # Clean up for next batch
