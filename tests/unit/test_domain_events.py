"""Tests for domain event system.

Tests the event bus, event publishing, and event handling.
"""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.domain.events import (
    EventBus,
    UserCreatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
    UserUpdatedEvent,
    get_event_bus,
    reset_event_bus,
)


class TestDomainEvent:
    """Tests for DomainEvent base class."""

    def test_domain_event_creation(self) -> None:
        """Test creating a domain event."""
        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        assert event.user_id == user_id
        assert event.email == "test@example.com"
        assert event.aggregate_id == user_id
        assert event.event_id is not None
        assert isinstance(event.occurred_at, datetime)

    def test_domain_event_immutability(self) -> None:
        """Test that events are immutable."""
        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        with pytest.raises((AttributeError, ValueError)):
            event.email = "changed@example.com"  # type: ignore

    def test_event_type_property(self) -> None:
        """Test event_type property returns class name."""
        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        assert event.event_type == "UserCreatedEvent"

    def test_event_to_dict(self) -> None:
        """Test converting event to dictionary."""
        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        data = event.to_dict()

        assert data["event_type"] == "UserCreatedEvent"
        assert "user_id" in data
        assert "email" in data
        assert "occurred_at" in data

    def test_event_str_repr(self) -> None:
        """Test string representations of event."""
        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        event_str = str(event)
        event_repr = repr(event)

        assert "UserCreatedEvent" in event_str
        assert str(user_id) in event_str
        assert "UserCreatedEvent" in event_repr


