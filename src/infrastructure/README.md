# Infrastructure Layer

The **Infrastructure Layer** contains all technical implementations and external integrations. This is where framework-specific code lives - databases, caching, external APIs, messaging, logging, and more.

## 🎯 Purpose

The infrastructure layer provides **implementations** of interfaces defined in the application layer. It:
- Implements repository interfaces
- Manages database connections and sessions
- Integrates with external services (email, messaging, etc.)
- Provides caching mechanisms
- Handles configuration and settings
- Manages telemetry and logging
- Implements security and compliance features

## 📂 Structure

```
infrastructure/
├── persistence/           # Database configuration
│   ├── database.py       # SQLAlchemy async session
│   └── unit_of_work.py   # Transaction management
├── repositories/          # Repository implementations
│   ├── base_repository.py
│   ├── user_repository.py
│   └── mixins.py         # Reusable query patterns
├── cache/                 # Caching layer
│   ├── cache.py          # Redis cache implementation
│   └── strategies.py     # Cache invalidation strategies
├── security/              # Security implementations
│   ├── hmac_auth.py      # HMAC signature validation
│   └── rate_limiter.py   # Rate limiting
├── compliance/            # Enterprise compliance
│   ├── gdpr.py           # GDPR compliance
│   ├── hipaa.py          # HIPAA compliance
│   ├── iso27001.py       # ISO 27001 compliance
│   └── soc2.py           # SOC 2 compliance
├── config/                # Configuration management
│   ├── settings.py       # Pydantic settings
│   ├── security_settings.py
│   └── database_settings.py
├── telemetry/             # OpenTelemetry
│   ├── __init__.py       # Tracing setup
│   └── middleware.py     # Tracing middleware
├── logging/               # Structured logging
│   ├── config.py         # Logging configuration
│   └── sanitizer.py      # PII sanitization
├── patterns/              # Infrastructure patterns
│   ├── circuit_breaker.py
│   └── retry.py
├── plugins/               # Plugin system
│   ├── base.py           # Plugin interfaces
│   ├── manager.py        # Plugin manager
│   └── builtin/          # Built-in plugins
├── queue/                 # Message queue
│   ├── rabbitmq.py       # RabbitMQ implementation
│   └── redis.py          # Redis implementation
├── scheduler/             # Job scheduler
│   └── scheduler.py      # CRON-based scheduling
└── streaming/             # Real-time communication
    ├── websocket.py      # WebSocket manager
    └── sse.py            # Server-Sent Events
```

## 🔧 Key Components

### Repositories

Repositories implement data access using SQLAlchemy.

**Example:**
```python
class UserRepository(BaseRepository[User], IUserRepository):
    """SQLAlchemy implementation of user repository."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        query = select(User).where(User.email == email.lower())
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_active_users(
        self,
        tenant_id: UUID | None = None,
    ) -> list[User]:
        """List all active (non-deleted) users."""
        query = select(User).where(User.deleted_at.is_(None))

        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)

        result = await self._session.execute(query)
        return list(result.scalars().all())
```

### Caching

Redis-based caching with compression and TTL.

**Example:**
```python
class RedisCache(ICache):
    """Redis cache implementation with zstd compression."""

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        data = await self._redis.get(key)
        if data:
            return self._deserialize(data)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
    ) -> None:
        """Set value in cache with TTL."""
        data = self._serialize(value)
        await self._redis.setex(key, ttl, data)
```

### Configuration

Pydantic-based settings with environment variable support.

**Example:**
```python
class DatabaseSettings(BaseSettings):
    """Database configuration."""

    host: str = Field("localhost", env="DB_HOST")
    port: int = Field(5432, env="DB_PORT")
    name: str = Field("app_db", env="DB_NAME")
    user: str = Field(..., env="DB_USER")  # Required
    password: str = Field(..., env="DB_PASSWORD")  # Required

    @property
    def url(self) -> str:
        """Build database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    model_config = SettingsConfigDict(env_prefix="DB_")
```

### Circuit Breaker

Resilience pattern for external service calls.

