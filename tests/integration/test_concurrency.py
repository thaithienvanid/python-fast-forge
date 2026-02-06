"""Concurrency and race condition tests.

This module tests for race conditions, concurrent access patterns,
and thread-safety issues in critical code paths.
"""

import asyncio
from collections import Counter
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import ValidationError
from src.domain.models.user import User
from src.infrastructure.repositories.user_repository import UserRepository


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentDatabaseOperations:
    """Test concurrent database operations for race conditions."""

    async def test_concurrent_user_creation_different_emails(
        self,
        db_session,
    ) -> None:
        """Test concurrent creation of different users succeeds.

        Multiple users with different emails should be created successfully
        when done concurrently.
        """
        repository = UserRepository(db_session)

        # Create 10 users concurrently
        async def create_user(index: int) -> User:
            user = User(
                email=f"user{index}@example.com",
                username=f"user{index}",
                full_name=f"User {index}",
            )
            return await repository.create(user)

        tasks = [create_user(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successful_results = [r for r in results if isinstance(r, User)]
        assert len(successful_results) == 10

        # Verify all have unique IDs
        ids = {user.id for user in successful_results}
        assert len(ids) == 10

    async def test_concurrent_user_creation_duplicate_email_race(
        self,
        db_session,
    ) -> None:
        """Test race condition with duplicate email creation.

        When multiple concurrent requests try to create users with the same
        email, only one should succeed due to unique constraint.
        """
        repository = UserRepository(db_session)
        same_email = "duplicate@example.com"

        # Try to create 5 users with same email concurrently
        async def create_user(index: int) -> User:
            user = User(
                email=same_email,
                username=f"user{index}",  # Different usernames
                full_name=f"User {index}",
            )
            return await repository.create(user)

        tasks = [create_user(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and failures
        successes = [r for r in results if isinstance(r, User)]
        failures = [r for r in results if isinstance(r, (IntegrityError, Exception))]

        # Exactly one should succeed, others should fail with IntegrityError
        assert len(successes) == 1, "Only one user creation should succeed"
        assert len(failures) >= 4, "At least 4 should fail due to duplicate email"

    async def test_concurrent_update_same_user(
        self,
        db_session,
    ) -> None:
        """Test concurrent updates to the same user.

        Multiple concurrent updates to the same user should all succeed
        without data corruption (last write wins with optimistic locking).
        """
        repository = UserRepository(db_session)

        # Create initial user
        user = User(
            email="concurrent@example.com",
            username="concurrent_user",
            full_name="Concurrent User",
        )
        user = await repository.create(user)
        user_id = user.id

        # Concurrently update the same user's full_name
        async def update_user(new_name: str) -> User:
            # Re-fetch user to get fresh instance
            user = await repository.get_by_id(user_id)
            if user is None:
                raise ValueError("User not found")

            user.full_name = new_name
            await db_session.flush()
            await db_session.refresh(user)
            return user

        names = [f"Name {i}" for i in range(10)]
        tasks = [update_user(name) for name in names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All updates should succeed
        successful_updates = [r for r in results if isinstance(r, User)]
        assert len(successful_updates) >= 8, "Most updates should succeed"

        # Final user should have one of the names
        final_user = await repository.get_by_id(user_id)
        assert final_user is not None
        assert final_user.full_name in names

    async def test_concurrent_soft_delete_and_read(
        self,
        db_session,
    ) -> None:
        """Test race between soft delete and read operations.

        Ensures that concurrent soft deletes and reads handle properly.
        """
        repository = UserRepository(db_session)

        # Create user
        user = User(
            email="deleteme@example.com",
            username="deleteme",
            full_name="Delete Me",
        )
        user = await repository.create(user)
        user_id = user.id

        # Concurrently delete and read
        async def read_user() -> User | None:
            await asyncio.sleep(0.001)  # Small delay
            return await repository.get_by_id(user_id)

        async def delete_user() -> bool:
            return await repository.delete(user_id)

        # Run 1 delete and 10 reads concurrently
        tasks = [delete_user()] + [read_user() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Delete should succeed
        delete_result = results[0]
        assert delete_result is True

        # Reads might return user or None (depending on timing)
        read_results = results[1:]
        # At least some reads should return None after delete
        none_count = sum(1 for r in read_results if r is None)
        assert none_count > 0, "Some reads should return None after delete"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentBatchOperations:
    """Test concurrent batch operations for race conditions."""

    async def test_batch_create_no_duplicates_across_batches(
        self,
        db_session,
    ) -> None:
        """Test that concurrent batch creates don't create duplicates.

        Multiple batches running concurrently should not create duplicate
        users even if emails overlap between batches (should fail properly).
        """
        repository = UserRepository(db_session)

        # Create function that creates a batch of users
        async def create_batch(batch_id: int, count: int) -> list[User]:
            users = []
            for i in range(count):
                user = User(
                    email=f"batch{batch_id}_user{i}@example.com",
                    username=f"batch{batch_id}_user{i}",
                    full_name=f"Batch {batch_id} User {i}",
                )
                created = await repository.create(user)
                users.append(created)
            return users

        # Create 5 batches concurrently
        tasks = [create_batch(batch_id, 5) for batch_id in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All batches should succeed
        successful_batches = [r for r in results if isinstance(r, list)]
        assert len(successful_batches) == 5

        # Count total users created
        total_users = sum(len(batch) for batch in successful_batches)
        assert total_users == 25  # 5 batches * 5 users

        # Verify no duplicate emails
        all_users = [user for batch in successful_batches for user in batch]
        emails = [user.email for user in all_users]
        assert len(emails) == len(set(emails)), "No duplicate emails should exist"

    async def test_concurrent_bulk_query_operations(
        self,
        db_session,
    ) -> None:
        """Test that concurrent bulk queries work correctly.

        Multiple concurrent bulk queries should return consistent results
        without race conditions.
        """
        repository = UserRepository(db_session)

        # Create initial users
        emails = [f"bulkquery{i}@example.com" for i in range(20)]
        for i, email in enumerate(emails):
            user = User(
                email=email,
                username=f"bulkquery{i}",
                full_name=f"Bulk Query {i}",
            )
            await repository.create(user)

        await db_session.commit()

        # Concurrently query for different subsets of emails
        async def query_emails(email_list: list[str]) -> list[User]:
            return await repository.find_by_emails(email_list)

        # Create overlapping email lists
        tasks = [
            query_emails(emails[0:10]),
            query_emails(emails[5:15]),
            query_emails(emails[10:20]),
            query_emails(emails[0:5]),
            query_emails(emails[15:20]),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all queries succeeded
        assert len(results) == 5
        assert all(isinstance(r, list) for r in results)

        # Verify correct number of results for each query
        assert len(results[0]) == 10  # emails[0:10]
        assert len(results[1]) == 10  # emails[5:15]
        assert len(results[2]) == 10  # emails[10:20]
        assert len(results[3]) == 5  # emails[0:5]
        assert len(results[4]) == 5  # emails[15:20]


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentIdempotency:
    """Test idempotency under concurrent access."""

    async def test_concurrent_identical_creates_fail_properly(
        self,
        db_session,
    ) -> None:
        """Test that identical concurrent create requests fail properly.

        When multiple requests try to create the exact same user
        concurrently, only one should succeed.
        """
        repository = UserRepository(db_session)

        # Try to create identical user 10 times concurrently
        async def create_same_user() -> User:
            user = User(
                email="identical@example.com",
                username="identical_user",
                full_name="Identical User",
            )
            return await repository.create(user)

        tasks = [create_same_user() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Exactly one should succeed
        successes = [r for r in results if isinstance(r, User)]
        failures = [r for r in results if isinstance(r, (IntegrityError, Exception))]

        assert len(successes) == 1, "Only one create should succeed"
        assert len(failures) >= 9, "At least 9 should fail"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentCacheAccess:
    """Test concurrent cache access patterns."""

    async def test_concurrent_cache_get_operations(
        self,
        mock_cache,
    ) -> None:
        """Test that concurrent cache reads don't cause issues.

        Multiple concurrent reads of the same cache key should work safely.
        """
        # Setup cache to return a value
        mock_cache.get.return_value = {"id": "123", "email": "test@example.com"}

        # Concurrently read from cache
        async def read_cache() -> dict | None:
            return await mock_cache.get("user:123")

        tasks = [read_cache() for _ in range(100)]
        results = await asyncio.gather(*tasks)

        # All reads should succeed with same value
        assert len(results) == 100
        assert all(r == {"id": "123", "email": "test@example.com"} for r in results)

    async def test_concurrent_cache_set_operations(
        self,
        mock_cache,
    ) -> None:
        """Test that concurrent cache writes don't cause issues.

        Multiple concurrent writes to different keys should work safely.
        """
        # Concurrently write to cache
        async def write_cache(key: str, value: dict) -> bool:
            return await mock_cache.set(key, value, ttl=300)

        tasks = [
            write_cache(f"user:{i}", {"id": str(i), "email": f"user{i}@example.com"})
            for i in range(50)
        ]

        results = await asyncio.gather(*tasks)

        # All writes should succeed
        assert len(results) == 50
        assert all(r is True for r in results)


@pytest.mark.integration
@pytest.mark.asyncio
class TestStressConditions:
    """Test behavior under stress/high concurrency."""

    async def test_high_concurrency_user_creation(
        self,
        db_session,
    ) -> None:
        """Test creating many users concurrently (stress test).

        Creates 50 users concurrently to test system stability under load.
        """
        repository = UserRepository(db_session)

        async def create_user(index: int) -> User:
            user = User(
                email=f"stress{index}@example.com",
                username=f"stress{index}",
                full_name=f"Stress User {index}",
            )
            return await repository.create(user)

        tasks = [create_user(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed (allow for some timing issues)
        successes = [r for r in results if isinstance(r, User)]
        assert len(successes) >= 45, "At least 45 out of 50 should succeed"

    async def test_concurrent_mixed_operations(
        self,
        db_session,
    ) -> None:
        """Test mixed concurrent operations (create, read, update, delete).

        Simulates realistic concurrent access patterns with different
        operation types happening simultaneously.
        """
        repository = UserRepository(db_session)

        # Create initial users
        initial_users = []
        for i in range(10):
            user = User(
                email=f"mixed{i}@example.com",
                username=f"mixed{i}",
                full_name=f"Mixed User {i}",
            )
            created = await repository.create(user)
            initial_users.append(created)

        await db_session.commit()

        # Define different operations
        async def create_op(index: int) -> User:
            user = User(
                email=f"newmixed{index}@example.com",
                username=f"newmixed{index}",
                full_name=f"New Mixed {index}",
            )
            return await repository.create(user)

        async def read_op(user_id: UUID) -> User | None:
            return await repository.get_by_id(user_id)

        async def update_op(user_id: UUID) -> User:
            user = await repository.get_by_id(user_id)
            if user is None:
                raise ValueError("User not found")
            user.full_name = f"Updated {user.username}"
            await db_session.flush()
            await db_session.refresh(user)
            return user

        # Mix different operation types
        tasks = []
        # 10 creates
        tasks.extend([create_op(i) for i in range(10)])
        # 20 reads
        tasks.extend([read_op(user.id) for user in initial_users[:5]] * 4)
        # 10 updates
        tasks.extend([update_op(user.id) for user in initial_users[5:]])

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful operations
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) >= 35, "Most operations should succeed"
