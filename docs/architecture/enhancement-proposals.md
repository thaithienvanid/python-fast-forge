# Python-Fast-Forge Enhancement Proposals

**Status:** Draft
**Date:** 2026-02-06
**Current Score:** 9/10 (Excellent foundation)
**Target Score:** 10/10 (World-class production system)

---

## Executive Summary

This document proposes **8 production-ready enhancement packages** to transform python-fast-forge from an excellent boilerplate into a **world-class, event-driven, scalable microservices platform**.

**Current Strengths:**
- ✅ Clean Architecture (4-layer separation)
- ✅ Domain Events + EventBus (in-memory)
- ✅ Comprehensive testing (84% coverage)
- ✅ Multi-tenancy + Soft delete
- ✅ Strong security posture

**Enhancement Areas:**
1. **Event Sourcing & CQRS** - Full event-driven architecture
2. **Real-Time Streaming** - WebSocket + SSE support
3. **Plugin System** - Extensible architecture
4. **Message Queue Integration** - Distributed async processing
5. **Advanced Observability** - Production monitoring
6. **API Gateway Pattern** - GraphQL + gRPC support
7. **Search & Analytics** - Full-text search + aggregations
8. **Multi-Database Support** - Read replicas + sharding

---

## 1. Event Sourcing & CQRS Pattern

### Current State
- ✅ Domain events implemented (UserCreated, UserUpdated, etc.)
- ✅ In-memory EventBus with pub/sub
- ❌ Events lost on restart (no persistence)
- ❌ No event replay capability
- ❌ No CQRS separation (read/write use same models)

### Proposed Architecture

```
┌─────────────────────────────────────────────────────┐
│                  COMMAND SIDE                        │
├─────────────────────────────────────────────────────┤
│  API Request → Command → Aggregate → Event Store    │
│                    ↓                      ↓          │
│              Validate Business       Append Events   │
│              Rules & State          (Immutable Log)  │
└─────────────────────────┬───────────────────────────┘
                          │
                    Event Published
                          ↓
┌─────────────────────────────────────────────────────┐
│                   QUERY SIDE                         │
├─────────────────────────────────────────────────────┤
│  Event Handler → Update Read Models → Query API     │
│       ↓               ↓                    ↓         │
│  Projection      Denormalized        Fast Reads     │
│  Logic           Tables/Cache        (No Joins)     │
└─────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 1: Event Store (Week 1-2)

**1.1 Database Schema**

```python
# src/infrastructure/persistence/event_store_schema.py
from sqlalchemy import Column, String, DateTime, JSON, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, UTC

class EventStoreEntry(Base):
    """Immutable append-only event log."""

    __tablename__ = "event_store"

    # Identity
    event_id = Column(UUID, primary_key=True)  # UUIDv7 for time-ordering

    # Event metadata
    event_type = Column(String(255), nullable=False, index=True)
    event_version = Column(Integer, default=1, nullable=False)
    aggregate_type = Column(String(100), nullable=False)  # "User", "Order", etc.
    aggregate_id = Column(UUID, nullable=False, index=True)
    aggregate_version = Column(Integer, nullable=False)  # For optimistic locking

    # Event data
    event_data = Column(JSONB, nullable=False)  # Actual event payload
    metadata = Column(JSONB, default={})  # Causation/correlation IDs, user context

    # Timing
    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Optimistic locking constraint
    __table_args__ = (
        Index('ix_event_store_aggregate', 'aggregate_type', 'aggregate_id'),
        Index('ix_event_store_occurred_at', 'occurred_at'),
        Index('ix_event_store_event_type', 'event_type'),
        # Ensure events are ordered per aggregate
        Index('ix_event_store_aggregate_version', 'aggregate_id', 'aggregate_version', unique=True),
    )


class EventStoreSnapshot(Base):
    """Snapshot table for performance optimization."""

    __tablename__ = "event_store_snapshots"

    id = Column(UUID, primary_key=True)
    aggregate_type = Column(String(100), nullable=False)
    aggregate_id = Column(UUID, nullable=False, unique=True)
    aggregate_version = Column(Integer, nullable=False)

    snapshot_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

**1.2 Event Store Repository**

```python
# src/infrastructure/repositories/event_store_repository.py
from typing import AsyncIterator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class EventStoreRepository:
    """Repository for event store operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def append_event(
        self,
        event: DomainEvent,
        aggregate_type: str,
        expected_version: int | None = None,
    ) -> None:
        """Append event to store with optimistic locking.

        Args:
            event: Domain event to persist
            aggregate_type: Type of aggregate (e.g., "User")
            expected_version: Expected current version (for concurrency control)

        Raises:
            ConcurrencyError: If aggregate version mismatch
        """
        # Get current version
        current_version = await self._get_current_version(
            aggregate_type, event.aggregate_id
        )

        # Optimistic locking check
        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                f"Expected version {expected_version}, but current is {current_version}"
            )

        # Create entry
        entry = EventStoreEntry(
            event_id=event.event_id,
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_type=aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=current_version + 1,
            event_data=event.model_dump(mode='json'),
            metadata={
                "user_id": event.metadata.get("user_id"),
                "correlation_id": event.metadata.get("correlation_id"),
                "causation_id": event.metadata.get("causation_id"),
            },
            occurred_at=event.occurred_at,
        )

        self._session.add(entry)
        await self._session.flush()

    async def get_events(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
        from_version: int = 0,
    ) -> AsyncIterator[DomainEvent]:
        """Get all events for an aggregate.

        Args:
            aggregate_id: Aggregate identifier
            aggregate_type: Type of aggregate
            from_version: Starting version (for incremental replay)

        Yields:
            Domain events in order
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
            event_class = self._get_event_class(entry.event_type)
            yield event_class.model_validate(entry.event_data)

    async def get_all_events_since(
        self,
        since: datetime,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[tuple[EventStoreEntry, DomainEvent]]:
        """Get all events since a timestamp (for projections).

        Args:
            since: Starting timestamp
            event_types: Filter by event types

        Yields:
            Tuples of (entry, reconstructed_event)
        """
        query = select(EventStoreEntry).where(
            EventStoreEntry.occurred_at > since
        )

        if event_types:
            query = query.where(EventStoreEntry.event_type.in_(event_types))

        query = query.order_by(EventStoreEntry.occurred_at)

        result = await self._session.execute(query)

        for entry in result.scalars():
            event_class = self._get_event_class(entry.event_type)
            event = event_class.model_validate(entry.event_data)
            yield entry, event

    async def save_snapshot(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
        aggregate_version: int,
        snapshot_data: dict,
    ) -> None:
        """Save aggregate snapshot for performance."""
        snapshot = EventStoreSnapshot(
            id=uuid7(),
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            snapshot_data=snapshot_data,
        )

        # Upsert snapshot
        await self._session.merge(snapshot)

    async def get_snapshot(
        self,
        aggregate_id: UUID,
        aggregate_type: str,
    ) -> tuple[int, dict] | None:
        """Get latest snapshot for aggregate.

        Returns:
            Tuple of (version, snapshot_data) or None
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
        """Get current version of aggregate."""
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

    def _get_event_class(self, event_type: str) -> type[DomainEvent]:
        """Get event class from event type string."""
        # Event registry pattern
        from src.domain.events import EVENT_REGISTRY
        return EVENT_REGISTRY[event_type]
```