**Example:**
```python
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    timeout_duration=60,
    expected_exception=httpx.HTTPError,
)

@circuit_breaker
async def call_external_api():
    """Call external API with circuit breaker protection."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

### Compliance

Enterprise compliance implementations (HIPAA, GDPR, ISO 27001, SOC 2).

**Example:**
```python
class HIPAACompliance:
    """HIPAA compliance implementation."""

    async def encrypt_phi(self, data: dict) -> bytes:
        """Encrypt Protected Health Information."""
        return self._fernet.encrypt(json.dumps(data).encode())

    async def log_audit_event(
        self,
        event_type: str,
        user_id: str,
        resource_type: str,
        action: str,
    ) -> None:
        """Log audit event per HIPAA §164.312(b)."""
        await self._audit_logger.log({
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "resource": resource_type,
            "action": action,
        })
```

## ✅ Design Rules

### Dependency Direction
- ✅ **Implements interfaces** from application layer
- ✅ **Uses domain entities** for data models
- ❌ **Does NOT define business logic** (that's domain)
- ❌ **Does NOT handle HTTP** (that's presentation)

### Responsibilities

**DO:**
- Implement repository interfaces
- Manage database connections
- Integrate with external services
- Handle technical configurations
- Provide caching and performance optimizations
- Implement security and compliance features

**DON'T:**
- Define business rules (that's domain)
- Orchestrate workflows (that's application)
- Handle HTTP requests (that's presentation)

## 🔧 Common Patterns

### Repository Pattern

```python
class BaseRepository(Generic[T], IRepository[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]):
        self._session = session
        self._model = model

    async def create(self, entity: T) -> T:
        """Create new entity."""
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def get_by_id(self, id: UUID) -> T | None:
        """Get entity by ID."""
        return await self._session.get(self._model, id)

    async def update(self, entity: T) -> T:
        """Update existing entity."""
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        """Delete entity (hard delete)."""
        await self._session.delete(entity)
        await self._session.flush()
```

### Unit of Work Pattern

```python
class UnitOfWork:
    """Manage database transactions."""

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self):
        self._session = self._session_factory()
        self.users = UserRepository(self._session)
        self.audit_log = AuditLogRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self._session.rollback()
        else:
            await self._session.commit()
        await self._session.close()
```

### Plugin Pattern

```python
class EmailPlugin(BasePlugin):
    """Email sending plugin."""

    name = "email"
    version = "1.0.0"
    dependencies = []

    async def initialize(self, config: dict) -> None:
        """Initialize email client."""
        self._smtp_client = SMTPClient(config)

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> None:
        """Send email."""
        await self._smtp_client.send(to, subject, body)
```

## 🧪 Testing

Infrastructure tests are integration tests with real dependencies:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_repository_create(db_session):
    """Test creating user via repository."""
    # Arrange
    repo = UserRepository(db_session)
    user = User(email="test@example.com", username="testuser")

    # Act
    created_user = await repo.create(user)

    # Assert
    assert created_user.id is not None
    assert created_user.email == "test@example.com"

    # Verify in database
    fetched_user = await repo.get_by_id(created_user.id)
    assert fetched_user is not None
```

## 🚀 Performance Optimizations

### Database Indexes

```python
class User(BaseEntity):
    """User with optimized indexes."""

    __table_args__ = (
        # Partial index for active users (99% of queries)
        Index(
            "ix_users_active",
            "id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Composite index for multi-tenant queries
        Index("ix_users_tenant_deleted", "tenant_id", "deleted_at"),
    )
```

### Connection Pooling

```python
engine = create_async_engine(
    database_url,
    pool_size=20,  # Number of connections to maintain
    max_overflow=10,  # Additional connections when needed
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
)
```

### Caching Strategy

```python
@cache_result(ttl=3600, key_prefix="user")
async def get_user(user_id: UUID) -> User:
    """Get user with caching."""
    return await repository.get_by_id(user_id)

# Cache invalidation
await cache.delete(f"user:{user_id}")
```

## 📊 Monitoring & Observability

### OpenTelemetry

```python
# Automatic instrumentation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
```

### Structured Logging

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    "user_created",
    user_id=str(user.id),
    email=user.email,
    tenant_id=str(user.tenant_id),
)
```

## 📖 Further Reading

- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Unit of Work Pattern](https://martinfowler.com/eaaCatalog/unitOfWork.html)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Database Performance](../../docs/how-to/database-migrations.md)
- [Caching Strategies](https://martinfowler.com/bliki/TwoHardThings.html)

---

**Key Principle:** The infrastructure layer is **replaceable**. You should be able to swap PostgreSQL for MongoDB, Redis for Memcached, or RabbitMQ for Kafka without affecting business logic.
