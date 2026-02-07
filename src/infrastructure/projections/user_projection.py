"""User projection worker for syncing events to read models.

Projection workers consume events from the event store and update
denormalized read models. This keeps the read side eventually consistent
with the write side in CQRS.

How It Works:
1. Load checkpoint (last processed event timestamp)
2. Query events since checkpoint
3. For each event, update read model
4. Save new checkpoint
5. Repeat (continuous polling or message-driven)

Benefits:
- Keeps read models in sync with events
- Can rebuild read models from scratch (event replay)
- Independent scaling (multiple workers)
- Fault tolerant (checkpointing)

Features:
- Checkpoint-based resumption
- Error handling with retry
- Metrics tracking
- Multiple projection strategies
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events import (
    UserCreatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
    UserUpdatedEvent,
)
from src.domain.events.base import DomainEvent
from src.infrastructure.logging.config import get_logger
from src.infrastructure.persistence.read_models import UserReadModel
from src.infrastructure.repositories.event_store_repository import (
    EventStoreRepository,
)


logger = get_logger(__name__)


class ProjectionCheckpoint:
    """Manages projection checkpoint for resumability.

    The checkpoint stores the last processed event timestamp,
    allowing the projection worker to resume from where it left off.

    Storage options:
    - Database table
    - Redis
    - File system

    Attributes:
        projection_name: Name of the projection (e.g., "user_projection")
        last_event_timestamp: Last processed event timestamp
    """

    def __init__(self, projection_name: str):
        """Initialize checkpoint.

        Args:
            projection_name: Unique name for this projection
        """
        self.projection_name = projection_name
        self.last_event_timestamp: datetime | None = None

    async def load(self, session: AsyncSession) -> datetime:
        """Load checkpoint from storage.

        Args:
            session: Database session

        Returns:
            Last processed event timestamp (or epoch if no checkpoint)
        """
        from sqlalchemy import text

        # Load checkpoint from database using raw SQL
        # This avoids needing a separate ORM model
        result = await session.execute(
            text(
                """
                SELECT last_event_timestamp
                FROM projection_checkpoints
                WHERE projection_name = :name
                """
            ),
            {"name": self.projection_name},
        )
        row = result.first()

        if row and row[0]:
            self.last_event_timestamp = row[0]
            logger.info(
                "checkpoint_loaded",
                projection=self.projection_name,
                timestamp=row[0].isoformat(),
            )
            return row[0]

        # No checkpoint found, start from epoch
        logger.info(
            "checkpoint_not_found",
            projection=self.projection_name,
            message="Starting from beginning",
        )
        return datetime.min.replace(tzinfo=UTC)

    async def save(self, session: AsyncSession, timestamp: datetime) -> None:
        """Save checkpoint to storage.

        Args:
            session: Database session
            timestamp: Event timestamp to checkpoint
        """
        from sqlalchemy import text

        self.last_event_timestamp = timestamp

        # Upsert checkpoint using raw SQL (PostgreSQL syntax)
        await session.execute(
            text(
                """
                INSERT INTO projection_checkpoints (projection_name, last_event_timestamp, updated_at)
                VALUES (:name, :timestamp, :updated_at)
                ON CONFLICT (projection_name)
                DO UPDATE SET
                    last_event_timestamp = :timestamp,
                    updated_at = :updated_at
                """
            ),
            {
                "name": self.projection_name,
                "timestamp": timestamp,
                "updated_at": datetime.now(UTC),
            },
        )

        await session.commit()

        logger.debug(
            "checkpoint_saved",
            projection=self.projection_name,
            timestamp=timestamp.isoformat(),
        )


class UserProjectionWorker:
    """Background worker that projects user events to read models.

    This worker continuously polls for new events and updates the
    user read model accordingly. It's the glue that keeps the read
    side in sync with the write side.

    Projection Strategy:
    1. UserCreatedEvent → INSERT into user_read_model
    2. UserUpdatedEvent → UPDATE user_read_model
    3. UserDeletedEvent → UPDATE deleted_at
    4. UserRestoredEvent → UPDATE deleted_at = NULL

    Attributes:
        _event_store: Event store repository
        _session: Database session for read model updates
        _checkpoint: Checkpoint manager for resumability
        _running: Whether the worker is currently running

    Example:
        >>> worker = UserProjectionWorker(event_store, session)
        >>> await worker.start()  # Runs continuously
    """

    def __init__(
        self,
        event_store: EventStoreRepository,
        session: AsyncSession,
    ):
        """Initialize projection worker.

        Args:
            event_store: Event store repository
            session: Database session for read model writes
        """
        self._event_store = event_store
        self._session = session
        self._checkpoint = ProjectionCheckpoint("user_projection")
        self._running = False
        self._processed_count = 0
        self._error_count = 0

    async def start(self, poll_interval: float = 1.0) -> None:
        """Start projection worker (runs continuously).

        This method will run indefinitely, polling for new events
        and projecting them to the read model.

        Args:
            poll_interval: Seconds between polling iterations

        Example:
            >>> worker = UserProjectionWorker(event_store, session)
            >>> await worker.start(poll_interval=2.0)  # Poll every 2 seconds
        """
        self._running = True

        # Load checkpoint
        last_timestamp = await self._checkpoint.load(self._session)

        logger.info(
            "projection_worker_started",
            projection="user_projection",
            checkpoint=last_timestamp.isoformat(),
        )

        while self._running:
            try:
                # Get new events since checkpoint
                events_processed = 0

                async for entry, event in self._event_store.get_all_events_since(
                    since=last_timestamp,
                    event_types=[
                        "user.created",
                        "user.updated",
                        "user.deleted",
                        "user.restored",
                    ],
                    limit=100,  # Process in batches
                ):
                    # Project event to read model
                    await self._project_event(event)
                    events_processed += 1

                    # Update checkpoint
                    last_timestamp = entry.occurred_at
                    await self._checkpoint.save(self._session, last_timestamp)

                    self._processed_count += 1

                if events_processed > 0:
                    # Commit batch
                    await self._session.commit()

                    logger.info(
                        "projection_batch_processed",
                        count=events_processed,
                        total_processed=self._processed_count,
                    )

                # Sleep before next poll
                await asyncio.sleep(poll_interval)

            except Exception as e:
                self._error_count += 1
                logger.error(
                    "projection_error",
                    error=str(e),
                    error_count=self._error_count,
                )
                await self._session.rollback()

                # Exponential backoff on errors
                await asyncio.sleep(min(poll_interval * (2**self._error_count), 60))

    async def stop(self) -> None:
        """Stop projection worker gracefully."""
        self._running = False
        logger.info("projection_worker_stopped", processed=self._processed_count)

    async def rebuild_from_scratch(self) -> None:
        """Rebuild read model from scratch by replaying all events.

        This is useful for:
        - Recovering from data corruption
        - Adding new denormalized fields
        - Testing projection logic

        WARNING: This will DELETE all data in the read model
        and replay all events from the beginning.

        Example:
            >>> worker = UserProjectionWorker(event_store, session)
            >>> await worker.rebuild_from_scratch()
        """
        logger.warning("rebuild_started", projection="user_projection")

        # Clear read model
        await self._session.execute(update(UserReadModel).values(deleted_at=datetime.now(UTC)))
        await self._session.commit()

        # Replay all events from beginning
        count = 0
        async for entry, event in self._event_store.get_all_events_since(
            since=datetime.min.replace(tzinfo=UTC),
            event_types=[
                "user.created",
                "user.updated",
                "user.deleted",
                "user.restored",
            ],
        ):
            await self._project_event(event)
            count += 1

            # Commit in batches
            if count % 100 == 0:
                await self._session.commit()
                logger.info("rebuild_progress", events_processed=count)

        # Final commit
        await self._session.commit()

        logger.info("rebuild_completed", total_events=count)

    async def _project_event(self, event: DomainEvent) -> None:
        """Project single event to read model.

        This is where the event sourcing "magic" happens - we update
        the denormalized read model based on domain events.

        Args:
            event: Domain event to project

        Example:
            >>> event = UserCreatedEvent(user_id=..., email=..., username=...)
            >>> await worker._project_event(event)
        """
        if isinstance(event, UserCreatedEvent):
            await self._handle_user_created(event)

        elif isinstance(event, UserUpdatedEvent):
            await self._handle_user_updated(event)

        elif isinstance(event, UserDeletedEvent):
            await self._handle_user_deleted(event)

        elif isinstance(event, UserRestoredEvent):
            await self._handle_user_restored(event)

    async def _handle_user_created(self, event: UserCreatedEvent) -> None:
        """Handle UserCreatedEvent projection.

        Creates new entry in user read model.

        Args:
            event: User created event
        """
        # Calculate profile completion
        profile_completion = self._calculate_profile_completion(
            email=event.email,
            username=event.username,
            full_name=event.full_name,
        )

        # Create read model entry
        read_model = UserReadModel(
            id=event.user_id,
            email=event.email,
            username=event.username,
            full_name=event.full_name,
            is_active=True,
            tenant_id=event.tenant_id,
            created_at=event.occurred_at,
            updated_at=event.occurred_at,
            total_orders=0,
            profile_completion=profile_completion,
        )

        self._session.add(read_model)

        logger.debug(
            "projection_user_created",
            user_id=str(event.user_id),
            email=event.email,
        )

    async def _handle_user_updated(self, event: UserUpdatedEvent) -> None:
        """Handle UserUpdatedEvent projection.

        Updates existing entry in user read model.

        Args:
            event: User updated event
        """
        # Build update values
        update_values: dict = {"updated_at": event.occurred_at}

        for field, (old_value, new_value) in event.changed_fields.items():
            update_values[field] = new_value

        # Execute update
        stmt = (
            update(UserReadModel).where(UserReadModel.id == event.user_id).values(**update_values)
        )

        await self._session.execute(stmt)

        logger.debug(
            "projection_user_updated",
            user_id=str(event.user_id),
            fields_changed=list(event.changed_fields.keys()),
        )

    async def _handle_user_deleted(self, event: UserDeletedEvent) -> None:
        """Handle UserDeletedEvent projection.

        Marks user as deleted in read model.

        Args:
            event: User deleted event
        """
        stmt = (
            update(UserReadModel)
            .where(UserReadModel.id == event.user_id)
            .values(deleted_at=event.occurred_at)
        )

        await self._session.execute(stmt)

        logger.debug(
            "projection_user_deleted",
            user_id=str(event.user_id),
            soft_delete=event.soft_delete,
        )

    async def _handle_user_restored(self, event: UserRestoredEvent) -> None:
        """Handle UserRestoredEvent projection.

        Restores deleted user in read model.

        Args:
            event: User restored event
        """
        stmt = (
            update(UserReadModel)
            .where(UserReadModel.id == event.user_id)
            .values(deleted_at=None, updated_at=event.occurred_at)
        )

        await self._session.execute(stmt)

        logger.debug("projection_user_restored", user_id=str(event.user_id))

    def _calculate_profile_completion(
        self,
        email: str | None,
        username: str | None,
        full_name: str | None,
    ) -> int:
        """Calculate profile completion percentage.

        Args:
            email: Email address
            username: Username
            full_name: Full name

        Returns:
            Profile completion percentage (0-100)
        """
        score = 0
        if email:
            score += 30
        if username:
            score += 30
        if full_name:
            score += 40
        return score


__all__ = [
    "ProjectionCheckpoint",
    "UserProjectionWorker",
]