**1.3 Event Registry**

```python
# src/domain/events/__init__.py
from typing import Type
from .base import DomainEvent
from .user_events import (
    UserCreatedEvent,
    UserUpdatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
)

# Event type registry for deserialization
EVENT_REGISTRY: dict[str, Type[DomainEvent]] = {
    "user.created": UserCreatedEvent,
    "user.updated": UserUpdatedEvent,
    "user.deleted": UserDeletedEvent,
    "user.restored": UserRestoredEvent,
}

def register_event(event_type: str):
    """Decorator to register event types."""
    def decorator(cls: Type[DomainEvent]):
        EVENT_REGISTRY[event_type] = cls
        cls.event_type = event_type
        return cls
    return decorator
```

#### Phase 2: CQRS Separation (Week 3-4)

**2.1 Command Models**

```python
# src/app/commands/user_commands.py
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

class CreateUserCommand(BaseModel):
    """Command to create a new user."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str | None = Field(None, max_length=255)
    tenant_id: UUID | None = None

    # Command metadata
    commanded_by: UUID  # User who initiated command
    correlation_id: UUID  # For tracing across services
    idempotency_key: UUID  # For duplicate prevention


class UpdateUserCommand(BaseModel):
    """Command to update user."""

    user_id: UUID
    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None
    is_active: bool | None = None

    commanded_by: UUID
    correlation_id: UUID
    expected_version: int  # Optimistic locking
```

**2.2 Command Handlers**

```python
# src/app/command_handlers/user_command_handler.py
from src.domain.models.user import User
from src.infrastructure.repositories.event_store_repository import EventStoreRepository

class UserCommandHandler:
    """Handles user commands and produces events."""

    def __init__(
        self,
        event_store: EventStoreRepository,
        event_bus: EventBus,
    ):
        self._event_store = event_store
        self._event_bus = event_bus

    async def handle_create_user(self, command: CreateUserCommand) -> UUID:
        """Handle CreateUserCommand.

        Returns:
            Created user ID
        """
        # 1. Create aggregate
        user = User(
            id=uuid7(),
            email=command.email,
            username=command.username,
            full_name=command.full_name,
            tenant_id=command.tenant_id,
        )

        # 2. Validate business rules
        user.validate()

        # 3. Create domain event
        event = UserCreatedEvent(
            aggregate_id=user.id,
            user_id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            tenant_id=user.tenant_id,
            metadata={
                "commanded_by": str(command.commanded_by),
                "correlation_id": str(command.correlation_id),
            }
        )

        # 4. Append to event store
        await self._event_store.append_event(
            event=event,
            aggregate_type="User",
            expected_version=None,  # New aggregate
        )

        # 5. Publish event (async handlers)
        await self._event_bus.publish(event)

        return user.id

    async def handle_update_user(self, command: UpdateUserCommand) -> None:
        """Handle UpdateUserCommand."""
        # 1. Reconstruct aggregate from events
        user = await self._reconstruct_user(command.user_id)

        # 2. Apply changes
        changed_fields = {}
        if command.email:
            changed_fields['email'] = (user.email, command.email)
            user.email = command.email
        if command.username:
            changed_fields['username'] = (user.username, command.username)
            user.username = command.username
        # ... other fields

        # 3. Validate business rules
        user.validate()

        # 4. Create domain event
        event = UserUpdatedEvent(
            aggregate_id=user.id,
            user_id=user.id,
            changed_fields=changed_fields,
            metadata={
                "commanded_by": str(command.commanded_by),
                "correlation_id": str(command.correlation_id),
            }
        )

        # 5. Append to event store with optimistic locking
        await self._event_store.append_event(
            event=event,
            aggregate_type="User",
            expected_version=command.expected_version,
        )

        # 6. Publish event
        await self._event_bus.publish(event)

    async def _reconstruct_user(self, user_id: UUID) -> User:
        """Reconstruct user aggregate from event stream.

        Uses snapshot + incremental replay for performance.
        """
        # 1. Try to load snapshot
        snapshot = await self._event_store.get_snapshot(user_id, "User")

        if snapshot:
            version, snapshot_data = snapshot
            user = User.model_validate(snapshot_data)
            from_version = version
        else:
            user = None
            from_version = 0

        # 2. Replay events since snapshot
        async for event in self._event_store.get_events(
            user_id, "User", from_version=from_version
        ):
            user = self._apply_event(user, event)

        if user is None:
            raise EntityNotFoundError(f"User {user_id} not found")

        return user

    def _apply_event(self, user: User | None, event: DomainEvent) -> User:
        """Apply event to user aggregate."""
        if isinstance(event, UserCreatedEvent):
            return User(
                id=event.user_id,
                email=event.email,
                username=event.username,
                full_name=event.full_name,
                tenant_id=event.tenant_id,
                created_at=event.occurred_at,
            )
        elif isinstance(event, UserUpdatedEvent):
            for field, (old_value, new_value) in event.changed_fields.items():
                setattr(user, field, new_value)
            user.updated_at = event.occurred_at
            return user
        elif isinstance(event, UserDeletedEvent):
            user.deleted_at = event.occurred_at
            return user
        elif isinstance(event, UserRestoredEvent):
            user.deleted_at = None
            user.updated_at = event.occurred_at
            return user

        return user
```

**2.3 Query Models (Read Side)**

```python
# src/app/queries/user_queries.py
from pydantic import BaseModel
from uuid import UUID

class UserQueryModel(BaseModel):
    """Denormalized user for fast reads."""

    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime

    # Denormalized fields for performance
    total_orders: int = 0  # From OrderCreatedEvent projections
    last_login_at: datetime | None = None  # From UserLoggedInEvent
    profile_completion: int = 0  # Calculated field

    class Config:
        from_attributes = True


class UserListQuery(BaseModel):
    """Query for listing users."""

    tenant_id: UUID | None = None
    is_active: bool | None = None
    email_contains: str | None = None
    skip: int = 0
    limit: int = 50


class UserDetailQuery(BaseModel):
    """Query for user detail."""

    user_id: UUID
    include_deleted: bool = False
```

**2.4 Query Handlers (Projections)**