class TestEventBus:
    """Tests for EventBus."""

    def test_event_bus_creation(self) -> None:
        """Test creating an event bus."""
        bus = EventBus()

        assert bus is not None
        metrics = bus.get_metrics()
        assert metrics["published"] == 0
        assert metrics["handled"] == 0

    def test_subscribe_with_decorator(self) -> None:
        """Test subscribing to events with decorator."""
        bus = EventBus()
        handler_called = []

        @bus.subscribe(UserCreatedEvent)
        async def handler(event: UserCreatedEvent) -> None:
            handler_called.append(event)

        handlers = bus.get_handlers(UserCreatedEvent)
        assert len(handlers) == 1
        assert handlers[0] == handler

    def test_subscribe_multiple_handlers(self) -> None:
        """Test multiple handlers for same event."""
        bus = EventBus()

        @bus.subscribe(UserCreatedEvent)
        async def handler1(event: UserCreatedEvent) -> None:
            pass

        @bus.subscribe(UserCreatedEvent)
        async def handler2(event: UserCreatedEvent) -> None:
            pass

        handlers = bus.get_handlers(UserCreatedEvent)
        assert len(handlers) == 2

    def test_unsubscribe_handler(self) -> None:
        """Test unsubscribing a handler."""
        bus = EventBus()

        @bus.subscribe(UserCreatedEvent)
        async def handler(event: UserCreatedEvent) -> None:
            pass

        assert len(bus.get_handlers(UserCreatedEvent)) == 1

        result = bus.unsubscribe(UserCreatedEvent, handler)
        assert result is True
        assert len(bus.get_handlers(UserCreatedEvent)) == 0

    def test_unsubscribe_nonexistent_handler(self) -> None:
        """Test unsubscribing handler that doesn't exist."""
        bus = EventBus()

        async def handler(event: UserCreatedEvent) -> None:
            pass

        result = bus.unsubscribe(UserCreatedEvent, handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_event(self) -> None:
        """Test publishing an event."""
        bus = EventBus()
        handler_called = []

        @bus.subscribe(UserCreatedEvent)
        async def handler(event: UserCreatedEvent) -> None:
            handler_called.append(event)

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        await bus.publish(event)

        # Give handlers time to run
        await asyncio.sleep(0.01)

        assert len(handler_called) == 1
        assert handler_called[0] == event

    @pytest.mark.asyncio
    async def test_publish_to_multiple_handlers(self) -> None:
        """Test publishing to multiple handlers."""
        bus = EventBus()
        handler1_called = []
        handler2_called = []

        @bus.subscribe(UserCreatedEvent)
        async def handler1(event: UserCreatedEvent) -> None:
            handler1_called.append(event)

        @bus.subscribe(UserCreatedEvent)
        async def handler2(event: UserCreatedEvent) -> None:
            handler2_called.append(event)

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        await bus.publish(event)
        await asyncio.sleep(0.01)

        assert len(handler1_called) == 1
        assert len(handler2_called) == 1

    @pytest.mark.asyncio
    async def test_publish_with_no_handlers(self) -> None:
        """Test publishing event with no subscribers (should not error)."""
        bus = EventBus()

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        # Should not raise exception
        await bus.publish(event)

    @pytest.mark.asyncio
    async def test_handler_error_isolation(self) -> None:
        """Test that handler error doesn't affect other handlers."""
        bus = EventBus()
        handler2_called = []

        @bus.subscribe(UserCreatedEvent)
        async def failing_handler(event: UserCreatedEvent) -> None:
            raise ValueError("Handler failed")

        @bus.subscribe(UserCreatedEvent)
        async def successful_handler(event: UserCreatedEvent) -> None:
            handler2_called.append(event)

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        await bus.publish(event)
        await asyncio.sleep(0.01)

        # Second handler should still be called despite first handler failing
        assert len(handler2_called) == 1

        # Metrics should show one failed
        metrics = bus.get_metrics()
        assert metrics["failed"] >= 1

    @pytest.mark.asyncio
    async def test_sync_handler_support(self) -> None:
        """Test that synchronous handlers work."""
        bus = EventBus()
        handler_called = []

        @bus.subscribe(UserCreatedEvent)
        def sync_handler(event: UserCreatedEvent) -> None:
            """Synchronous handler (not async)."""
            handler_called.append(event)

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        await bus.publish(event)
        await asyncio.sleep(0.01)

        assert len(handler_called) == 1

    def test_event_bus_metrics(self) -> None:
        """Test event bus metrics tracking."""
        bus = EventBus()

        @bus.subscribe(UserCreatedEvent)
        async def handler(event: UserCreatedEvent) -> None:
            pass

        metrics = bus.get_metrics()
        assert metrics["published"] == 0
        assert metrics["handled"] == 0
        assert metrics["handler_count"] == 1
        assert metrics["event_types"] == 1

    def test_clear_handlers_specific_type(self) -> None:
        """Test clearing handlers for specific event type."""
        bus = EventBus()

        @bus.subscribe(UserCreatedEvent)
        async def handler1(event: UserCreatedEvent) -> None:
            pass

        @bus.subscribe(UserDeletedEvent)
        async def handler2(event: UserDeletedEvent) -> None:
            pass

        bus.clear_handlers(UserCreatedEvent)

        assert len(bus.get_handlers(UserCreatedEvent)) == 0
        assert len(bus.get_handlers(UserDeletedEvent)) == 1

    def test_clear_all_handlers(self) -> None:
        """Test clearing all handlers."""
        bus = EventBus()

        @bus.subscribe(UserCreatedEvent)
        async def handler1(event: UserCreatedEvent) -> None:
            pass

        @bus.subscribe(UserDeletedEvent)
        async def handler2(event: UserDeletedEvent) -> None:
            pass

        bus.clear_handlers()

        assert len(bus.get_handlers(UserCreatedEvent)) == 0
        assert len(bus.get_handlers(UserDeletedEvent)) == 0

    def test_event_history_tracking(self) -> None:
        """Test event history tracking."""
        bus = EventBus(track_history=True)

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        asyncio.run(bus.publish(event))

        history = bus.get_event_history()
        assert len(history) == 1
        assert history[0] == event

    def test_event_history_disabled(self) -> None:
        """Test that history is not tracked when disabled."""
        bus = EventBus(track_history=False)

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
        )

        asyncio.run(bus.publish(event))

        history = bus.get_event_history()
        assert len(history) == 0


