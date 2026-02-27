"""Unit tests for event store models."""

from datetime import UTC, datetime
from uuid import uuid4

from src.infrastructure.persistence.event_store_models import (
    EventStoreEntry,
    EventStoreSnapshot,
)


class TestEventStoreEntry:
    """Tests for EventStoreEntry SQLAlchemy model."""

    def test_creates_event_store_entry(self):
        """Can create event store entry with all fields."""
        event_id = uuid4()
        aggregate_id = uuid4()
        occurred_at = datetime.now(UTC)

        entry = EventStoreEntry(
            event_id=event_id,
            event_type="user.created",
            event_version=1,
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=1,
            event_data={"email": "user@example.com", "username": "john"},
            event_metadata={"user_id": str(uuid4()), "correlation_id": str(uuid4())},
            occurred_at=occurred_at,
        )

        assert entry.event_id == event_id
        assert entry.event_type == "user.created"
        assert entry.event_version == 1
        assert entry.aggregate_type == "User"
        assert entry.aggregate_id == aggregate_id
        assert entry.aggregate_version == 1
        assert entry.event_data == {"email": "user@example.com", "username": "john"}
        assert "user_id" in entry.event_metadata
        assert "correlation_id" in entry.event_metadata
        assert entry.occurred_at == occurred_at

    def test_event_store_entry_repr(self):
        """Repr includes key event fields."""
        event_id = uuid4()
        aggregate_id = uuid4()

        entry = EventStoreEntry(
            event_id=event_id,
            event_type="user.updated",
            event_version=2,
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=5,
            event_data={},
            occurred_at=datetime.now(UTC),
        )

        repr_str = repr(entry)
        assert "EventStoreEntry" in repr_str
        assert str(event_id) in repr_str
        assert "user.updated" in repr_str
        assert "User" in repr_str
        assert str(aggregate_id) in repr_str
        assert "5" in repr_str

    def test_event_store_entry_table_name(self):
        """Event store entry has correct table name."""
        assert EventStoreEntry.__tablename__ == "event_store"

    def test_event_store_entry_with_minimal_fields(self):
        """Can create entry with minimal required fields."""
        event_id = uuid4()
        aggregate_id = uuid4()

        entry = EventStoreEntry(
            event_id=event_id,
            event_type="user.created",
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=1,
            event_data={"test": "data"},
            occurred_at=datetime.now(UTC),
        )

        assert entry.event_id == event_id
        assert entry.event_type == "user.created"
        assert entry.aggregate_type == "User"
        assert entry.aggregate_id == aggregate_id
        assert entry.aggregate_version == 1

    def test_event_store_entry_defaults(self):
        """Event store entry has default values."""
        entry = EventStoreEntry(
            event_id=uuid4(),
            event_type="test.event",
            aggregate_type="Test",
            aggregate_id=uuid4(),
            aggregate_version=1,
            event_data={},
            occurred_at=datetime.now(UTC),
        )

        # Check that defaults are set (would be applied by SQLAlchemy)
        assert hasattr(entry, "event_version")
        assert hasattr(entry, "event_metadata")
        assert hasattr(entry, "recorded_at")

    def test_event_store_entry_with_complex_event_data(self):
        """Event data can contain complex nested structures."""
        event_id = uuid4()

        entry = EventStoreEntry(
            event_id=event_id,
            event_type="order.created",
            aggregate_type="Order",
            aggregate_id=uuid4(),
            aggregate_version=1,
            event_data={
                "order_id": str(uuid4()),
                "items": [
                    {"product_id": "123", "quantity": 2, "price": 19.99},
                    {"product_id": "456", "quantity": 1, "price": 39.99},
                ],
                "total": 79.97,
                "status": "pending",
            },
            event_metadata={
                "user_id": str(uuid4()),
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
            },
            occurred_at=datetime.now(UTC),
        )

        assert "items" in entry.event_data
        assert len(entry.event_data["items"]) == 2
        assert entry.event_data["total"] == 79.97
        assert "ip_address" in entry.event_metadata