```python
# src/app/query_handlers/user_query_handler.py
from sqlalchemy import select
from src.infrastructure.persistence.read_models import UserReadModel

class UserQueryHandler:
    """Handles user queries against read models."""

    def __init__(
        self,
        read_session: AsyncSession,  # Separate read-only connection
        cache: RedisCache,
    ):
        self._session = read_session
        self._cache = cache

    async def handle_user_detail(self, query: UserDetailQuery) -> UserQueryModel:
        """Get user detail from read model.

        This is fast because:
        1. No event reconstruction needed
        2. Denormalized data (no joins)
        3. Cached results
        4. Read replica database
        """
        # Try cache first
        cache_key = f"user:detail:{query.user_id}"
        cached = await self._cache.get(cache_key)
        if cached:
            return UserQueryModel.model_validate_json(cached)

        # Query read model
        stmt = select(UserReadModel).where(UserReadModel.id == query.user_id)
        if not query.include_deleted:
            stmt = stmt.where(UserReadModel.deleted_at.is_(None))

        result = await self._session.execute(stmt)
        user_rm = result.scalar_one_or_none()

        if not user_rm:
            raise EntityNotFoundError(f"User {query.user_id} not found")

        user = UserQueryModel.model_validate(user_rm)

        # Cache result
        await self._cache.set(cache_key, user.model_dump_json(), ttl=300)

        return user

    async def handle_user_list(self, query: UserListQuery) -> list[UserQueryModel]:
        """List users from read model."""
        stmt = select(UserReadModel)

        if query.tenant_id:
            stmt = stmt.where(UserReadModel.tenant_id == query.tenant_id)
        if query.is_active is not None:
            stmt = stmt.where(UserReadModel.is_active == query.is_active)
        if query.email_contains:
            stmt = stmt.where(UserReadModel.email.ilike(f"%{query.email_contains}%"))

        stmt = stmt.offset(query.skip).limit(query.limit)

        result = await self._session.execute(stmt)
        return [UserQueryModel.model_validate(rm) for rm in result.scalars()]
```

**2.5 Projection Workers**

```python
# src/infrastructure/projections/user_projection.py
from sqlalchemy import update
from src.infrastructure.persistence.read_models import UserReadModel

class UserProjectionWorker:
    """Background worker that projects events to read models.

    This runs continuously, consuming events and updating read models.
    """

    def __init__(
        self,
        event_store: EventStoreRepository,
        write_session: AsyncSession,
    ):
        self._event_store = event_store
        self._session = write_session
        self._checkpoint = None

    async def run(self):
        """Main projection loop."""
        # Load checkpoint (last processed event timestamp)
        self._checkpoint = await self._load_checkpoint()

        while True:
            try:
                # Get new events since checkpoint
                async for entry, event in self._event_store.get_all_events_since(
                    since=self._checkpoint,
                    event_types=["user.created", "user.updated", "user.deleted", "user.restored"],
                ):
                    # Project event to read model
                    await self._project_event(event)

                    # Update checkpoint
                    self._checkpoint = entry.occurred_at
                    await self._save_checkpoint(self._checkpoint)

                # Sleep before next poll
                await asyncio.sleep(1)

            except Exception as e:
                logger.error("projection_error", error=str(e))
                await asyncio.sleep(5)

    async def _project_event(self, event: DomainEvent):
        """Project single event to read model."""
        if isinstance(event, UserCreatedEvent):
            # Insert into read model
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
                profile_completion=self._calculate_profile_completion(event),
            )
            self._session.add(read_model)

        elif isinstance(event, UserUpdatedEvent):
            # Update read model
            stmt = (
                update(UserReadModel)
                .where(UserReadModel.id == event.user_id)
                .values(
                    email=event.changed_fields.get('email', UserReadModel.email),
                    username=event.changed_fields.get('username', UserReadModel.username),
                    full_name=event.changed_fields.get('full_name', UserReadModel.full_name),
                    updated_at=event.occurred_at,
                )
            )
            await self._session.execute(stmt)

        elif isinstance(event, UserDeletedEvent):
            # Soft delete in read model
            stmt = (
                update(UserReadModel)
                .where(UserReadModel.id == event.user_id)
                .values(deleted_at=event.occurred_at)
            )
            await self._session.execute(stmt)

        await self._session.commit()

    async def _load_checkpoint(self) -> datetime:
        """Load last processed event timestamp."""
        # Load from checkpoint table
        pass

    async def _save_checkpoint(self, timestamp: datetime):
        """Save checkpoint."""
        pass

    def _calculate_profile_completion(self, event: UserCreatedEvent) -> int:
        """Calculate profile completion percentage."""
        score = 0
        if event.email:
            score += 30
        if event.username:
            score += 30
        if event.full_name:
            score += 40
        return score
```

### Benefits of CQRS

| Benefit | Details |
|---------|---------|
| **Performance** | Write: Event append only. Read: Denormalized, no joins, cached |
| **Scalability** | Separate read/write databases, scale independently |
| **Flexibility** | Multiple read models for different use cases |
| **Auditability** | Full event history, reconstruct any state |
| **Temporal Queries** | Query state at any point in time |
| **Debugging** | Replay events to reproduce bugs |
| **Analytics** | Event stream as data source |

### Migration Strategy

1. **Phase 1** (Week 1-2): Implement event store alongside existing repository
2. **Phase 2** (Week 3-4): Add CQRS command/query handlers
3. **Phase 3** (Week 5): Run projections in parallel with existing writes
4. **Phase 4** (Week 6): Switch reads to query handlers
5. **Phase 5** (Week 7): Deprecate old repository pattern

---

## 2. Real-Time Streaming (WebSocket + SSE)

### Current State
- ❌ No WebSocket support
- ❌ No Server-Sent Events (SSE)
- ✅ Temporal workflows for async tasks
- ❌ No real-time notifications

### Proposed Architecture

```
┌──────────────┐     WebSocket      ┌──────────────┐
│   Browser    │◄───────────────────►│  WebSocket   │
│   Client     │                     │   Manager    │
└──────────────┘                     └───────┬──────┘
                                             │
┌──────────────┐     SSE Stream     ┌───────▼──────┐
│   Browser    │◄───────────────────│   Pub/Sub    │
│   Client     │                     │   Hub        │
└──────────────┘                     └───────┬──────┘
                                             │
┌──────────────┐     Redis Pub/Sub  ┌───────▼──────┐
│   API        │────────────────────►│    Redis     │
│  Instance 1  │                     │   Channels   │
└──────────────┘                     └───────▲──────┘
                                             │
┌──────────────┐                     ┌───────┴──────┐
│   API        │────────────────────►│    Redis     │
│  Instance 2  │     Subscribe       │   Channels   │
└──────────────┘                     └──────────────┘
```

### Implementation Plan

#### Phase 1: WebSocket Support (Week 1-2)

**1.1 WebSocket Connection Manager**