class TestGlobalEventBus:
    """Tests for global event bus singleton."""

    def test_get_event_bus(self) -> None:
        """Test getting global event bus."""
        reset_event_bus()  # Ensure clean state

        bus1 = get_event_bus()
        bus2 = get_event_bus()

        # Should be same instance (singleton)
        assert bus1 is bus2

    def test_reset_event_bus(self) -> None:
        """Test resetting global event bus."""
        bus1 = get_event_bus()

        reset_event_bus()

        bus2 = get_event_bus()

        # Should be different instances
        assert bus1 is not bus2


class TestUserEvents:
    """Tests for user-specific events."""

    def test_user_created_event(self) -> None:
        """Test UserCreatedEvent creation."""
        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
            full_name="Test User",
        )

        assert event.user_id == user_id
        assert event.email == "test@example.com"
        assert event.username == "testuser"
        assert event.full_name == "Test User"

    def test_user_updated_event(self) -> None:
        """Test UserUpdatedEvent creation."""
        user_id = uuid4()
        event = UserUpdatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            changed_fields=["email", "full_name"],
            previous_values={"email": "old@example.com"},
        )

        assert event.user_id == user_id
        assert "email" in event.changed_fields
        assert event.previous_values is not None

    def test_user_deleted_event(self) -> None:
        """Test UserDeletedEvent creation."""
        user_id = uuid4()
        deleted_at = datetime.now(UTC)
        event = UserDeletedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
            deleted_at=deleted_at,
            soft_delete=True,
        )

        assert event.user_id == user_id
        assert event.deleted_at == deleted_at
        assert event.soft_delete is True

    def test_user_restored_event(self) -> None:
        """Test UserRestoredEvent creation."""
        user_id = uuid4()
        restored_at = datetime.now(UTC)
        event = UserRestoredEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
            restored_at=restored_at,
        )

        assert event.user_id == user_id
        assert event.restored_at == restored_at


class TestEventRegistry:
    """Tests for event registry functionality."""

    def test_get_event_class_for_registered_event(self):
        """Can retrieve event class for registered event type."""
        from src.domain.events import get_event_class

        event_class = get_event_class("user.created")
        assert event_class == UserCreatedEvent

    def test_get_event_class_raises_for_unregistered_event(self):
        """get_event_class raises KeyError for unregistered type."""
        from src.domain.events import get_event_class

        with pytest.raises(KeyError) as exc_info:
            get_event_class("unregistered.event")

        assert "unregistered.event" in str(exc_info.value)
        assert "not registered" in str(exc_info.value)

    def test_register_event_decorator(self):
        """register_event decorator adds event to registry."""
        from uuid import UUID

        from pydantic import Field

        from src.domain.events import DomainEvent, get_event_class, register_event

        @register_event("test.custom_event")
        class CustomEvent(DomainEvent):
            test_field: str = Field(...)

            @property
            def aggregate_id(self) -> UUID:
                return self.event_id

        # Should be able to retrieve it
        event_class = get_event_class("test.custom_event")
        assert event_class == CustomEvent

        # Clean up
        from src.domain.events import EVENT_REGISTRY

        del EVENT_REGISTRY["test.custom_event"]

    def test_all_user_events_are_registered(self):
        """All user events are registered in the registry."""
        from src.domain.events import get_event_class

        event_types = [
            ("user.created", UserCreatedEvent),
            ("user.updated", UserUpdatedEvent),
            ("user.deleted", UserDeletedEvent),
            ("user.restored", UserRestoredEvent),
        ]

        for event_type, expected_class in event_types:
            event_class = get_event_class(event_type)
            assert event_class == expected_class

    def test_event_registry_is_dict(self):
        """EVENT_REGISTRY is a dict mapping strings to classes."""
        from src.domain.events import EVENT_REGISTRY

        assert isinstance(EVENT_REGISTRY, dict)
        assert len(EVENT_REGISTRY) >= 4  # At least our 4 user events
        assert all(isinstance(k, str) for k in EVENT_REGISTRY)