class TestEventStoreSnapshot:
    """Tests for EventStoreSnapshot SQLAlchemy model."""

    def test_creates_event_store_snapshot(self):
        """Can create event store snapshot with all fields."""
        snapshot_id = uuid4()
        aggregate_id = uuid4()
        created_at = datetime.now(UTC)

        snapshot = EventStoreSnapshot(
            id=snapshot_id,
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=50,
            snapshot_data={
                "id": str(uuid4()),
                "email": "user@example.com",
                "username": "john",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
            },
            created_at=created_at,
        )

        assert snapshot.id == snapshot_id
        assert snapshot.aggregate_type == "User"
        assert snapshot.aggregate_id == aggregate_id
        assert snapshot.aggregate_version == 50
        assert snapshot.snapshot_data["email"] == "user@example.com"
        assert snapshot.snapshot_data["username"] == "john"
        assert snapshot.created_at == created_at

    def test_event_store_snapshot_repr(self):
        """Repr includes key snapshot fields."""
        aggregate_id = uuid4()

        snapshot = EventStoreSnapshot(
            id=uuid4(),
            aggregate_type="Order",
            aggregate_id=aggregate_id,
            aggregate_version=100,
            snapshot_data={"test": "data"},
        )

        repr_str = repr(snapshot)
        assert "EventStoreSnapshot" in repr_str
        assert "Order" in repr_str
        assert str(aggregate_id) in repr_str
        assert "100" in repr_str

    def test_event_store_snapshot_table_name(self):
        """Event store snapshot has correct table name."""
        assert EventStoreSnapshot.__tablename__ == "event_store_snapshots"

    def test_event_store_snapshot_with_minimal_fields(self):
        """Can create snapshot with minimal required fields."""
        snapshot_id = uuid4()
        aggregate_id = uuid4()

        snapshot = EventStoreSnapshot(
            id=snapshot_id,
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=50,
            snapshot_data={},
        )

        assert snapshot.id == snapshot_id
        assert snapshot.aggregate_type == "User"
        assert snapshot.aggregate_id == aggregate_id
        assert snapshot.aggregate_version == 50

    def test_event_store_snapshot_with_complex_data(self):
        """Snapshot data can contain complex aggregate state."""
        snapshot = EventStoreSnapshot(
            id=uuid4(),
            aggregate_type="ShoppingCart",
            aggregate_id=uuid4(),
            aggregate_version=25,
            snapshot_data={
                "cart_id": str(uuid4()),
                "user_id": str(uuid4()),
                "items": [
                    {
                        "product_id": "prod-123",
                        "name": "Widget",
                        "quantity": 3,
                        "unit_price": 29.99,
                    },
                    {
                        "product_id": "prod-456",
                        "name": "Gadget",
                        "quantity": 1,
                        "unit_price": 99.99,
                    },
                ],
                "subtotal": 189.96,
                "tax": 18.00,
                "total": 207.96,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T14:30:00Z",
            },
        )

        assert "items" in snapshot.snapshot_data
        assert len(snapshot.snapshot_data["items"]) == 2
        assert snapshot.snapshot_data["total"] == 207.96
        assert snapshot.aggregate_version == 25


class TestEventStoreModelsIntegration:
    """Integration tests for event store models."""

    def test_event_entry_and_snapshot_have_same_aggregate_id(self):
        """Event entry and snapshot can reference the same aggregate."""
        aggregate_id = uuid4()

        entry = EventStoreEntry(
            event_id=uuid4(),
            event_type="user.created",
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=1,
            event_data={"email": "test@example.com"},
            occurred_at=datetime.now(UTC),
        )

        snapshot = EventStoreSnapshot(
            id=uuid4(),
            aggregate_type="User",
            aggregate_id=aggregate_id,
            aggregate_version=50,
            snapshot_data={"email": "test@example.com", "total_events": 50},
        )

        assert entry.aggregate_id == snapshot.aggregate_id
        assert entry.aggregate_type == snapshot.aggregate_type

    def test_multiple_events_for_same_aggregate(self):
        """Multiple events can exist for the same aggregate with increasing versions."""
        aggregate_id = uuid4()

        events = [
            EventStoreEntry(
                event_id=uuid4(),
                event_type="user.created",
                aggregate_type="User",
                aggregate_id=aggregate_id,
                aggregate_version=1,
                event_data={"email": "user@example.com"},
                occurred_at=datetime.now(UTC),
            ),
            EventStoreEntry(
                event_id=uuid4(),
                event_type="user.updated",
                aggregate_type="User",
                aggregate_id=aggregate_id,
                aggregate_version=2,
                event_data={"email": "newemail@example.com"},
                occurred_at=datetime.now(UTC),
            ),
            EventStoreEntry(
                event_id=uuid4(),
                event_type="user.deleted",
                aggregate_type="User",
                aggregate_id=aggregate_id,
                aggregate_version=3,
                event_data={},
                occurred_at=datetime.now(UTC),
            ),
        ]

        assert all(e.aggregate_id == aggregate_id for e in events)
        assert [e.aggregate_version for e in events] == [1, 2, 3]
        assert [e.event_type for e in events] == [
            "user.created",
            "user.updated",
            "user.deleted",
        ]