```python
# src/infrastructure/realtime/websocket_manager.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
from uuid import UUID
import json

class WebSocketManager:
    """Manages WebSocket connections and message broadcasting.

    Features:
    - Connection lifecycle management
    - Room-based broadcasting (tenant isolation)
    - Redis pub/sub for multi-instance support
    - Authentication via query params or initial message
    - Heartbeat/ping-pong for connection health
    """

    def __init__(self, redis_client: Redis):
        # Active connections: {connection_id: WebSocket}
        self._connections: Dict[str, WebSocket] = {}

        # User connections: {user_id: Set[connection_id]}
        self._user_connections: Dict[UUID, Set[str]] = {}

        # Room subscriptions: {room_id: Set[connection_id]}
        self._rooms: Dict[str, Set[str]] = {}

        # Redis for cross-instance communication
        self._redis = redis_client
        self._pubsub = redis_client.pubsub()

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: UUID | None = None,
    ) -> None:
        """Accept WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            connection_id: Unique connection identifier
            user_id: Authenticated user ID (optional)
        """
        await websocket.accept()

        self._connections[connection_id] = websocket

        if user_id:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

        logger.info(
            "websocket_connected",
            connection_id=connection_id,
            user_id=str(user_id) if user_id else None,
        )

    def disconnect(self, connection_id: str, user_id: UUID | None = None) -> None:
        """Remove WebSocket connection.

        Args:
            connection_id: Connection to remove
            user_id: User ID to clean up
        """
        self._connections.pop(connection_id, None)

        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(connection_id)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        # Remove from all rooms
        for room_connections in self._rooms.values():
            room_connections.discard(connection_id)

        logger.info("websocket_disconnected", connection_id=connection_id)

    async def join_room(self, connection_id: str, room: str) -> None:
        """Add connection to a room (e.g., tenant, chat channel).

        Args:
            connection_id: Connection to add
            room: Room identifier
        """
        if room not in self._rooms:
            self._rooms[room] = set()

        self._rooms[room].add(connection_id)

        # Subscribe to Redis channel for this room
        await self._pubsub.subscribe(f"room:{room}")

        logger.info("websocket_joined_room", connection_id=connection_id, room=room)

    async def leave_room(self, connection_id: str, room: str) -> None:
        """Remove connection from room."""
        if room in self._rooms:
            self._rooms[room].discard(connection_id)

    async def send_personal_message(
        self,
        connection_id: str,
        message: dict,
    ) -> None:
        """Send message to specific connection.

        Args:
            connection_id: Target connection
            message: JSON-serializable message
        """
        websocket = self._connections.get(connection_id)
        if websocket:
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                self.disconnect(connection_id)

    async def send_to_user(self, user_id: UUID, message: dict) -> None:
        """Send message to all connections of a user.

        Args:
            user_id: Target user
            message: JSON-serializable message
        """
        connection_ids = self._user_connections.get(user_id, set())

        for connection_id in connection_ids:
            await self.send_personal_message(connection_id, message)

    async def broadcast_to_room(self, room: str, message: dict) -> None:
        """Broadcast message to all connections in a room.

        Uses Redis pub/sub to reach connections on other instances.

        Args:
            room: Target room
            message: JSON-serializable message
        """
        # Send to local connections
        connection_ids = self._rooms.get(room, set())
        for connection_id in connection_ids:
            await self.send_personal_message(connection_id, message)

        # Publish to Redis for other instances
        await self._redis.publish(
            f"room:{room}",
            json.dumps(message),
        )

    async def broadcast_all(self, message: dict) -> None:
        """Broadcast message to all connections."""
        for connection_id in list(self._connections.keys()):
            await self.send_personal_message(connection_id, message)

    async def listen_redis_pubsub(self):
        """Background task to listen for Redis pub/sub messages."""
        async for message in self._pubsub.listen():
            if message['type'] == 'message':
                channel = message['channel'].decode('utf-8')
                data = json.loads(message['data'])

                # Extract room from channel name
                if channel.startswith('room:'):
                    room = channel[5:]

                    # Send to local connections in this room
                    connection_ids = self._rooms.get(room, set())
                    for connection_id in connection_ids:
                        await self.send_personal_message(connection_id, data)
```

**1.2 WebSocket Endpoints**

```python
# src/presentation/api/v1/endpoints/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from src.infrastructure.realtime.websocket_manager import WebSocketManager
from src.container import Container
from uuid import uuid4

router = APIRouter()
ws_manager: WebSocketManager = Container.websocket_manager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),  # JWT token for auth
):
    """WebSocket endpoint for real-time communication.

    Protocol:
        Client → Server:
            {"type": "subscribe", "room": "tenant:123"}
            {"type": "unsubscribe", "room": "tenant:123"}
            {"type": "ping"}

        Server → Client:
            {"type": "message", "data": {...}}
            {"type": "notification", "data": {...}}
            {"type": "pong"}

    Example:
        const ws = new WebSocket('ws://localhost:8000/api/v1/ws?token=JWT_TOKEN');

        ws.onopen = () => {
            ws.send(JSON.stringify({type: 'subscribe', room: 'tenant:123'}));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
        };
    """
    connection_id = str(uuid4())
    user_id = None

    try:
        # Authenticate user from token
        user_id = await authenticate_token(token)

        # Accept connection
        await ws_manager.connect(websocket, connection_id, user_id)

        # Send welcome message
        await ws_manager.send_personal_message(
            connection_id,
            {
                "type": "connected",
                "connection_id": connection_id,
                "user_id": str(user_id),
            }
        )

        # Message loop
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            message_type = data.get("type")

            if message_type == "subscribe":
                room = data.get("room")
                if room:
                    await ws_manager.join_room(connection_id, room)
                    await ws_manager.send_personal_message(
                        connection_id,
                        {"type": "subscribed", "room": room}
                    )

            elif message_type == "unsubscribe":
                room = data.get("room")
                if room:
                    await ws_manager.leave_room(connection_id, room)
                    await ws_manager.send_personal_message(
                        connection_id,
                        {"type": "unsubscribed", "room": room}
                    )

            elif message_type == "ping":
                await ws_manager.send_personal_message(
                    connection_id,
                    {"type": "pong"}
                )

            else:
                await ws_manager.send_personal_message(
                    connection_id,
                    {"type": "error", "message": f"Unknown message type: {message_type}"}
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id, user_id)
    except Exception as e:
        logger.error("websocket_error", connection_id=connection_id, error=str(e))
        ws_manager.disconnect(connection_id, user_id)


async def authenticate_token(token: str) -> UUID:
    """Authenticate JWT token and return user ID."""
    # TODO: Implement JWT validation
    pass
```

**1.3 Event Broadcasting Integration**

