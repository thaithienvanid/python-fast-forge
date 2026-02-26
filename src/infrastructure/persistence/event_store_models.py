"""Event Store database models for Event Sourcing.

This module provides the database schema for persisting domain events
in an append-only log, enabling event sourcing and CQRS patterns.

Features:
- Immutable event log (append-only)
- Optimistic locking with aggregate versioning
- Event snapshots for performance optimization
- Full event history and audit trail
- Time-ordered events with occurred_at timestamps
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from src.domain.models.base import Base


class EventStoreEntry(Base):
    """Immutable append-only event log entry.

    Each entry represents a single domain event that has occurred in the system.
    Events are never updated or deleted - only appended.

    Attributes:
        event_id: Unique identifier for this specific event (UUIDv7 for time-ordering)
        event_type: Fully-qualified event type name (e.g., "user.created")
        event_version: Schema version for event evolution (default: 1)
        aggregate_type: Type of aggregate this event belongs to (e.g., "User")
        aggregate_id: Identifier of the aggregate instance
        aggregate_version: Version number of aggregate after this event (for optimistic locking)
        event_data: Full event payload as JSON
        metadata: Additional context (causation_id, correlation_id, user_id, etc.)
        occurred_at: When the event occurred (business time)
        recorded_at: When the event was persisted (technical time)

    Indexes:
        - Primary key on event_id
        - Composite index on (aggregate_type, aggregate_id) for event stream reconstruction
        - Index on occurred_at for temporal queries
        - Index on event_type for event type queries
        - Unique index on (aggregate_id, aggregate_version) for optimistic locking

    Example:
        >>> entry = EventStoreEntry(
        ...     event_id=uuid7(),
        ...     event_type="user.created",
        ...     event_version=1,
        ...     aggregate_type="User",
        ...     aggregate_id=user_id,
        ...     aggregate_version=1,
        ...     event_data={"email": "user@example.com", "username": "john"},
        ...     metadata={"user_id": str(admin_id), "correlation_id": str(trace_id)},
        ...     occurred_at=datetime.now(UTC),
        ... )
        >>> session.add(entry)
        >>> await session.commit()
    """

    __tablename__ = "event_store"

    # Event identity
    event_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="Unique event identifier (UUIDv7 for time-ordering)",
    )

    # Event metadata
    event_type = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Fully-qualified event type (e.g., 'user.created')",
    )
    event_version = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Event schema version for evolution",
    )

    # Aggregate identification
    aggregate_type = Column(
        String(100),
        nullable=False,
        comment="Type of aggregate (e.g., 'User', 'Order')",
    )
    aggregate_id = Column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Aggregate instance identifier",
    )
    aggregate_version = Column(
        Integer,
        nullable=False,
        comment="Aggregate version after this event (for optimistic locking)",
    )

    # Event payload
    event_data = Column(
        JSONB,
        nullable=False,
        comment="Full event payload as JSON",
    )
    event_metadata = Column(
        JSONB,
        default=dict,  # Use callable to avoid shared mutable default
        server_default="{}",  # Ensure default at DB level
        comment="Additional metadata (causation_id, correlation_id, user_id, etc.)",
    )

    # Timing
    occurred_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the event occurred (business time)",
    )
    recorded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the event was persisted (technical time)",
    )

    # Composite indexes for efficient queries
    __table_args__ = (
        # Index for reconstructing aggregate event stream
        Index(
            "ix_event_store_aggregate",
            "aggregate_type",
            "aggregate_id",
        ),
        # Index for temporal queries
        Index(
            "ix_event_store_occurred_at",
            "occurred_at",
        ),
        # Index for event type filtering
        Index(
            "ix_event_store_event_type",
            "event_type",
        ),
        # Unique constraint for optimistic locking (prevents concurrent updates)
        Index(
            "ix_event_store_aggregate_version_unique",
            "aggregate_id",
            "aggregate_version",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EventStoreEntry("
            f"event_id={self.event_id}, "
            f"event_type={self.event_type}, "
            f"aggregate_type={self.aggregate_type}, "
            f"aggregate_id={self.aggregate_id}, "
            f"aggregate_version={self.aggregate_version})"
        )


class EventStoreSnapshot(Base):
    """Snapshot table for aggregate state optimization.

    Snapshots store the computed state of an aggregate at a specific version,
    allowing faster reconstruction by loading the snapshot + subsequent events
    instead of replaying all events from the beginning.

    Attributes:
        id: Unique snapshot identifier
        aggregate_type: Type of aggregate (e.g., "User")
        aggregate_id: Identifier of the aggregate instance
        aggregate_version: Version of aggregate when snapshot was taken
        snapshot_data: Full aggregate state as JSON
        created_at: When this snapshot was created

    Indexes:
        - Primary key on id
        - Unique index on aggregate_id (one snapshot per aggregate)

    Snapshot Strategy:
        - Create snapshot every N events (e.g., every 50 events)
        - Snapshots are optional (system works without them)
        - Old snapshots can be deleted (keep only latest)

    Example:
        >>> snapshot = EventStoreSnapshot(
        ...     id=uuid7(),
        ...     aggregate_type="User",
        ...     aggregate_id=user_id,
        ...     aggregate_version=50,
        ...     snapshot_data={
        ...         "id": str(user_id),
        ...         "email": "user@example.com",
        ...         "username": "john",
        ...         "is_active": True,
        ...         "created_at": "2024-01-15T10:30:00Z",
        ...     },
        ... )
        >>> session.add(snapshot)
        >>> await session.commit()
    """

    __tablename__ = "event_store_snapshots"

    # Identity
    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="Unique snapshot identifier",
    )

    # Aggregate identification
    aggregate_type = Column(
        String(100),
        nullable=False,
        comment="Type of aggregate (e.g., 'User', 'Order')",
    )
    aggregate_id = Column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        comment="Aggregate instance identifier (one snapshot per aggregate)",
    )
    aggregate_version = Column(
        Integer,
        nullable=False,
        comment="Aggregate version when snapshot was taken",
    )

    # Snapshot data
    snapshot_data = Column(
        JSONB,
        nullable=False,
        comment="Full aggregate state as JSON",
    )

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When this snapshot was created",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"EventStoreSnapshot("
            f"aggregate_type={self.aggregate_type}, "
            f"aggregate_id={self.aggregate_id}, "
            f"aggregate_version={self.aggregate_version})"
        )


__all__ = [
    "EventStoreEntry",
    "EventStoreSnapshot",
]
