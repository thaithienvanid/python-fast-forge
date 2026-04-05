"""Event Store repository for persisting and retrieving domain events.

This repository implements the event sourcing pattern, storing all domain events
in an append-only log and providing methods for event reconstruction.

Features:
- Append-only event log (immutable)
- Optimistic locking with aggregate versioning
- Event stream reconstruction
- Snapshot support for performance optimization
- Temporal queries (events since timestamp)
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events import get_event_class
from src.domain.events.base import DomainEvent
from src.domain.exceptions import DomainException
from src.infrastructure.persistence.event_store_models import (
    EventStoreEntry,
    EventStoreSnapshot,
)


class ConcurrencyError(DomainException):
    """Raised when optimistic locking detects concurrent modifications.

    This error occurs when two processes try to append events to the same
    aggregate simultaneously with mismatched version numbers.

    Example:
        >>> # Process A and B both read User at version 5
        >>> # Process A appends event (expects version 5, writes version 6)
        >>> await event_store.append_event(event_a, expected_version=5)  # OK
        >>> # Process B tries to append event (expects version 5, but current is 6)
        >>> await event_store.append_event(event_b, expected_version=5)  # ConcurrencyError!
    """


class EventStoreRepository:
    """Repository for event store operations.

    This repository handles all persistence operations for the event store,
    including appending events, reconstructing event streams, and managing snapshots.

    Attributes:
        _session: SQLAlchemy async session for database operations

    Example:
        >>> async with get_session() as session:
        ...     event_store = EventStoreRepository(session)
        ...
        ...     # Append event
        ...     event = UserCreatedEvent(aggregate_id=user_id, ...)
        ...     await event_store.append_event(event, "User", expected_version=None)
        ...
        ...     # Get event stream
        ...     async for event in event_store.get_events(user_id, "User"):
        ...         print(f"Event: {event.event_type}")
    """

    def __init__(self, session: AsyncSession):
        """Initialize event store repository.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def append_event(
        self,
        event: DomainEvent,
        aggregate_type: str,
        expected_version: int | None = None,
    ) -> int:
        """Append event to store with optimistic locking.

        Args:
            event: Domain event to persist
            aggregate_type: Type of aggregate (e.g., "User", "Order")
            expected_version: Expected current version (for concurrency control)

        Returns:
            New aggregate version after appending this event

        Raises:
            ConcurrencyError: If aggregate version mismatch (concurrent modification detected)

        Example:
            >>> event = UserCreatedEvent(
            ...     aggregate_id=user_id,
            ...     user_id=user_id,
            ...     email="user@example.com",
            ...     username="john",
            ... )
            >>> new_version = await event_store.append_event(
            ...     event,
            ...     "User",
            ...     expected_version=None,  # New aggregate
            ... )
            >>> print(f"New version: {new_version}")  # 1
        """
        # Get current version
        current_version = await self._get_current_version(aggregate_type, event.aggregate_id)

        # Optimistic locking check
        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                f"Concurrency conflict for {aggregate_type} {event.aggregate_id}: "
                f"expected version {expected_version}, but current is {current_version}"
            )

        # Calculate new version
        new_version = current_version + 1

        # Create event store entry
        entry = EventStoreEntry(
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=getattr(event, "event_version", 1),
            aggregate_type=aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=new_version,
            event_data=event.model_dump(mode="json"),
            metadata={
                "commanded_by": event.metadata.get("commanded_by")
                if hasattr(event, "metadata")
                else None,
                "correlation_id": event.metadata.get("correlation_id")
                if hasattr(event, "metadata")
                else None,
                "causation_id": event.metadata.get("causation_id")
                if hasattr(event, "metadata")
                else None,
            },
            occurred_at=event.occurred_at,
        )

        self._session.add(entry)
        await self._session.flush()

        return new_version

    async def get_events(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
        from_version: int = 0,
    ) -> AsyncIterator[DomainEvent]:
        """Get all events for an aggregate.

        Yields events in order from oldest to newest, allowing reconstruction
        of aggregate state by replaying events.

        Args:
            aggregate_id: Aggregate identifier
            aggregate_type: Type of aggregate (e.g., "User")
            from_version: Starting version (for incremental replay)

        Yields:
            Domain events in chronological order

        Example:
            >>> events = []
            >>> async for event in event_store.get_events(user_id, "User"):
            ...     events.append(event)
            ...     print(f"{event.event_type} at version {event.aggregate_version}")
            user.created at version 1
            user.updated at version 2
            user.updated at version 3
        """
        query = (
            select(EventStoreEntry)
            .where(
                EventStoreEntry.aggregate_id == aggregate_id,
                EventStoreEntry.aggregate_type == aggregate_type,
                EventStoreEntry.aggregate_version > from_version,
            )
            .order_by(EventStoreEntry.aggregate_version)
        )

        result = await self._session.execute(query)

        for entry in result.scalars():
            # Reconstruct domain event from stored data
            event_class = get_event_class(entry.event_type)
            event = event_class.model_validate(entry.event_data)
            yield event

    async def get_all_events_since(
        self,
        since: datetime,
        event_types: list[str] | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[tuple[EventStoreEntry, DomainEvent]]:
        """Get all events since a timestamp (for projections).

        This is used by projection workers to process new events and update read models.

        Args:
            since: Starting timestamp
            event_types: Filter by specific event types (optional)
            limit: Maximum number of events to return (optional)

        Yields:
            Tuples of (EventStoreEntry, reconstructed DomainEvent)

        Example:
            >>> # Projection worker polling for new events
            >>> checkpoint = await load_checkpoint()
            >>> async for entry, event in event_store.get_all_events_since(checkpoint):
            ...     await update_read_model(event)
            ...     await save_checkpoint(entry.occurred_at)
        """
        query = select(EventStoreEntry).where(EventStoreEntry.occurred_at > since)

        if event_types:
            query = query.where(EventStoreEntry.event_type.in_(event_types))

        query = query.order_by(EventStoreEntry.occurred_at)

        if limit:
            query = query.limit(limit)

        result = await self._session.execute(query)

        for entry in result.scalars():
            event_class = get_event_class(entry.event_type)
            event = event_class.model_validate(entry.event_data)
            yield entry, event

    async def save_snapshot(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
        aggregate_version: int,
        snapshot_data: dict[str, Any],
    ) -> None:
        """Save aggregate snapshot for performance optimization.

        Snapshots allow faster aggregate reconstruction by loading the snapshot
        plus incremental events instead of replaying all events from the beginning.

        Args:
            aggregate_id: Aggregate identifier
            aggregate_type: Type of aggregate
            aggregate_version: Version at which snapshot was taken
            snapshot_data: Full aggregate state as dict

        Example:
            >>> # Create snapshot every 50 events
            >>> if aggregate_version % 50 == 0:
            ...     await event_store.save_snapshot(
            ...         user_id,
            ...         "User",
            ...         aggregate_version,
            ...         user.model_dump(mode="json"),
            ...     )
        """
        # Check if snapshot already exists
        existing = await self._session.execute(
            select(EventStoreSnapshot).where(EventStoreSnapshot.aggregate_id == aggregate_id)
        )
        snapshot = existing.scalar_one_or_none()

        if snapshot:
            # Update existing snapshot
            snapshot.aggregate_version = aggregate_version
            snapshot.snapshot_data = snapshot_data
            snapshot.created_at = datetime.now()
        else:
            # Create new snapshot
            from uuid_extensions import uuid7

            snapshot = EventStoreSnapshot(
                id=uuid7(),
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                aggregate_version=aggregate_version,
                snapshot_data=snapshot_data,
            )
            self._session.add(snapshot)

        await self._session.flush()

    async def get_snapshot(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
    ) -> tuple[int, dict[str, Any]] | None:
        """Get latest snapshot for aggregate.

        Args:
            aggregate_id: Aggregate identifier
            aggregate_type: Type of aggregate

        Returns:
            Tuple of (version, snapshot_data) or None if no snapshot exists

        Example:
            >>> snapshot = await event_store.get_snapshot(user_id, "User")
            >>> if snapshot:
            ...     version, data = snapshot
            ...     user = User.model_validate(data)
            ...     # Then replay events since version
            ...     async for event in event_store.get_events(user_id, "User", from_version=version):
            ...         user = apply_event(user, event)
        """
        query = select(EventStoreSnapshot).where(
            EventStoreSnapshot.aggregate_id == aggregate_id,
            EventStoreSnapshot.aggregate_type == aggregate_type,
        )

        result = await self._session.execute(query)
        snapshot = result.scalar_one_or_none()

        if snapshot:
            return (snapshot.aggregate_version, snapshot.snapshot_data)
        return None

    async def _get_current_version(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
    ) -> int:
        """Get current version of aggregate.

        Args:
            aggregate_type: Type of aggregate
            aggregate_id: Aggregate identifier

        Returns:
            Current version (0 if aggregate doesn't exist yet)
        """
        query = (
            select(EventStoreEntry.aggregate_version)
            .where(
                EventStoreEntry.aggregate_type == aggregate_type,
                EventStoreEntry.aggregate_id == aggregate_id,
            )
            .order_by(EventStoreEntry.aggregate_version.desc())
            .limit(1)
        )

        result = await self._session.execute(query)
        version = result.scalar_one_or_none()
        return version or 0


__all__ = [
    "ConcurrencyError",
    "EventStoreRepository",
]