```python
# src/domain/events/event_bus.py (Enhanced)
class EventBus:
    """Enhanced EventBus with WebSocket broadcasting."""

    def __init__(
        self,
        websocket_manager: WebSocketManager | None = None,
        track_history: bool = False,
    ):
        # Existing code...
        self._websocket_manager = websocket_manager

    async def publish(self, event: DomainEvent) -> None:
        """Publish event to handlers AND broadcast via WebSocket."""
        # Existing code: call handlers
        await self._call_handlers(event)

        # NEW: Broadcast to WebSocket connections
        if self._websocket_manager:
            await self._broadcast_event(event)

    async def _broadcast_event(self, event: DomainEvent) -> None:
        """Broadcast domain event to WebSocket clients."""
        message = {
            "type": "domain_event",
            "event_type": event.event_type,
            "event_id": str(event.event_id),
            "aggregate_id": str(event.aggregate_id),
            "occurred_at": event.occurred_at.isoformat(),
            "data": event.model_dump(mode='json'),
        }

        # Broadcast to relevant rooms
        if isinstance(event, UserCreatedEvent):
            # Broadcast to tenant room
            if event.tenant_id:
                await self._websocket_manager.broadcast_to_room(
                    f"tenant:{event.tenant_id}",
                    message
                )

        elif isinstance(event, UserUpdatedEvent):
            # Send to specific user
            await self._websocket_manager.send_to_user(
                event.user_id,
                message
            )
```

#### Phase 2: Server-Sent Events (Week 3)

**2.1 SSE Endpoint**

```python
# src/presentation/api/v1/endpoints/sse.py
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
import asyncio

router = APIRouter()


@router.get("/stream")
async def sse_endpoint(
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Server-Sent Events endpoint for real-time updates.

    This is simpler than WebSocket (unidirectional, HTTP-based).
    Use for notifications, live feeds, progress updates.

    Example client:
        const eventSource = new EventSource('/api/v1/stream?token=JWT_TOKEN');

        eventSource.addEventListener('user.created', (event) => {
            const data = JSON.parse(event.data);
            console.log('New user:', data);
        });

        eventSource.addEventListener('notification', (event) => {
            const data = JSON.parse(event.data);
            showNotification(data.message);
        });
    """
    async def event_generator():
        """Generate SSE events."""
        # Create Redis subscriber for user-specific events
        redis = await get_redis_client()
        pubsub = redis.pubsub()

        # Subscribe to user-specific and tenant-specific channels
        await pubsub.subscribe(
            f"user:{user_id}",
            f"tenant:{tenant_id}",
        )

        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "user_id": str(user_id),
                    "tenant_id": str(tenant_id),
                    "timestamp": datetime.now(UTC).isoformat(),
                })
            }

            # Stream events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Get message from Redis (non-blocking)
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message:
                    event_data = json.loads(message['data'])

                    yield {
                        "event": event_data.get("event_type", "message"),
                        "id": event_data.get("event_id"),
                        "data": json.dumps(event_data)
                    }
                else:
                    # Send heartbeat every 30 seconds
                    await asyncio.sleep(30)
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"timestamp": datetime.now(UTC).isoformat()})
                    }

        finally:
            await pubsub.unsubscribe()
            await pubsub.close()

    return EventSourceResponse(event_generator())
```

**2.2 SSE Event Publisher**

```python
# src/infrastructure/realtime/sse_publisher.py
class SSEPublisher:
    """Publishes events to SSE clients via Redis pub/sub."""

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def publish_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: dict,
    ) -> None:
        """Publish event to specific user's SSE stream.

        Args:
            user_id: Target user
            event_type: Event type (e.g., "notification", "user.updated")
            data: Event payload
        """
        message = {
            "event_type": event_type,
            "event_id": str(uuid7()),
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish(
            f"user:{user_id}",
            json.dumps(message)
        )

    async def publish_to_tenant(
        self,
        tenant_id: UUID,
        event_type: str,
        data: dict,
    ) -> None:
        """Publish event to all users in a tenant."""
        message = {
            "event_type": event_type,
            "event_id": str(uuid7()),
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish(
            f"tenant:{tenant_id}",
            json.dumps(message)
        )
```

### WebSocket vs SSE Comparison

| Feature | WebSocket | Server-Sent Events (SSE) |
|---------|-----------|--------------------------|
| **Direction** | Bidirectional (full-duplex) | Unidirectional (server → client) |
| **Protocol** | Custom over TCP | HTTP (EventSource API) |
| **Complexity** | High (connection management) | Low (built-in browser API) |
| **Use Cases** | Chat, gaming, collaboration | Notifications, live feeds, progress |
| **Browser Support** | Excellent | Excellent (except IE11) |
| **Reconnection** | Manual | Automatic browser retry |
| **Scalability** | Requires Redis pub/sub | Simpler (just Redis pub/sub) |

### Recommendation
- Use **SSE** for notifications, live updates, progress bars
- Use **WebSocket** for chat, real-time collaboration, gaming

---

## 3. Plugin System Architecture

### Current State
- ❌ No plugin system
- ❌ No extensibility mechanism
- ✅ Dependency injection container
- ✅ Repository pattern (easily extendable)

### Proposed Architecture

```
┌───────────────────────────────────────────────────┐
│              Plugin Architecture                   │
├───────────────────────────────────────────────────┤
│                                                    │
│  ┌─────────────┐    ┌─────────────┐              │
│  │   Plugin    │    │   Plugin    │              │
│  │  Manager    │───►│   Loader    │              │
│  └──────┬──────┘    └─────────────┘              │
│         │                                          │
│         ▼                                          │
│  ┌─────────────┐    ┌─────────────┐              │
│  │   Plugin    │    │   Plugin    │              │
│  │  Registry   │◄───│  Interface  │              │
│  └──────┬──────┘    └─────────────┘              │
│         │                                          │
│         ▼                                          │
│  ┌─────────────────────────────────┐             │
│  │     Plugin Implementations       │             │
│  ├─────────────────────────────────┤             │
│  │  • Email Providers               │             │
│  │  • Payment Gateways              │             │
│  │  • Authentication Providers      │             │
│  │  • Storage Backends              │             │
│  │  • Search Engines                │             │
│  │  • Notification Channels         │             │
│  └─────────────────────────────────┘             │
└───────────────────────────────────────────────────┘
```

### Implementation Plan

#### Phase 1: Plugin Framework (Week 1)

**1.1 Plugin Interface**

```python
# src/infrastructure/plugins/base.py
from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")


class PluginMetadata(BaseModel):
    """Plugin metadata."""

    name: str
    version: str
    author: str
    description: str
    dependencies: list[str] = []
    config_schema: dict[str, Any] | None = None


class IPlugin(ABC, Generic[T]):
    """Base interface for all plugins.

    Example:
        class EmailPlugin(IPlugin[EmailConfig]):
            @property
            def metadata(self) -> PluginMetadata:
                return PluginMetadata(
                    name="sendgrid-email",
                    version="1.0.0",
                    author="Your Name",
                    description="SendGrid email provider",
                )

            async def initialize(self, config: EmailConfig) -> None:
                self.client = SendGridClient(api_key=config.api_key)

            async def send_email(self, to: str, subject: str, body: str) -> bool:
                return await self.client.send(to=to, subject=subject, body=body)
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        pass

    @abstractmethod
    async def initialize(self, config: T) -> None:
        """Initialize plugin with configuration.

        Args:
            config: Plugin-specific configuration
        """
        pass

    async def start(self) -> None:
        """Start plugin (optional hook)."""
        pass

    async def stop(self) -> None:
        """Stop plugin and cleanup resources (optional hook)."""
        pass

    async def health_check(self) -> bool:
        """Check plugin health (optional)."""
        return True
```

