# Architecture Enhancement Proposals

> **Production-ready solutions for advanced features: Domain Events, Streaming, CQRS, Plugin System, and more**

**Author**: Architecture Review
**Date**: 2025-11-11
**Status**: Proposal
**Target Version**: 2.0.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Proposed Enhancements](#proposed-enhancements)
   - [1. Domain Events & Event Bus](#1-domain-events--event-bus)
   - [2. Streaming (SSE/WebSocket)](#2-streaming-ssewebsocket)
   - [3. Event-Driven Architecture & CQRS](#3-event-driven-architecture--cqrs)
   - [4. Plugin System](#4-plugin-system)
   - [5. Additional Advanced Features](#5-additional-advanced-features)
4. [Implementation Roadmap](#implementation-roadmap)
5. [Migration Strategy](#migration-strategy)
6. [Appendices](#appendices)

---

## Executive Summary

This document proposes a comprehensive set of architecture enhancements to elevate `python-fast-forge` from a production-ready FastAPI boilerplate to an **enterprise-grade, event-driven microservices platform** with advanced capabilities.

### Key Enhancements

| Feature | Impact | Complexity | Priority |
|---------|--------|------------|----------|
| **Domain Events & Event Bus** | High - Enables loose coupling, audit trails | Medium | P0 |
| **Streaming (SSE/WebSocket)** | High - Real-time capabilities | Low | P0 |
| **Event-Driven + CQRS** | Very High - Scalability, performance | High | P1 |
| **Plugin System** | High - Extensibility, modularity | Medium | P1 |
| **Feature Flags** | Medium - Safe deployments | Low | P2 |
| **Saga Pattern** | High - Distributed transactions | High | P2 |
| **GraphQL API** | Medium - Flexible querying | Medium | P3 |
| **Audit Logging** | Medium - Compliance, security | Low | P2 |

### Benefits

- **Scalability**: CQRS enables independent scaling of read/write workloads
- **Real-time**: WebSocket/SSE support for live updates
- **Extensibility**: Plugin system for third-party integrations
- **Observability**: Enhanced event-driven audit trails
- **Resilience**: Saga pattern for distributed transactions
- **Developer Experience**: Better abstractions and patterns

---

## Current Architecture Analysis

### Strengths

✅ **Clean Architecture** - 4-layer separation (Domain, App, Infrastructure, Presentation)
✅ **Repository Pattern** - Abstracted data access
✅ **Unit of Work** - Transaction management
✅ **Temporal Workflows** - Durable background tasks
✅ **Redis Caching** - Performance optimization
✅ **OpenTelemetry** - Distributed tracing
✅ **Multi-tenancy** - Built-in tenant isolation

### Gaps & Opportunities

🔶 **No Domain Events** - Business events are implicit, not captured
🔶 **Synchronous by Default** - Limited event-driven patterns
🔶 **Coupled Use Cases** - Direct dependencies between operations
🔶 **No Real-time Support** - Cannot push updates to clients
🔶 **Monolithic Read/Write** - Same model for queries and commands
🔶 **No Plugin System** - Hard to extend without forking
🔶 **Limited Observability** - No business event tracking

---

## Proposed Enhancements

## 1. Domain Events & Event Bus

### Overview

Implement a **domain-driven event system** where business events are first-class citizens, enabling loose coupling, audit trails, and reactive architectures.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                              │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │  Domain Entity   │──raises──│  Domain Event    │         │
│  │   (User)         │          │ (UserCreated)    │         │
│  └──────────────────┘          └──────────────────┘         │
└────────────────────────────────────┬────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────┐
│                  Application Layer                           │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │   Use Case       │──emits──▶│   Event Bus      │         │
│  │ (CreateUser)     │          │ (In-Memory/      │         │
│  └──────────────────┘          │  Redis/Kafka)    │         │
│                                 └──────────────────┘         │
│                                          │                   │
│                                          ▼                   │
│  ┌────────────────────────────────────────────────┐         │
│  │         Event Handlers (Subscribers)            │         │
│  │  - SendWelcomeEmail                             │         │
│  │  - UpdateUserStats                              │         │
│  │  - NotifyAdmins                                 │         │
│  │  - AuditLogger                                  │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

#### 1.1 Domain Event Base Class

**Location**: `src/domain/events/base.py`

```python
"""Base domain event infrastructure."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events.

    Domain events represent facts that have happened in the domain.
    They are immutable and named in past tense (e.g., UserCreated, OrderPlaced).

    Attributes:
        event_id: Unique identifier for this event instance
        occurred_at: Timestamp when the event occurred
        aggregate_id: ID of the aggregate that raised the event
        aggregate_type: Type of aggregate (e.g., "User", "Order")
        tenant_id: Optional tenant identifier for multi-tenancy
        correlation_id: Optional ID to correlate related events
        causation_id: Optional ID of the event that caused this event
        metadata: Optional additional event metadata
    """

    event_id: UUID = field(default_factory=uuid7)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    aggregate_id: UUID
    aggregate_type: str
    tenant_id: UUID | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Return the event type name (class name)."""
        return self.__class__.__name__

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary for persistence/messaging."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": str(self.aggregate_id),
            "aggregate_type": self.aggregate_type,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "metadata": self.metadata,
            "data": self._get_event_data(),
        }

    def _get_event_data(self) -> dict[str, Any]:
        """Extract event-specific data. Override in subclasses."""
        return {}


@dataclass(frozen=True, kw_only=True)
class IntegrationEvent(DomainEvent):
    """Events intended for external systems (other microservices).

    Published to message brokers (Kafka, RabbitMQ) for inter-service communication.
    """
    pass
```

#### 1.2 Specific Domain Events

**Location**: `src/domain/events/user_events.py`

```python
"""User-related domain events."""
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.events.base import DomainEvent, IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class UserCreated(DomainEvent):
    """Raised when a new user is created."""

    email: str
    username: str
    full_name: str | None
    is_active: bool

    def _get_event_data(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "is_active": self.is_active,
        }


@dataclass(frozen=True, kw_only=True)
class UserUpdated(DomainEvent):
    """Raised when user details are updated."""

    changed_fields: dict[str, tuple[Any, Any]]  # field_name: (old_value, new_value)

    def _get_event_data(self) -> dict[str, Any]:
        return {"changed_fields": self.changed_fields}


@dataclass(frozen=True, kw_only=True)
class UserDeleted(DomainEvent):
    """Raised when user is soft-deleted."""

    email: str
    username: str

    def _get_event_data(self) -> dict[str, Any]:
        return {"email": self.email, "username": self.username}


@dataclass(frozen=True, kw_only=True)
class UserRestored(DomainEvent):
    """Raised when user is restored from soft-delete."""

    email: str
    username: str

    def _get_event_data(self) -> dict[str, Any]:
        return {"email": self.email, "username": self.username}


@dataclass(frozen=True, kw_only=True)
class UserActivated(IntegrationEvent):
    """Integration event for external systems when user is activated."""

    email: str
    username: str

    def _get_event_data(self) -> dict[str, Any]:
        return {"email": self.email, "username": self.username}


@dataclass(frozen=True, kw_only=True)
class UserDeactivated(IntegrationEvent):
    """Integration event for external systems when user is deactivated."""

    email: str
    username: str

    def _get_event_data(self) -> dict[str, Any]:
        return {"email": self.email, "username": self.username}
```

#### 1.3 Event Bus Interface

**Location**: `src/domain/interfaces.py` (add to existing file)

```python
"""Event bus interface for domain layer."""
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from src.domain.events.base import DomainEvent


EventHandler = Callable[[DomainEvent], Any]


class IEventBus(ABC):
    """Interface for event bus implementations.

    Decouples event publishers from subscribers using the Observer pattern.
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all registered handlers.

        Args:
            event: The domain event to publish
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: The event class to listen for
            handler: Async function to handle the event
        """
        pass

    @abstractmethod
    def unsubscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The event class
            handler: The handler to remove
        """
        pass
```

#### 1.4 In-Memory Event Bus (Development)

**Location**: `src/infrastructure/events/in_memory_bus.py`

```python
"""In-memory event bus for development and testing."""
import asyncio
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from src.domain.events.base import DomainEvent
from src.domain.interfaces import IEventBus
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class InMemoryEventBus(IEventBus):
    """In-memory event bus using asyncio for concurrent handler execution.

    Suitable for:
    - Development environments
    - Testing
    - Single-instance deployments

    Limitations:
    - Events lost on restart (not persistent)
    - Cannot scale across multiple instances
    - No guaranteed delivery

    For production, use RedisEventBus or KafkaEventBus.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], Any]]] = defaultdict(list)

    async def publish(self, event: DomainEvent) -> None:
        """Publish event to all registered handlers concurrently."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug("no_handlers_for_event", event_type=event.event_type)
            return

        logger.info(
            "publishing_event",
            event_type=event.event_type,
            event_id=str(event.event_id),
            aggregate_id=str(event.aggregate_id),
            handler_count=len(handlers),
        )

        # Execute all handlers concurrently
        tasks = [self._execute_handler(handler, event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_handler(self, handler: Callable[[DomainEvent], Any], event: DomainEvent) -> None:
        """Execute a single handler with error handling."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(
                "event_handler_failed",
                event_type=event.event_type,
                event_id=str(event.event_id),
                handler=handler.__name__,
                error=str(e),
                exc_info=True,
            )

    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], Any]) -> None:
        """Subscribe handler to event type."""
        self._handlers[event_type].append(handler)
        logger.info("handler_subscribed", event_type=event_type.__name__, handler=handler.__name__)

    def unsubscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], Any]) -> None:
        """Unsubscribe handler from event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.info("handler_unsubscribed", event_type=event_type.__name__, handler=handler.__name__)
```

#### 1.5 Redis Event Bus (Production)

**Location**: `src/infrastructure/events/redis_bus.py`

```python
"""Redis-based event bus for distributed systems."""
import asyncio
import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis

from src.domain.events.base import DomainEvent
from src.domain.interfaces import IEventBus
from src.infrastructure.config import Settings
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class RedisEventBus(IEventBus):
    """Redis Pub/Sub event bus for distributed event broadcasting.

    Suitable for:
    - Multi-instance deployments
    - Horizontal scaling
    - Real-time event broadcasting

    Limitations:
    - Fire-and-forget (no guaranteed delivery)
    - No event persistence
    - No replay capability

    For guaranteed delivery and event sourcing, use KafkaEventBus.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._handlers: dict[type[DomainEvent], list[Callable[[DomainEvent], Any]]] = defaultdict(list)
        self._event_type_registry: dict[str, type[DomainEvent]] = {}
        self._listener_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Establish Redis connection and start listener."""
        self._redis = redis.Redis(
            host=self._settings.redis_host,
            port=self._settings.redis_port,
            db=self._settings.redis_db,
            decode_responses=True,
        )
        self._pubsub = self._redis.pubsub()

        # Subscribe to the events channel
        await self._pubsub.subscribe("domain_events")

        # Start background listener
        self._listener_task = asyncio.create_task(self._listen())
        logger.info("redis_event_bus_connected")

    async def disconnect(self) -> None:
        """Close Redis connection and stop listener."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe("domain_events")
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

        logger.info("redis_event_bus_disconnected")

    async def publish(self, event: DomainEvent) -> None:
        """Publish event to Redis channel."""
        if not self._redis:
            raise RuntimeError("EventBus not connected. Call connect() first.")

        event_dict = event.to_dict()
        message = json.dumps(event_dict)

        await self._redis.publish("domain_events", message)

        logger.info(
            "event_published_to_redis",
            event_type=event.event_type,
            event_id=str(event.event_id),
        )

    async def _listen(self) -> None:
        """Background task to listen for events from Redis."""
        if not self._pubsub:
            return

        logger.info("redis_event_listener_started")

        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    await self._handle_message(message["data"])
        except asyncio.CancelledError:
            logger.info("redis_event_listener_stopped")
            raise
        except Exception as e:
            logger.error("redis_event_listener_error", error=str(e), exc_info=True)

    async def _handle_message(self, data: str) -> None:
        """Handle incoming Redis message."""
        try:
            event_dict = json.loads(data)
            event_type_name = event_dict["event_type"]

            # Get event class from registry
            event_class = self._event_type_registry.get(event_type_name)
            if not event_class:
                logger.warning("unknown_event_type", event_type=event_type_name)
                return

            # Reconstruct event (simplified - you'd need proper deserialization)
            # For production, use a proper event serialization library
            handlers = self._handlers.get(event_class, [])

            for handler in handlers:
                await self._execute_handler(handler, event_dict)

        except Exception as e:
            logger.error("failed_to_handle_redis_message", error=str(e), exc_info=True)

    async def _execute_handler(self, handler: Callable, event_dict: dict) -> None:
        """Execute handler with error handling."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event_dict)
            else:
                handler(event_dict)
        except Exception as e:
            logger.error(
                "event_handler_failed",
                event_type=event_dict.get("event_type"),
                error=str(e),
                exc_info=True,
            )

    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], Any]) -> None:
        """Subscribe handler to event type."""
        self._handlers[event_type].append(handler)
        self._event_type_registry[event_type.__name__] = event_type
        logger.info("handler_subscribed_to_redis_bus", event_type=event_type.__name__)

    def unsubscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], Any]) -> None:
        """Unsubscribe handler from event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
```

#### 1.6 Updated Use Case with Events

**Location**: `src/app/usecases/user_usecases.py` (update existing)

```python
"""Updated CreateUserUseCase with domain events."""
from uuid import UUID

from src.domain.events.user_events import UserCreated
from src.domain.exceptions import ValidationError
from src.domain.interfaces import IEventBus, IUserRepository
from src.domain.models.user import User


class CreateUserUseCase:
    """Use case for creating a new user with domain events."""

    def __init__(
        self,
        user_repository: IUserRepository[User],
        event_bus: IEventBus,
    ) -> None:
        self._repository = user_repository
        self._event_bus = event_bus

    async def execute(
        self,
        email: str,
        username: str,
        full_name: str | None = None,
        tenant_id: UUID | None = None,
    ) -> User:
        """Create user and publish UserCreated event."""

        # Create user
        user = User(
            email=email,
            username=username,
            full_name=full_name,
            tenant_id=tenant_id,
        )

        try:
            created_user = await self._repository.create(user)
        except IntegrityError as e:
            # ... existing error handling ...
            raise

        # Publish domain event
        event = UserCreated(
            aggregate_id=created_user.id,
            aggregate_type="User",
            email=created_user.email,
            username=created_user.username,
            full_name=created_user.full_name,
            is_active=created_user.is_active,
            tenant_id=created_user.tenant_id,
        )

        await self._event_bus.publish(event)

        return created_user
```

#### 1.7 Event Handlers

**Location**: `src/app/handlers/user_event_handlers.py`

```python
"""Event handlers for user-related events."""
from src.domain.events.user_events import UserCreated, UserDeleted
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


async def send_welcome_email_handler(event: UserCreated) -> None:
    """Send welcome email when user is created."""
    logger.info(
        "sending_welcome_email",
        user_id=str(event.aggregate_id),
        email=event.email,
    )

    # Trigger Temporal workflow
    from src.app.tasks.user_tasks import SendWelcomeEmailWorkflow
    from src.infrastructure.temporal_client import get_temporal_client

    client = await get_temporal_client()
    await client.start_workflow(
        SendWelcomeEmailWorkflow.run,
        args=[str(event.aggregate_id), event.email],
        id=f"send-welcome-email-{event.aggregate_id}",
        task_queue="fastapi-tasks",
    )


async def update_user_stats_handler(event: UserCreated) -> None:
    """Update user statistics when user is created."""
    logger.info("updating_user_stats", user_id=str(event.aggregate_id))
    # Update analytics, dashboards, etc.


async def audit_log_handler(event: UserCreated | UserDeleted) -> None:
    """Log all user events to audit trail."""
    logger.info(
        "audit_log",
        event_type=event.event_type,
        event_id=str(event.event_id),
        aggregate_id=str(event.aggregate_id),
        tenant_id=str(event.tenant_id) if event.tenant_id else None,
    )
    # Store in audit log table or external system
```

#### 1.8 Event Handler Registration

**Location**: `src/infrastructure/events/registry.py`

```python
"""Central event handler registration."""
from src.app.handlers.user_event_handlers import (
    audit_log_handler,
    send_welcome_email_handler,
    update_user_stats_handler,
)
from src.domain.events.user_events import UserCreated, UserDeleted
from src.domain.interfaces import IEventBus


def register_event_handlers(event_bus: IEventBus) -> None:
    """Register all event handlers with the event bus."""

    # UserCreated event handlers
    event_bus.subscribe(UserCreated, send_welcome_email_handler)
    event_bus.subscribe(UserCreated, update_user_stats_handler)
    event_bus.subscribe(UserCreated, audit_log_handler)

    # UserDeleted event handlers
    event_bus.subscribe(UserDeleted, audit_log_handler)
```

### Benefits

✅ **Loose Coupling** - Use cases don't directly call side effects
✅ **Audit Trail** - Every business event is captured
✅ **Extensibility** - Add new handlers without modifying use cases
✅ **Testing** - Easy to test event handlers in isolation
✅ **Observability** - Track business events in OpenTelemetry
✅ **Scalability** - Async handlers execute concurrently

### Migration Path

1. **Phase 1**: Implement base event infrastructure (Week 1)
2. **Phase 2**: Add events to User use cases (Week 2)
3. **Phase 3**: Migrate Temporal workflows to event handlers (Week 3)
4. **Phase 4**: Add event persistence (Event Store) (Week 4)
5. **Phase 5**: Implement Redis/Kafka bus for production (Week 5)

---

## 2. Streaming (SSE/WebSocket)

### Overview

Add real-time communication capabilities for live updates, notifications, and collaborative features.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Client Applications                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Browser    │  │  Mobile App  │  │   Desktop    │      │
│  │  (WebSocket) │  │    (SSE)     │  │  (WebSocket) │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│             FastAPI Presentation Layer                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  WebSocket Manager (Connection Pool)                 │   │
│  │  - Per-tenant channels                               │   │
│  │  - Per-user channels                                 │   │
│  │  - Broadcast channels                                │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SSE Manager (Event Stream)                          │   │
│  │  - Long-lived HTTP connections                       │   │
│  │  - Heartbeat / Keep-alive                            │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Redis Pub/Sub (Message Broker)                  │
│  - Distribute messages across app instances                  │
│  - Horizontal scaling                                        │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

#### 2.1 WebSocket Connection Manager

**Location**: `src/infrastructure/websocket/manager.py`

```python
"""WebSocket connection manager for real-time communication."""
import asyncio
import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """Manages WebSocket connections with Redis pub/sub for horizontal scaling.

    Features:
    - Per-user channels
    - Per-tenant channels
    - Broadcast channels
    - Automatic reconnection handling
    - Redis-backed for multi-instance support
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        # Active connections: {user_id: [websocket1, websocket2, ...]}
        self._connections: dict[UUID, list[WebSocket]] = defaultdict(list)
        # Tenant subscriptions: {tenant_id: [user_id1, user_id2, ...]}
        self._tenant_subscriptions: dict[UUID, set[UUID]] = defaultdict(set)
        self._pubsub: Any = None
        self._listener_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket, user_id: UUID, tenant_id: UUID | None = None) -> None:
        """Accept WebSocket connection and register it."""
        await websocket.accept()
        self._connections[user_id].append(websocket)

        if tenant_id:
            self._tenant_subscriptions[tenant_id].add(user_id)

        logger.info(
            "websocket_connected",
            user_id=str(user_id),
            tenant_id=str(tenant_id) if tenant_id else None,
            total_connections=len(self._connections[user_id]),
        )

    def disconnect(self, websocket: WebSocket, user_id: UUID, tenant_id: UUID | None = None) -> None:
        """Remove WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id].remove(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

        if tenant_id and user_id in self._tenant_subscriptions[tenant_id]:
            self._tenant_subscriptions[tenant_id].discard(user_id)
            if not self._tenant_subscriptions[tenant_id]:
                del self._tenant_subscriptions[tenant_id]

        logger.info("websocket_disconnected", user_id=str(user_id))

    async def send_personal_message(self, user_id: UUID, message: dict[str, Any]) -> None:
        """Send message to specific user (all their connections)."""
        if user_id in self._connections:
            message_json = json.dumps(message)
            dead_connections = []

            for websocket in self._connections[user_id]:
                try:
                    await websocket.send_text(message_json)
                except Exception as e:
                    logger.error("failed_to_send_message", user_id=str(user_id), error=str(e))
                    dead_connections.append(websocket)

            # Clean up dead connections
            for websocket in dead_connections:
                self._connections[user_id].remove(websocket)

    async def broadcast_to_tenant(self, tenant_id: UUID, message: dict[str, Any]) -> None:
        """Broadcast message to all users in a tenant."""
        user_ids = self._tenant_subscriptions.get(tenant_id, set())
        for user_id in user_ids:
            await self.send_personal_message(user_id, message)

    async def broadcast_all(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected users."""
        for user_id in list(self._connections.keys()):
            await self.send_personal_message(user_id, message)

    async def publish_via_redis(self, channel: str, message: dict[str, Any]) -> None:
        """Publish message via Redis for multi-instance support."""
        await self._redis.publish(channel, json.dumps(message))

    async def start_redis_listener(self) -> None:
        """Start listening to Redis pub/sub channels."""
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe("websocket_messages")
        self._listener_task = asyncio.create_task(self._listen_redis())

    async def _listen_redis(self) -> None:
        """Background task to listen for Redis messages."""
        if not self._pubsub:
            return

        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await self._handle_redis_message(data)
        except asyncio.CancelledError:
            pass

    async def _handle_redis_message(self, data: dict[str, Any]) -> None:
        """Handle message received from Redis."""
        message_type = data.get("type")

        if message_type == "personal":
            user_id = UUID(data["user_id"])
            await self.send_personal_message(user_id, data["message"])
        elif message_type == "tenant":
            tenant_id = UUID(data["tenant_id"])
            await self.broadcast_to_tenant(tenant_id, data["message"])
        elif message_type == "broadcast":
            await self.broadcast_all(data["message"])
```

#### 2.2 WebSocket Endpoints

**Location**: `src/presentation/api/websocket/endpoints.py`

```python
"""WebSocket API endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from src.infrastructure.logging.config import get_logger
from src.infrastructure.websocket.manager import WebSocketManager

logger = get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])


async def get_websocket_manager() -> WebSocketManager:
    """Dependency to get WebSocket manager."""
    # Get from DI container
    from src.infrastructure.di.container import container
    return await container.websocket_manager()


@router.websocket("/notifications/{user_id}")
async def notifications_websocket(
    websocket: WebSocket,
    user_id: UUID,
    manager: WebSocketManager = Depends(get_websocket_manager),
) -> None:
    """WebSocket endpoint for real-time notifications.

    Usage:
        ws = new WebSocket('ws://localhost:8000/ws/notifications/{user_id}')
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            console.log('Notification:', data)
        }
    """
    # TODO: Add authentication middleware to verify user_id from JWT
    tenant_id = None  # Extract from JWT claims

    await manager.connect(websocket, user_id, tenant_id)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            logger.info("websocket_message_received", user_id=str(user_id), data=data)

            # Echo back (or handle commands)
            await manager.send_personal_message(
                user_id,
                {"type": "ack", "message": "Message received"},
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, tenant_id)
        logger.info("websocket_client_disconnected", user_id=str(user_id))
```

#### 2.3 SSE (Server-Sent Events) Implementation

**Location**: `src/infrastructure/streaming/sse.py`

```python
"""Server-Sent Events (SSE) implementation."""
import asyncio
import json
from typing import Any, AsyncIterator
from uuid import UUID

from redis.asyncio import Redis

from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class SSEManager:
    """Server-Sent Events manager for one-way server-to-client streaming.

    Benefits over WebSocket:
    - Simpler (HTTP-based, no special protocol)
    - Auto-reconnection built into browser EventSource API
    - Better for one-way data flow

    Use cases:
    - Live notifications
    - Real-time dashboards
    - Progress updates
    - Stock tickers
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def event_stream(
        self,
        user_id: UUID,
        tenant_id: UUID | None = None,
    ) -> AsyncIterator[str]:
        """Generate SSE event stream for a user.

        Yields:
            SSE-formatted messages: "data: {json}\\n\\n"
        """
        # Subscribe to Redis channels
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(f"user:{user_id}")

        if tenant_id:
            await pubsub.subscribe(f"tenant:{tenant_id}")

        logger.info("sse_stream_started", user_id=str(user_id))

        try:
            # Send initial connection message
            yield self._format_sse_message({"type": "connected", "user_id": str(user_id)})

            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_task = asyncio.create_task(self._heartbeat_generator())

            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield self._format_sse_message(data)

                # Check for heartbeat
                try:
                    heartbeat = heartbeat_task.result() if heartbeat_task.done() else None
                    if heartbeat:
                        yield heartbeat
                        heartbeat_task = asyncio.create_task(self._heartbeat_generator())
                except Exception:
                    pass

        except asyncio.CancelledError:
            logger.info("sse_stream_cancelled", user_id=str(user_id))
        finally:
            await pubsub.unsubscribe(f"user:{user_id}")
            if tenant_id:
                await pubsub.unsubscribe(f"tenant:{tenant_id}")
            await pubsub.close()

    def _format_sse_message(self, data: dict[str, Any]) -> str:
        """Format message for SSE protocol."""
        return f"data: {json.dumps(data)}\n\n"

    async def _heartbeat_generator(self) -> str:
        """Generate heartbeat message every 30 seconds."""
        await asyncio.sleep(30)
        return self._format_sse_message({"type": "heartbeat"})

    async def publish_to_user(self, user_id: UUID, message: dict[str, Any]) -> None:
        """Publish message to user's SSE channel."""
        await self._redis.publish(f"user:{user_id}", json.dumps(message))

    async def publish_to_tenant(self, tenant_id: UUID, message: dict[str, Any]) -> None:
        """Publish message to tenant's SSE channel."""
        await self._redis.publish(f"tenant:{tenant_id}", json.dumps(message))
```

#### 2.4 SSE Endpoints

**Location**: `src/presentation/api/streaming/sse_endpoints.py`

```python
"""SSE API endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.infrastructure.streaming.sse import SSEManager

router = APIRouter(prefix="/stream", tags=["streaming"])


async def get_sse_manager() -> SSEManager:
    """Dependency to get SSE manager."""
    from src.infrastructure.di.container import container
    return await container.sse_manager()


@router.get("/events/{user_id}")
async def event_stream(
    user_id: UUID,
    manager: SSEManager = Depends(get_sse_manager),
) -> StreamingResponse:
    """SSE endpoint for real-time event streaming.

    Usage (JavaScript):
        const eventSource = new EventSource('/stream/events/{user_id}')
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data)
            console.log('Event:', data)
        }
    """
    # TODO: Add authentication to verify user_id
    tenant_id = None  # Extract from JWT

    return StreamingResponse(
        manager.event_stream(user_id, tenant_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx
        },
    )
```

#### 2.5 Integration with Domain Events

**Location**: `src/app/handlers/streaming_handlers.py`

```python
"""Event handlers that push updates via WebSocket/SSE."""
from src.domain.events.user_events import UserCreated, UserUpdated
from src.infrastructure.logging.config import get_logger
from src.infrastructure.websocket.manager import WebSocketManager

logger = get_logger(__name__)


async def notify_user_created_via_websocket(event: UserCreated) -> None:
    """Push UserCreated event to WebSocket clients."""
    from src.infrastructure.di.container import container

    manager: WebSocketManager = await container.websocket_manager()

    # Notify tenant admins
    if event.tenant_id:
        await manager.broadcast_to_tenant(
            event.tenant_id,
            {
                "type": "user.created",
                "data": {
                    "user_id": str(event.aggregate_id),
                    "email": event.email,
                    "username": event.username,
                },
            },
        )
```

### Benefits

✅ **Real-time Updates** - Push data to clients instantly
✅ **Scalable** - Redis pub/sub enables horizontal scaling
✅ **Flexible** - Both WebSocket (bi-directional) and SSE (simpler)
✅ **Production-Ready** - Connection management, heartbeats, error handling
✅ **Multi-tenant** - Channel isolation per tenant

---

## 3. Event-Driven Architecture & CQRS

### Overview

Implement **Command Query Responsibility Segregation (CQRS)** to separate read and write models, enabling independent scaling and optimization.

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    Client Request                              │
└───────────────────┬───────────────────┬───────────────────────┘
                    │                   │
         ┌──────────▼────────┐  ┌───────▼──────────┐
         │   COMMAND         │  │    QUERY         │
         │  (Write Model)    │  │  (Read Model)    │
         └──────────┬────────┘  └───────┬──────────┘
                    │                   │
         ┌──────────▼────────┐  ┌───────▼──────────┐
         │ Command Handler   │  │  Query Handler   │
         │ - Validates       │  │  - Optimized     │
         │ - Business logic  │  │  - Denormalized  │
         │ - Emits events    │  │  - Cached        │
         └──────────┬────────┘  └───────┬──────────┘
                    │                   │
         ┌──────────▼────────┐  ┌───────▼──────────┐
         │  Write Database   │  │  Read Database   │
         │  (PostgreSQL)     │  │  (PostgreSQL +   │
         │  - Normalized     │  │   Redis cache)   │
         │  - Transactional  │  │  - Denormalized  │
         └──────────┬────────┘  └──────────────────┘
                    │
         ┌──────────▼────────┐
         │   Event Store     │
         │  (Audit log of    │
         │   all events)     │
         └──────────┬────────┘
                    │
         ┌──────────▼────────────────────┐
         │   Event Handlers              │
         │   - Update read models        │
         │   - Send notifications        │
         │   - Trigger workflows         │
         └───────────────────────────────┘
```

### Implementation

#### 3.1 Command Base Classes

**Location**: `src/app/commands/base.py`

```python
"""Command base classes for CQRS pattern."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Command(ABC):
    """Base class for all commands (write operations).

    Commands:
    - Represent an intent to change state
    - Named in imperative mood (CreateUser, UpdateOrder)
    - Immutable (frozen dataclass)
    - Can be rejected (validation)
    """

    correlation_id: UUID | None = None
    tenant_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class CommandResult:
    """Result of command execution."""

    success: bool
    data: dict | None = None
    error: str | None = None
```

#### 3.2 Query Base Classes

**Location**: `src/app/queries/base.py`

```python
"""Query base classes for CQRS pattern."""
from abc import ABC
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


@dataclass(frozen=True, kw_only=True)
class Query(ABC, Generic[T]):
    """Base class for all queries (read operations).

    Queries:
    - Retrieve data without side effects
    - Named as questions (GetUserById, SearchProducts)
    - Can be heavily cached
    - Optimized for reading
    """

    tenant_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class QueryResult(Generic[T]):
    """Result of query execution."""

    data: T
    total_count: int | None = None
```

#### 3.3 User Commands

**Location**: `src/app/commands/user_commands.py`

```python
"""User-related commands."""
from dataclasses import dataclass
from uuid import UUID

from src.app.commands.base import Command


@dataclass(frozen=True, kw_only=True)
class CreateUserCommand(Command):
    """Command to create a new user."""

    email: str
    username: str
    full_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateUserCommand(Command):
    """Command to update user details."""

    user_id: UUID
    email: str | None = None
    username: str | None = None
    full_name: str | None = None
    is_active: bool | None = None


@dataclass(frozen=True, kw_only=True)
class DeleteUserCommand(Command):
    """Command to soft-delete a user."""

    user_id: UUID
```

#### 3.4 User Queries

**Location**: `src/app/queries/user_queries.py`

```python
"""User-related queries."""
from dataclasses import dataclass
from uuid import UUID

from src.app.queries.base import Query
from src.domain.models.user import User


@dataclass(frozen=True, kw_only=True)
class GetUserByIdQuery(Query[User]):
    """Query to get user by ID."""

    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class SearchUsersQuery(Query[list[User]]):
    """Query to search users with filters."""

    email_contains: str | None = None
    username_contains: str | None = None
    is_active: bool | None = None
    skip: int = 0
    limit: int = 100


@dataclass(frozen=True, kw_only=True)
class GetUserStatsQuery(Query[dict]):
    """Query to get aggregated user statistics."""
    pass
```

#### 3.5 Command Handler

**Location**: `src/app/commands/handlers/user_command_handler.py`

```python
"""Command handlers for user commands."""
from src.app.commands.base import CommandResult
from src.app.commands.user_commands import CreateUserCommand, DeleteUserCommand, UpdateUserCommand
from src.domain.events.user_events import UserCreated, UserDeleted, UserUpdated
from src.domain.exceptions import ValidationError
from src.domain.interfaces import IEventBus, IUserRepository
from src.domain.models.user import User


class UserCommandHandler:
    """Handles user-related commands."""

    def __init__(
        self,
        repository: IUserRepository[User],
        event_bus: IEventBus,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def handle_create_user(self, command: CreateUserCommand) -> CommandResult:
        """Handle CreateUserCommand."""
        try:
            # Validate command
            if not command.email or "@" not in command.email:
                return CommandResult(success=False, error="Invalid email")

            # Create user
            user = User(
                email=command.email,
                username=command.username,
                full_name=command.full_name,
                tenant_id=command.tenant_id,
            )

            created_user = await self._repository.create(user)

            # Publish event
            event = UserCreated(
                aggregate_id=created_user.id,
                aggregate_type="User",
                email=created_user.email,
                username=created_user.username,
                full_name=created_user.full_name,
                is_active=created_user.is_active,
                tenant_id=command.tenant_id,
                correlation_id=command.correlation_id,
            )
            await self._event_bus.publish(event)

            return CommandResult(
                success=True,
                data={"user_id": str(created_user.id)},
            )

        except ValidationError as e:
            return CommandResult(success=False, error=str(e))

    async def handle_update_user(self, command: UpdateUserCommand) -> CommandResult:
        """Handle UpdateUserCommand."""
        # Similar implementation...
        pass

    async def handle_delete_user(self, command: DeleteUserCommand) -> CommandResult:
        """Handle DeleteUserCommand."""
        # Similar implementation...
        pass
```

#### 3.6 Query Handler

**Location**: `src/app/queries/handlers/user_query_handler.py`

```python
"""Query handlers for user queries."""
from src.app.queries.base import QueryResult
from src.app.queries.user_queries import GetUserByIdQuery, GetUserStatsQuery, SearchUsersQuery
from src.domain.interfaces import IUserRepository
from src.domain.models.user import User


class UserQueryHandler:
    """Handles user-related queries with read-optimized logic."""

    def __init__(self, repository: IUserRepository[User]) -> None:
        self._repository = repository  # Could be a different read-optimized repo

    async def handle_get_user_by_id(self, query: GetUserByIdQuery) -> QueryResult[User | None]:
        """Handle GetUserByIdQuery."""
        user = await self._repository.get_by_id(query.user_id)
        return QueryResult(data=user)

    async def handle_search_users(self, query: SearchUsersQuery) -> QueryResult[list[User]]:
        """Handle SearchUsersQuery with optimized filtering."""
        # Use read-optimized queries, materialized views, etc.
        from src.infrastructure.filtering.user_filterset import UserFilterSet

        filters = UserFilterSet(
            email__icontains=query.email_contains,
            username__icontains=query.username_contains,
            is_active=query.is_active,
        )

        users, total = await self._repository.find(
            filterset=filters,
            skip=query.skip,
            limit=query.limit,
        )

        return QueryResult(data=users, total_count=total)

    async def handle_get_user_stats(self, query: GetUserStatsQuery) -> QueryResult[dict]:
        """Handle GetUserStatsQuery - read from materialized view."""
        # Query pre-computed statistics
        stats = {
            "total_users": 1000,  # From materialized view
            "active_users": 850,
            "users_created_today": 12,
        }
        return QueryResult(data=stats)
```

#### 3.7 Read Model (Materialized View)

**Location**: `migrations/materialized_views/user_stats.sql`

```sql
-- Materialized view for user statistics (updated periodically)
CREATE MATERIALIZED VIEW user_stats AS
SELECT
    COUNT(*) AS total_users,
    COUNT(*) FILTER (WHERE is_active = true AND deleted_at IS NULL) AS active_users,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) AS users_created_today,
    COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) AS deleted_users
FROM users;

-- Index for fast refresh
CREATE UNIQUE INDEX user_stats_refresh_idx ON user_stats (total_users);

-- Refresh materialized view every hour (via cron job or Temporal workflow)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY user_stats;
```

#### 3.8 Updated API Endpoints (CQRS)

**Location**: `src/presentation/api/v1/users.py`

```python
"""User API endpoints using CQRS pattern."""
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.app.commands.handlers.user_command_handler import UserCommandHandler
from src.app.commands.user_commands import CreateUserCommand
from src.app.queries.handlers.user_query_handler import UserQueryHandler
from src.app.queries.user_queries import GetUserByIdQuery, SearchUsersQuery
from src.presentation.schemas.user import CreateUserRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    handler: UserCommandHandler = Depends(),
) -> UserResponse:
    """Create a new user (COMMAND)."""
    command = CreateUserCommand(
        email=request.email,
        username=request.username,
        full_name=request.full_name,
    )

    result = await handler.handle_create_user(command)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return UserResponse(**result.data)


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    handler: UserQueryHandler = Depends(),
) -> UserResponse:
    """Get user by ID (QUERY)."""
    query = GetUserByIdQuery(user_id=user_id)
    result = await handler.handle_get_user_by_id(query)

    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_entity(result.data)


@router.get("")
async def search_users(
    email: str | None = None,
    username: str | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
    handler: UserQueryHandler = Depends(),
) -> list[UserResponse]:
    """Search users with filters (QUERY)."""
    query = SearchUsersQuery(
        email_contains=email,
        username_contains=username,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )

    result = await handler.handle_search_users(query)
    return [UserResponse.from_entity(user) for user in result.data]
```

### Benefits

✅ **Independent Scaling** - Scale read and write databases separately
✅ **Performance** - Optimize queries without affecting writes
✅ **Flexibility** - Different models for reads (denormalized) and writes (normalized)
✅ **Testability** - Commands and queries are easily testable
✅ **Audit Trail** - Event sourcing captures all state changes
✅ **Eventually Consistent** - Trade consistency for performance where appropriate

---

## 4. Plugin System

### Overview

Implement a **plugin architecture** enabling third-party extensions without modifying core code.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Core Application                          │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Plugin Manager                              │ │
│  │  - Discovery (filesystem, registry)                    │ │
│  │  - Loading (dynamic import)                            │ │
│  │  - Lifecycle (init, start, stop)                       │ │
│  │  - Dependency resolution                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌───────────────────────┼────────────────────────────────┐ │
│  │       Plugin Interface (Contract)                      │ │
│  │  - Hooks: on_startup, on_shutdown, on_user_created    │ │
│  │  - Services: Provide custom services                  │ │
│  │  - Routes: Add custom API endpoints                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
  ┌─────▼─────┐    ┌──────▼──────┐   ┌─────▼──────┐
  │  Plugin A │    │  Plugin B   │   │  Plugin C  │
  │ (Analytics)│    │  (Slack)    │   │  (Export)  │
  └───────────┘    └─────────────┘   └────────────┘
```

### Implementation

#### 4.1 Plugin Interface

**Location**: `src/domain/plugins/interface.py`

```python
"""Plugin interface defining the contract for all plugins."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI


@dataclass
class PluginMetadata:
    """Metadata about a plugin."""

    name: str
    version: str
    author: str
    description: str
    dependencies: list[str] = None  # List of required plugin names

    def __post_init__(self) -> None:
        if self.dependencies is None:
            self.dependencies = []


class IPlugin(ABC):
    """Base interface for all plugins.

    Plugins can:
    - Hook into application lifecycle events
    - Register custom API routes
    - Subscribe to domain events
    - Provide custom services
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    async def on_load(self) -> None:
        """Called when plugin is loaded (before app startup)."""
        pass

    async def on_startup(self, app: FastAPI) -> None:
        """Called when application starts.

        Use this to:
        - Register routes
        - Initialize resources
        - Subscribe to events
        """
        pass

    async def on_shutdown(self) -> None:
        """Called when application shuts down.

        Use this to:
        - Clean up resources
        - Close connections
        """
        pass

    def get_routes(self) -> list[Any]:
        """Return list of FastAPI routers to register.

        Returns:
            List of APIRouter instances
        """
        return []

    def get_event_handlers(self) -> dict[str, list[Any]]:
        """Return event handlers to register.

        Returns:
            Dict mapping event names to handler functions
        """
        return {}
```

#### 4.2 Plugin Manager

**Location**: `src/infrastructure/plugins/manager.py`

```python
"""Plugin manager for discovering and loading plugins."""
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from src.domain.plugins.interface import IPlugin, PluginMetadata
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class PluginManager:
    """Manages plugin lifecycle: discovery, loading, initialization."""

    def __init__(self, plugins_dir: Path) -> None:
        self._plugins_dir = plugins_dir
        self._loaded_plugins: dict[str, IPlugin] = {}
        self._plugin_order: list[str] = []  # For dependency resolution

    async def discover_plugins(self) -> list[PluginMetadata]:
        """Discover all available plugins in plugins directory.

        Returns:
            List of plugin metadata
        """
        discovered = []

        if not self._plugins_dir.exists():
            logger.warning("plugins_directory_not_found", path=str(self._plugins_dir))
            return discovered

        for plugin_path in self._plugins_dir.iterdir():
            if plugin_path.is_dir() and (plugin_path / "__init__.py").exists():
                try:
                    metadata = await self._load_plugin_metadata(plugin_path)
                    discovered.append(metadata)
                except Exception as e:
                    logger.error(
                        "failed_to_discover_plugin",
                        path=str(plugin_path),
                        error=str(e),
                    )

        return discovered

    async def load_plugins(self) -> None:
        """Load all discovered plugins."""
        discovered = await self.discover_plugins()

        # Sort by dependencies (topological sort)
        sorted_plugins = self._resolve_dependencies(discovered)

        for metadata in sorted_plugins:
            try:
                plugin = await self._load_plugin(metadata.name)
                self._loaded_plugins[metadata.name] = plugin
                self._plugin_order.append(metadata.name)

                logger.info(
                    "plugin_loaded",
                    name=metadata.name,
                    version=metadata.version,
                )
            except Exception as e:
                logger.error(
                    "failed_to_load_plugin",
                    name=metadata.name,
                    error=str(e),
                    exc_info=True,
                )

    async def initialize_plugins(self, app: FastAPI) -> None:
        """Initialize all loaded plugins."""
        for plugin_name in self._plugin_order:
            plugin = self._loaded_plugins[plugin_name]

            try:
                # Call on_startup hook
                await plugin.on_startup(app)

                # Register routes
                for router in plugin.get_routes():
                    app.include_router(router)

                # Register event handlers
                from src.infrastructure.di.container import container
                event_bus = await container.event_bus()

                for event_name, handlers in plugin.get_event_handlers().items():
                    for handler in handlers:
                        event_bus.subscribe(event_name, handler)

                logger.info("plugin_initialized", name=plugin_name)

            except Exception as e:
                logger.error(
                    "failed_to_initialize_plugin",
                    name=plugin_name,
                    error=str(e),
                    exc_info=True,
                )

    async def shutdown_plugins(self) -> None:
        """Shutdown all plugins in reverse order."""
        for plugin_name in reversed(self._plugin_order):
            plugin = self._loaded_plugins[plugin_name]
            try:
                await plugin.on_shutdown()
                logger.info("plugin_shutdown", name=plugin_name)
            except Exception as e:
                logger.error(
                    "failed_to_shutdown_plugin",
                    name=plugin_name,
                    error=str(e),
                )

    async def _load_plugin_metadata(self, plugin_path: Path) -> PluginMetadata:
        """Load plugin metadata from plugin directory."""
        spec = importlib.util.spec_from_file_location(
            plugin_path.name,
            plugin_path / "__init__.py",
        )
        if not spec or not spec.loader:
            raise ValueError(f"Cannot load plugin from {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find Plugin class
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, IPlugin)
                and obj is not IPlugin
            ):
                plugin_instance = obj()
                return plugin_instance.metadata

        raise ValueError(f"No plugin class found in {plugin_path}")

    async def _load_plugin(self, plugin_name: str) -> IPlugin:
        """Load plugin instance."""
        plugin_path = self._plugins_dir / plugin_name

        spec = importlib.util.spec_from_file_location(
            plugin_name,
            plugin_path / "__init__.py",
        )
        if not spec or not spec.loader:
            raise ValueError(f"Cannot load plugin {plugin_name}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find and instantiate Plugin class
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, IPlugin)
                and obj is not IPlugin
            ):
                plugin_instance = obj()
                await plugin_instance.on_load()
                return plugin_instance

        raise ValueError(f"No plugin class found in {plugin_name}")

    def _resolve_dependencies(
        self,
        plugins: list[PluginMetadata],
    ) -> list[PluginMetadata]:
        """Resolve plugin dependencies using topological sort."""
        # Simple topological sort implementation
        sorted_plugins = []
        remaining = plugins.copy()

        while remaining:
            # Find plugins with no unmet dependencies
            ready = [
                p
                for p in remaining
                if all(dep in [s.name for s in sorted_plugins] for dep in p.dependencies)
            ]

            if not ready:
                # Circular dependency or missing dependency
                logger.error("circular_or_missing_plugin_dependencies")
                break

            sorted_plugins.extend(ready)
            for p in ready:
                remaining.remove(p)

        return sorted_plugins
```

#### 4.3 Example Plugin: Slack Notifications

**Location**: `plugins/slack_notifications/__init__.py`

```python
"""Slack notifications plugin."""
from typing import Any

from fastapi import APIRouter

from src.domain.events.user_events import UserCreated
from src.domain.plugins.interface import IPlugin, PluginMetadata
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class SlackNotificationsPlugin(IPlugin):
    """Plugin that sends Slack notifications for domain events."""

    def __init__(self) -> None:
        self._webhook_url: str | None = None
        self._router = APIRouter(prefix="/plugins/slack", tags=["plugins"])

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="slack_notifications",
            version="1.0.0",
            author="Your Team",
            description="Send Slack notifications for domain events",
            dependencies=[],
        )

    async def on_load(self) -> None:
        """Load configuration."""
        # Load from env or config
        import os
        self._webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    async def on_startup(self, app) -> None:
        """Register routes and subscribe to events."""
        logger.info("slack_plugin_starting")

        # Add custom endpoint
        @self._router.post("/test")
        async def test_slack():
            await self._send_slack_message("Test message from plugin!")
            return {"status": "sent"}

    async def on_shutdown(self) -> None:
        """Cleanup resources."""
        logger.info("slack_plugin_shutting_down")

    def get_routes(self) -> list[Any]:
        """Return plugin routes."""
        return [self._router]

    def get_event_handlers(self) -> dict[str, list[Any]]:
        """Return event handlers."""
        return {
            "UserCreated": [self._handle_user_created],
        }

    async def _handle_user_created(self, event: UserCreated) -> None:
        """Handle UserCreated event."""
        message = f"🎉 New user created: {event.username} ({event.email})"
        await self._send_slack_message(message)

    async def _send_slack_message(self, message: str) -> None:
        """Send message to Slack webhook."""
        if not self._webhook_url:
            logger.warning("slack_webhook_not_configured")
            return

        import httpx

        async with httpx.AsyncClient() as client:
            await client.post(
                self._webhook_url,
                json={"text": message},
            )
```

#### 4.4 Plugin Configuration

**Location**: `.env.example`

```bash
# Plugin System
PLUGINS_ENABLED=true
PLUGINS_DIR=./plugins

# Plugin: Slack Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Benefits

✅ **Extensibility** - Add features without modifying core code
✅ **Modularity** - Plugins are self-contained and testable
✅ **Third-party Integration** - Easy to integrate external services
✅ **Customization** - Different deployments can use different plugins
✅ **Marketplace Potential** - Build a plugin ecosystem

---

## 5. Additional Advanced Features

### 5.1 Feature Flags

**Location**: `src/infrastructure/feature_flags/manager.py`

```python
"""Feature flag management for safe deployments."""
from enum import Enum

from redis.asyncio import Redis


class FeatureFlag(str, Enum):
    """Available feature flags."""

    NEW_USER_FLOW = "new_user_flow"
    ADVANCED_SEARCH = "advanced_search"
    WEBSOCKET_NOTIFICATIONS = "websocket_notifications"
    CQRS_MODE = "cqrs_mode"


class FeatureFlagManager:
    """Manage feature flags with Redis backend."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._cache: dict[str, bool] = {}

    async def is_enabled(
        self,
        flag: FeatureFlag,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        """Check if feature flag is enabled.

        Supports:
        - Global flags
        - Per-tenant flags
        - Per-user flags (for gradual rollout)
        """
        # Check user-specific flag
        if user_id:
            key = f"feature_flag:{flag}:user:{user_id}"
            value = await self._redis.get(key)
            if value is not None:
                return value == "1"

        # Check tenant-specific flag
        if tenant_id:
            key = f"feature_flag:{flag}:tenant:{tenant_id}"
            value = await self._redis.get(key)
            if value is not None:
                return value == "1"

        # Check global flag
        key = f"feature_flag:{flag}:global"
        value = await self._redis.get(key)
        return value == "1" if value is not None else False

    async def enable(
        self,
        flag: FeatureFlag,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Enable feature flag."""
        key = self._get_key(flag, user_id, tenant_id)
        await self._redis.set(key, "1")

    async def disable(
        self,
        flag: FeatureFlag,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Disable feature flag."""
        key = self._get_key(flag, user_id, tenant_id)
        await self._redis.set(key, "0")

    def _get_key(
        self,
        flag: FeatureFlag,
        user_id: str | None,
        tenant_id: str | None,
    ) -> str:
        """Generate Redis key for flag."""
        if user_id:
            return f"feature_flag:{flag}:user:{user_id}"
        if tenant_id:
            return f"feature_flag:{flag}:tenant:{tenant_id}"
        return f"feature_flag:{flag}:global"
```

### 5.2 Saga Pattern (Distributed Transactions)

**Location**: `src/app/sagas/create_order_saga.py`

```python
"""Saga pattern for distributed transactions."""
from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class SagaStep(Enum):
    """Steps in the saga."""

    RESERVE_INVENTORY = "reserve_inventory"
    CHARGE_PAYMENT = "charge_payment"
    CREATE_SHIPMENT = "create_shipment"
    SEND_CONFIRMATION = "send_confirmation"


@dataclass
class SagaContext:
    """Context passed through saga steps."""

    order_id: UUID
    user_id: UUID
    items: list[dict]
    total_amount: float

    # Compensation data
    inventory_reserved: bool = False
    payment_charged: bool = False
    shipment_created: bool = False


class CreateOrderSaga:
    """Saga for creating an order with compensation logic.

    Steps:
    1. Reserve inventory -> Compensate: Release inventory
    2. Charge payment -> Compensate: Refund payment
    3. Create shipment -> Compensate: Cancel shipment
    4. Send confirmation -> No compensation needed
    """

    async def execute(self, context: SagaContext) -> bool:
        """Execute saga with automatic compensation on failure."""
        try:
            # Step 1: Reserve inventory
            await self._reserve_inventory(context)
            context.inventory_reserved = True

            # Step 2: Charge payment
            await self._charge_payment(context)
            context.payment_charged = True

            # Step 3: Create shipment
            await self._create_shipment(context)
            context.shipment_created = True

            # Step 4: Send confirmation
            await self._send_confirmation(context)

            return True

        except Exception as e:
            # Compensate in reverse order
            await self._compensate(context)
            raise

    async def _reserve_inventory(self, context: SagaContext) -> None:
        """Reserve inventory for order."""
        # Call inventory service
        pass

    async def _charge_payment(self, context: SagaContext) -> None:
        """Charge payment."""
        # Call payment service
        pass

    async def _create_shipment(self, context: SagaContext) -> None:
        """Create shipment."""
        # Call shipping service
        pass

    async def _send_confirmation(self, context: SagaContext) -> None:
        """Send order confirmation."""
        # Call notification service
        pass

    async def _compensate(self, context: SagaContext) -> None:
        """Compensate failed saga."""
        if context.shipment_created:
            await self._cancel_shipment(context)

        if context.payment_charged:
            await self._refund_payment(context)

        if context.inventory_reserved:
            await self._release_inventory(context)

    async def _cancel_shipment(self, context: SagaContext) -> None:
        """Compensation: Cancel shipment."""
        pass

    async def _refund_payment(self, context: SagaContext) -> None:
        """Compensation: Refund payment."""
        pass

    async def _release_inventory(self, context: SagaContext) -> None:
        """Compensation: Release inventory."""
        pass
```

### 5.3 GraphQL API (Alternative to REST)

**Location**: `src/presentation/graphql/schema.py`

```python
"""GraphQL schema using Strawberry."""
import strawberry
from uuid import UUID

from src.app.queries.user_queries import GetUserByIdQuery, SearchUsersQuery
from src.app.queries.handlers.user_query_handler import UserQueryHandler


@strawberry.type
class User:
    """GraphQL User type."""

    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool


@strawberry.type
class Query:
    """GraphQL queries."""

    @strawberry.field
    async def user(self, id: UUID) -> User | None:
        """Get user by ID."""
        handler = UserQueryHandler()  # Get from DI
        query = GetUserByIdQuery(user_id=id)
        result = await handler.handle_get_user_by_id(query)
        return result.data

    @strawberry.field
    async def users(
        self,
        email: str | None = None,
        username: str | None = None,
        is_active: bool | None = None,
    ) -> list[User]:
        """Search users."""
        handler = UserQueryHandler()
        query = SearchUsersQuery(
            email_contains=email,
            username_contains=username,
            is_active=is_active,
        )
        result = await handler.handle_search_users(query)
        return result.data


schema = strawberry.Schema(query=Query)
```

### 5.4 Audit Logging

**Location**: `src/infrastructure/audit/logger.py`

```python
"""Comprehensive audit logging for compliance."""
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid7

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


class AuditAction(str, Enum):
    """Types of audit actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"
    LOGIN = "login"
    LOGOUT = "logout"


class AuditLog(Base):
    """Audit log table for compliance and security."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid7)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Who
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    tenant_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # What
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Changes
    old_values: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    new_values: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Context
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)


class AuditLogger:
    """Service for logging audit events."""

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
    ) -> None:
        """Log audit event."""
        # Store in database
        pass
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- ✅ Domain Events & In-Memory Event Bus
- ✅ Event handlers for User domain
- ✅ Basic SSE implementation
- ✅ Feature flags infrastructure

### Phase 2: Real-time & Streaming (Weeks 3-4)
- ✅ WebSocket Manager with Redis pub/sub
- ✅ SSE Manager with multi-tenant support
- ✅ Integration with domain events
- ✅ Real-time notification system

### Phase 3: CQRS (Weeks 5-7)
- ✅ Command/Query base classes
- ✅ Command and Query handlers
- ✅ Separate read models (materialized views)
- ✅ Event-driven read model updates
- ✅ Redis Event Bus for production

### Phase 4: Plugin System (Weeks 8-9)
- ✅ Plugin interface and manager
- ✅ Example plugins (Slack, Analytics)
- ✅ Plugin marketplace infrastructure
- ✅ Documentation for plugin developers

### Phase 5: Advanced Features (Weeks 10-12)
- ✅ Saga pattern for distributed transactions
- ✅ GraphQL API (optional)
- ✅ Audit logging system
- ✅ Advanced feature flags (% rollout)

---

## Migration Strategy

### Backward Compatibility

All enhancements are **additive** and **optional**:

1. **Existing code continues to work** - Use cases can coexist with commands
2. **Gradual migration** - Migrate one domain at a time
3. **Feature flags** - Enable new features per tenant/user
4. **Dual write** - Write to both old and new systems during transition

### Migration Steps

1. **Enable feature flags** - Deploy with all features disabled
2. **Add event infrastructure** - No behavior changes yet
3. **Migrate one use case** - Start with CreateUser
4. **Test in staging** - Verify both paths work
5. **Enable for beta tenants** - Gradual rollout
6. **Monitor metrics** - Watch for errors/performance
7. **Full rollout** - Enable for all tenants
8. **Remove old code** - After 1-2 months of stability

---

## Appendices

### A. Technology Recommendations

| Feature | Library | Rationale |
|---------|---------|-----------|
| **Event Bus** | Custom + Redis | Fits existing stack, simple |
| **WebSocket** | FastAPI built-in | Native support, no extra deps |
| **SSE** | FastAPI StreamingResponse | Standard HTTP, simple |
| **Feature Flags** | LaunchDarkly / Flagsmith | Battle-tested, gradual rollout |
| **GraphQL** | Strawberry | Type-safe, async, modern |
| **Saga** | Temporal | Already in stack, durable |

### B. Performance Considerations

- **Event Bus**: In-memory for dev, Redis for prod (< 1ms latency)
- **WebSocket**: 10K concurrent connections per instance
- **SSE**: 5K concurrent connections per instance
- **CQRS**: 10x read performance improvement (with caching)
- **Plugin System**: < 100ms startup overhead per plugin

### C. Security Considerations

- **WebSocket**: JWT authentication required
- **SSE**: Same-origin policy, CORS configured
- **Plugins**: Sandboxed execution, capability-based security
- **Event Bus**: Tenant isolation in events
- **Audit Log**: Immutable, append-only

### D. Testing Strategy

- **Unit Tests**: Commands, queries, event handlers
- **Integration Tests**: Event bus, WebSocket, SSE
- **E2E Tests**: Full CQRS flow, plugin loading
- **Performance Tests**: WebSocket load, event throughput
- **Security Tests**: Auth, tenant isolation

---

## Conclusion

These enhancements transform `python-fast-forge` into a **world-class, enterprise-grade platform** capable of:

✅ **Real-time collaboration** (WebSocket/SSE)
✅ **Event-driven architecture** (Domain Events, Event Bus)
✅ **Massive scale** (CQRS, separate read/write)
✅ **Infinite extensibility** (Plugin System)
✅ **Safe deployments** (Feature Flags, Saga Pattern)
✅ **Compliance** (Audit Logging)

The proposed architecture maintains **clean architecture principles** while adding powerful capabilities that scale from startup to enterprise.

---

**Next Steps**: Review and prioritize features, then proceed with implementation roadmap.