**1.2 Plugin Registry**

```python
# src/infrastructure/plugins/registry.py
from typing import Type, TypeVar, Generic
from collections import defaultdict

T = TypeVar("T", bound=IPlugin)


class PluginRegistry:
    """Central registry for plugin discovery and management."""

    def __init__(self):
        # {plugin_type: {plugin_name: plugin_class}}
        self._plugins: dict[str, dict[str, Type[IPlugin]]] = defaultdict(dict)

        # {plugin_type: {plugin_name: plugin_instance}}
        self._instances: dict[str, dict[str, IPlugin]] = defaultdict(dict)

    def register(
        self,
        plugin_type: str,
        plugin_class: Type[T],
    ) -> None:
        """Register a plugin class.

        Args:
            plugin_type: Plugin category (e.g., "email", "storage")
            plugin_class: Plugin class to register
        """
        metadata = plugin_class().metadata
        self._plugins[plugin_type][metadata.name] = plugin_class

        logger.info(
            "plugin_registered",
            plugin_type=plugin_type,
            plugin_name=metadata.name,
            version=metadata.version,
        )

    def get_plugin_class(
        self,
        plugin_type: str,
        plugin_name: str,
    ) -> Type[IPlugin] | None:
        """Get registered plugin class.

        Args:
            plugin_type: Plugin category
            plugin_name: Plugin name

        Returns:
            Plugin class or None if not found
        """
        return self._plugins.get(plugin_type, {}).get(plugin_name)

    def list_plugins(self, plugin_type: str) -> list[PluginMetadata]:
        """List all registered plugins of a type.

        Args:
            plugin_type: Plugin category

        Returns:
            List of plugin metadata
        """
        plugins = self._plugins.get(plugin_type, {})
        return [plugin_class().metadata for plugin_class in plugins.values()]

    async def get_instance(
        self,
        plugin_type: str,
        plugin_name: str,
        config: Any,
    ) -> IPlugin:
        """Get or create plugin instance.

        Args:
            plugin_type: Plugin category
            plugin_name: Plugin name
            config: Plugin configuration

        Returns:
            Initialized plugin instance
        """
        # Check if already instantiated
        if plugin_name in self._instances[plugin_type]:
            return self._instances[plugin_type][plugin_name]

        # Create new instance
        plugin_class = self.get_plugin_class(plugin_type, plugin_name)
        if not plugin_class:
            raise ValueError(f"Plugin not found: {plugin_type}/{plugin_name}")

        instance = plugin_class()
        await instance.initialize(config)

        # Cache instance
        self._instances[plugin_type][plugin_name] = instance

        return instance


# Global registry
plugin_registry = PluginRegistry()


def register_plugin(plugin_type: str):
    """Decorator to register a plugin.

    Example:
        @register_plugin("email")
        class SendGridEmailPlugin(IPlugin[EmailConfig]):
            # implementation
    """
    def decorator(cls: Type[IPlugin]) -> Type[IPlugin]:
        plugin_registry.register(plugin_type, cls)
        return cls
    return decorator
```

**1.3 Plugin Manager**

```python
# src/infrastructure/plugins/manager.py
from pathlib import Path
import importlib.util
import sys

class PluginManager:
    """Manages plugin lifecycle (discovery, loading, initialization)."""

    def __init__(
        self,
        plugin_dirs: list[Path],
        registry: PluginRegistry,
    ):
        self._plugin_dirs = plugin_dirs
        self._registry = registry
        self._loaded_modules: dict[str, Any] = {}

    async def discover_and_load(self) -> None:
        """Discover and load all plugins from plugin directories.

        Plugin structure:
            plugins/
                email_sendgrid/
                    __init__.py  # Contains plugin class
                    plugin.toml  # Metadata
                payment_stripe/
                    __init__.py
                    plugin.toml
        """
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                continue

            for plugin_path in plugin_dir.iterdir():
                if plugin_path.is_dir() and (plugin_path / "__init__.py").exists():
                    await self._load_plugin(plugin_path)

    async def _load_plugin(self, plugin_path: Path) -> None:
        """Load a single plugin module.

        Args:
            plugin_path: Path to plugin directory
        """
        plugin_name = plugin_path.name

        try:
            # Read plugin metadata
            metadata_path = plugin_path / "plugin.toml"
            if metadata_path.exists():
                import toml
                metadata = toml.load(metadata_path)

            # Load plugin module
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_name}",
                plugin_path / "__init__.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugins.{plugin_name}"] = module
            spec.loader.exec_module(module)

            self._loaded_modules[plugin_name] = module

            logger.info("plugin_loaded", plugin_name=plugin_name)

        except Exception as e:
            logger.error(
                "plugin_load_failed",
                plugin_name=plugin_name,
                error=str(e)
            )

    async def start_all_plugins(self, configs: dict[str, dict[str, Any]]) -> None:
        """Start all loaded plugins with their configurations.

        Args:
            configs: {plugin_type: {plugin_name: config}}
        """
        for plugin_type, plugins in self._registry._plugins.items():
            for plugin_name in plugins.keys():
                config = configs.get(plugin_type, {}).get(plugin_name)
                if config:
                    plugin = await self._registry.get_instance(
                        plugin_type, plugin_name, config
                    )
                    await plugin.start()

    async def stop_all_plugins(self) -> None:
        """Stop all running plugins."""
        for plugin_type, instances in self._registry._instances.items():
            for plugin_name, instance in instances.items():
                try:
                    await instance.stop()
                except Exception as e:
                    logger.error(
                        "plugin_stop_failed",
                        plugin_type=plugin_type,
                        plugin_name=plugin_name,
                        error=str(e)
                    )
```

#### Phase 2: Built-in Plugin Types (Week 2)

**2.1 Email Provider Plugin**

```python
# src/infrastructure/plugins/email.py
from abc import abstractmethod
from pydantic import BaseModel, EmailStr

class EmailConfig(BaseModel):
    """Base email plugin configuration."""
    from_email: EmailStr
    from_name: str


class IEmailPlugin(IPlugin[EmailConfig]):
    """Interface for email provider plugins."""

    @abstractmethod
    async def send_email(
        self,
        to: EmailStr,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> bool:
        """Send an email.

        Returns:
            True if sent successfully
        """
        pass


# Example implementation: SendGrid
@register_plugin("email")
class SendGridEmailPlugin(IEmailPlugin):
    """SendGrid email provider."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="sendgrid",
            version="1.0.0",
            author="Python Fast Forge",
            description="SendGrid email provider",
        )

    async def initialize(self, config: EmailConfig) -> None:
        from sendgrid import SendGridAPIClient
        self.client = SendGridAPIClient(api_key=config.api_key)
        self.from_email = config.from_email
        self.from_name = config.from_name

    async def send_email(
        self,
        to: EmailStr,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> bool:
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=(self.from_email, self.from_name),
            to_emails=to,
            subject=subject,
            html_content=body_html,
            plain_text_content=body_text,
        )

        try:
            response = await self.client.send(message)
            return response.status_code == 202
        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return False
```

**2.2 Storage Provider Plugin**

```python
# src/infrastructure/plugins/storage.py
from abc import abstractmethod
from io import BytesIO

class IStoragePlugin(IPlugin):
    """Interface for storage backends (S3, GCS, Azure Blob, local)."""

    @abstractmethod
    async def upload(
        self,
        file_path: str,
        content: bytes | BytesIO,
        content_type: str | None = None,
    ) -> str:
        """Upload file and return URL."""
        pass

    @abstractmethod
    async def download(self, file_path: str) -> bytes:
        """Download file content."""
        pass

    @abstractmethod
    async def delete(self, file_path: str) -> bool:
        """Delete file."""
        pass

    @abstractmethod
    async def get_presigned_url(
        self,
        file_path: str,
        expires_in: int = 3600,
    ) -> str:
        """Get presigned URL for direct download."""
        pass


@register_plugin("storage")
class S3StoragePlugin(IStoragePlugin):
    """AWS S3 storage provider."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="s3",
            version="1.0.0",
            author="Python Fast Forge",
            description="AWS S3 storage backend",
        )

    async def initialize(self, config: dict) -> None:
        import aioboto3
        self.session = aioboto3.Session()
        self.bucket = config['bucket']
        self.region = config.get('region', 'us-east-1')

    async def upload(
        self,
        file_path: str,
        content: bytes | BytesIO,
        content_type: str | None = None,
    ) -> str:
        async with self.session.client('s3') as s3:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type

            await s3.put_object(
                Bucket=self.bucket,
                Key=file_path,
                Body=content,
                **extra_args
            )

            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{file_path}"

    # ... other methods
```

**2.3 Authentication Provider Plugin**

```python
# src/infrastructure/plugins/auth.py
from abc import abstractmethod

class IAuthPlugin(IPlugin):
    """Interface for authentication providers (OAuth2, SAML, LDAP)."""

    @abstractmethod
    async def authenticate(
        self,
        credentials: dict[str, Any],
    ) -> tuple[bool, dict[str, Any] | None]:
        """Authenticate user.

        Returns:
            Tuple of (success, user_info)
        """
        pass

    @abstractmethod
    async def get_authorization_url(self, redirect_uri: str) -> str:
        """Get OAuth2 authorization URL."""
        pass


@register_plugin("auth")
class GoogleOAuthPlugin(IAuthPlugin):
    """Google OAuth2 authentication."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="google-oauth",
            version="1.0.0",
            author="Python Fast Forge",
            description="Google OAuth2 authentication",
        )

    async def initialize(self, config: dict) -> None:
        from authlib.integrations.starlette_client import OAuth
        self.oauth = OAuth()
        self.oauth.register(
            name='google',
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    # ... implementation
```

### Plugin Configuration

```yaml
# config/plugins.yaml
email:
  provider: sendgrid
  config:
    api_key: ${SENDGRID_API_KEY}
    from_email: noreply@example.com
    from_name: "My App"

storage:
  provider: s3
  config:
    bucket: my-app-uploads
    region: us-east-1
    access_key: ${AWS_ACCESS_KEY}
    secret_key: ${AWS_SECRET_KEY}

auth:
  providers:
    - name: google-oauth
      config:
        client_id: ${GOOGLE_CLIENT_ID}
        client_secret: ${GOOGLE_CLIENT_SECRET}

    - name: github-oauth
      config:
        client_id: ${GITHUB_CLIENT_ID}
        client_secret: ${GITHUB_CLIENT_SECRET}

payment:
  provider: stripe
  config:
    api_key: ${STRIPE_API_KEY}
    webhook_secret: ${STRIPE_WEBHOOK_SECRET}
```

### Plugin Usage in Application

```python
# In use case or service
from src.infrastructure.plugins import plugin_registry

class CreateUserUseCase:
    def __init__(self):
        # Get email plugin instance
        self.email_plugin = await plugin_registry.get_instance(
            "email",
            "sendgrid",
            config=get_email_config()
        )

    async def execute(self, command: CreateUserCommand) -> UUID:
        # Create user...

        # Send welcome email via plugin
        await self.email_plugin.send_email(
            to=user.email,
            subject="Welcome!",
            body_html="<h1>Welcome to our platform!</h1>",
        )

        return user.id
```

---

## 4. Message Queue Integration (RabbitMQ/Kafka)

### Current State
- ✅ Temporal workflows (email sending)
- ❌ No general-purpose message queue
- ❌ No job scheduling (CRON)
- ❌ No retry/dead-letter queues

### Proposed Architecture

```
┌──────────────┐     Publish     ┌──────────────┐
│   API/Use    │────────────────►│   Message    │
│    Case      │     Message     │    Queue     │
└──────────────┘                 │ (RabbitMQ)   │
                                 └───────┬──────┘
                                         │
                              ┌──────────┴──────────┐
                              │   Exchange Router    │
                              └──────────┬──────────┘
                                         │
                        ┌────────────────┼────────────────┐
                        │                │                │
                   ┌────▼────┐    ┌─────▼────┐    ┌─────▼────┐
                   │  Queue  │    │  Queue   │    │  Queue   │
                   │ (email) │    │ (report) │    │  (task)  │
                   └────┬────┘    └────┬─────┘    └────┬─────┘
                        │              │               │
                   ┌────▼────┐    ┌────▼─────┐   ┌────▼─────┐
                   │ Worker  │    │  Worker  │   │  Worker  │
                   │  Pool   │    │   Pool   │   │   Pool   │
                   └─────────┘    └──────────┘   └──────────┘
```

### Implementation (Week 1-2)

**4.1 Message Queue Abstraction**

```python
# src/infrastructure/messaging/queue.py
from abc import ABC, abstractmethod
from typing import Callable, Any
from pydantic import BaseModel

class Message(BaseModel):
    """Message envelope."""

    id: str
    type: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Retry metadata
    attempts: int = 0
    max_attempts: int = 3
    retry_delay: int = 60  # seconds


class IMessageQueue(ABC):
    """Interface for message queue implementations."""

    @abstractmethod
    async def publish(
        self,
        queue_name: str,
        message: Message,
        delay: int = 0,
    ) -> None:
        """Publish message to queue."""
        pass

    @abstractmethod
    async def consume(
        self,
        queue_name: str,
        handler: Callable[[Message], bool],
        prefetch_count: int = 10,
    ) -> None:
        """Consume messages from queue."""
        pass

    @abstractmethod
    async def ack(self, message: Message) -> None:
        """Acknowledge message processing."""
        pass

    @abstractmethod
    async def nack(self, message: Message, requeue: bool = True) -> None:
        """Negative acknowledge (reject) message."""
        pass


# RabbitMQ implementation
class RabbitMQQueue(IMessageQueue):
    """RabbitMQ implementation."""

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self.connection = None
        self.channel = None

    async def connect(self):
        import aio_pika
        self.connection = await aio_pika.connect_robust(self.connection_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=10)

    async def publish(
        self,
        queue_name: str,
        message: Message,
        delay: int = 0,
    ) -> None:
        import aio_pika

        # Declare queue
        queue = await self.channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                'x-max-priority': 10,  # Priority queue
                'x-message-ttl': 86400000,  # 24h TTL
            }
        )

        # Prepare message
        body = message.model_dump_json().encode()

        # Delayed delivery
        properties = aio_pika.DeliveryMode.PERSISTENT
        if delay > 0:
            # Use delay queue pattern
            await self._publish_delayed(queue_name, message, delay)
        else:
            await self.channel.default_exchange.publish(
                aio_pika.Message(body=body, delivery_mode=properties),
                routing_key=queue_name,
            )

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[Message], bool],
        prefetch_count: int = 10,
    ) -> None:
        queue = await self.channel.declare_queue(queue_name, durable=True)

        async with queue.iterator() as queue_iter:
            async for raw_message in queue_iter:
                try:
                    message = Message.model_validate_json(raw_message.body)

                    # Call handler
                    success = await handler(message)

                    if success:
                        await raw_message.ack()
                    else:
                        # Retry logic
                        if message.attempts < message.max_attempts:
                            message.attempts += 1
                            await self.publish(
                                queue_name,
                                message,
                                delay=message.retry_delay * (2 ** message.attempts)
                            )
                            await raw_message.ack()
                        else:
                            # Move to dead letter queue
                            await self.publish(f"{queue_name}.dlq", message)
                            await raw_message.ack()

                except Exception as e:
                    logger.error("message_processing_failed", error=str(e))
                    await raw_message.nack(requeue=False)
```

**4.2 Job Scheduler**

```python
# src/infrastructure/messaging/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class JobScheduler:
    """CRON job scheduler using APScheduler."""

    def __init__(self, message_queue: IMessageQueue):
        self.scheduler = AsyncIOScheduler()
        self.queue = message_queue

    def schedule_job(
        self,
        job_id: str,
        cron_expression: str,
        queue_name: str,
        message_type: str,
        payload: dict,
    ) -> None:
        """Schedule recurring job.

        Example:
            scheduler.schedule_job(
                job_id="daily-report",
                cron_expression="0 9 * * *",  # Every day at 9 AM
                queue_name="reports",
                message_type="generate_daily_report",
                payload={"report_type": "sales"}
            )
        """
        async def job_function():
            message = Message(
                id=str(uuid7()),
                type=message_type,
                payload=payload,
            )
            await self.queue.publish(queue_name, message)

        self.scheduler.add_job(
            job_function,
            trigger=CronTrigger.from_crontab(cron_expression),
            id=job_id,
            replace_existing=True,
        )

    def start(self):
        self.scheduler.start()

    def stop(self):
        self.scheduler.shutdown()
```

---

## 5-8. Additional Enhancements (Summary)

Due to length constraints, here are condensed proposals:

### 5. Advanced Observability
- **Prometheus metrics** exporter
- **Grafana dashboards** (pre-built)
- **Distributed tracing** (Jaeger integration)
- **Log aggregation** (ELK stack)
- **Alerting** (Alert Manager rules)

### 6. API Gateway Pattern
- **GraphQL API** (Strawberry framework)
- **gRPC support** (Google Protocol Buffers)
- **API versioning** strategy (v1, v2 coexistence)
- **Rate limiting** per endpoint
- **API documentation** (OpenAPI 3.1)

### 7. Search & Analytics
- **Full-text search** (PostgreSQL + Elasticsearch)
- **Aggregation queries** (analytics endpoints)
- **Search suggestions** (autocomplete)
- **Faceted search** (filters)

### 8. Multi-Database Support
- **Read replicas** (PostgreSQL streaming replication)
- **Connection pooling** (PgBouncer)
- **Sharding strategy** (tenant-based)
- **Database migrations** (Alembic + Atlas)

---

## Implementation Roadmap

### Priority Matrix

| Enhancement | Impact | Effort | Priority | Timeline |
|-------------|--------|--------|----------|----------|
| **Event Sourcing + CQRS** | 🔥 High | High | P0 | 4-6 weeks |
| **Message Queue** | 🔥 High | Medium | P0 | 2-3 weeks |
| **WebSocket/SSE** | 🔥 High | Medium | P1 | 2-3 weeks |
| **Plugin System** | 🌟 Medium | Medium | P1 | 2-3 weeks |
| **Observability** | 🌟 Medium | Low | P1 | 1-2 weeks |
| **GraphQL** | 🟡 Low | High | P2 | 3-4 weeks |
| **Full-text Search** | 🟡 Low | Medium | P2 | 2-3 weeks |
| **Multi-DB** | 🟡 Low | High | P3 | 4-6 weeks |

### Phased Rollout

**Phase 1 (Weeks 1-6): Core Enhancements**
- Week 1-4: Event Sourcing + CQRS
- Week 5-6: Message Queue (RabbitMQ)

**Phase 2 (Weeks 7-12): Real-Time & Plugins**
- Week 7-9: WebSocket + SSE
- Week 10-12: Plugin System

**Phase 3 (Weeks 13-18): Advanced Features**
- Week 13-14: Observability stack
- Week 15-16: Full-text search
- Week 17-18: GraphQL API

**Phase 4 (Weeks 19-24): Scalability**
- Week 19-22: Read replicas + sharding
- Week 23-24: Performance optimization

---

## Conclusion

These enhancements will transform **python-fast-forge** into a **world-class, production-ready platform** with:

✅ **Event-Driven Architecture** (Event Sourcing + CQRS)
✅ **Real-Time Capabilities** (WebSocket + SSE)
✅ **Extensibility** (Plugin System)
✅ **Scalability** (Message Queue + Read Replicas)
✅ **Observability** (Full monitoring stack)
✅ **Flexibility** (Multiple API styles: REST, GraphQL, gRPC)

**Estimated Total Effort:** 24 weeks (6 months) with 2-3 engineers

**ROI:** Transform from boilerplate to enterprise-grade platform, supporting:
- 100K+ requests/second
- Real-time collaboration features
- Multi-tenant SaaS at scale
- Event-driven microservices architecture
