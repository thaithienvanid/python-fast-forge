# Application Layer

The **Application Layer** orchestrates business workflows by coordinating domain entities, implementing use cases, and handling commands/queries. This layer is framework-independent but knows about the domain.

## 🎯 Purpose

The application layer implements **use cases** - the specific business operations that the system supports. It:
- Orchestrates domain entities and services
- Implements CQRS (Command Query Responsibility Segregation)
- Handles domain events
- Manages background tasks and workflows
- Defines repository and service interfaces

## 📂 Structure

```
app/
├── usecases/              # Business use cases
│   ├── user_usecases.py  # User-related operations
│   └── ...
├── commands/              # CQRS write operations
│   └── __init__.py       # CreateUserCommand, UpdateUserCommand, etc.
├── queries/               # CQRS read operations
│   └── __init__.py       # UserListQuery, UserDetailQuery, etc.
├── events/                # Event handling
│   ├── bus.py            # Event bus implementation
│   └── handlers/         # Event handlers
├── tasks/                 # Background tasks (Temporal workflows)
│   └── user_tasks.py     # Async user operations
└── decorators.py          # Cross-cutting concerns
```

## 🎯 Key Components

### Use Cases

Use cases encapsulate business operations from the perspective of a user or system.

**Characteristics:**
- Single responsibility (one business operation)
- Framework-independent
- Coordinate domain entities
- Define repository interfaces
- Handle transactions

**Example:**
```python
class CreateUserUseCase:
    """Use case for creating a new user."""

    def __init__(
        self,
        repository: IUserRepository,
        event_bus: IEventBus,
    ):
        self._repository = repository
        self._event_bus = event_bus

    @handle_integrity_errors
    async def execute(self, command: CreateUserCommand) -> User:
        """Execute the create user use case.

        Steps:
        1. Create domain entity
        2. Persist via repository
        3. Publish domain event
        """
        # Create domain entity
        user = User(
            email=command.email,
            username=command.username,
            tenant_id=command.tenant_id,
        )

        # Persist
        created_user = await self._repository.create(user)

        # Publish domain event
        await self._event_bus.publish(UserCreatedEvent(
            aggregate_id=created_user.id,
            email=created_user.email,
            username=created_user.username,
        ))

        return created_user
```

### CQRS - Commands

Commands represent write operations (create, update, delete).

**Characteristics:**
- Immutable (frozen=True)
- Explicit metadata (commanded_by, correlation_id)
- Validated by Pydantic
- Can fail

**Example:**
```python
class CreateUserCommand(BaseModel):
    """Command to create a new user."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    tenant_id: UUID | None

    # Command metadata
    commanded_by: UUID
    correlation_id: UUID
    idempotency_key: UUID

    model_config = ConfigDict(frozen=True)
```

### CQRS - Queries

Queries represent read operations (list, get, search).

**Characteristics:**
- Immutable (frozen=True)
- Optimized for reads
- Can use denormalized data
- Always succeed (return empty if not found)

**Example:**
```python
class UserListQuery(BaseModel):
    """Query for listing users with filters."""

    tenant_id: UUID | None
    is_active: bool | None
    email_contains: str | None
    skip: int = 0
    limit: int = 50

    model_config = ConfigDict(frozen=True)
```

### Event Handlers

Event handlers respond to domain events asynchronously.

**Characteristics:**
- Loosely coupled
- Can fail independently
- Idempotent
- Retry-able

**Example:**
```python
@event_bus.subscribe(UserCreatedEvent)
async def send_welcome_email_handler(event: UserCreatedEvent):
    """Send welcome email when user is created."""
    await email_service.send_welcome_email(
        to=event.email,
        username=event.username,
    )
```

### Background Tasks

Long-running or async operations using Temporal workflows.

**Example:**
```python
@workflow.defn
class SendWelcomeEmailWorkflow:
    """Temporal workflow for sending welcome email."""

    @workflow.run
    async def run(self, user_id: str, email: str) -> None:
        # Durable execution with automatic retries
        await workflow.execute_activity(
            send_email_activity,
            args=[user_id, email],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
```

## ✅ Design Rules

### Dependency Direction
- ✅ **Depends on:** Domain layer only
- ✅ **Defines interfaces** for repositories, services
- ❌ **Does NOT depend on:** Infrastructure or Presentation
- ❌ **Does NOT know about:** Databases, HTTP, frameworks

### Responsibilities

**DO:**
- Define use case workflows
- Orchestrate domain entities
- Define repository interfaces
- Publish domain events
- Handle commands and queries

**DON'T:**
- Implement database access (that's infrastructure)
- Handle HTTP requests (that's presentation)
- Contain framework-specific code
- Implement business rules (that's domain)

## 🔀 Use Case Patterns

### Basic Use Case Structure

```python
class SomeUseCase:
    """Template for use cases."""

    def __init__(
        self,
        repository: IRepository,  # Interface from application layer
        service: IService,        # Interface from application layer
    ):
        self._repository = repository
        self._service = service

    @handle_integrity_errors  # Decorator for cross-cutting concerns
    @log_use_case_execution("SomeUseCase")
    async def execute(self, command: SomeCommand) -> SomeEntity:
        """Execute use case logic."""
        # 1. Validate (optional - Pydantic does most validation)
        # 2. Create/fetch domain entities
        # 3. Apply business rules
        # 4. Persist via repository
        # 5. Publish events
        # 6. Return result
        pass
```

### Transaction Management

```python
async def execute(self, command: CreateUserCommand) -> User:
    """Use case with transaction management."""
    async with self._unit_of_work as uow:
        # Operations within transaction
        user = await uow.users.create(user)
        await uow.audit_log.log_create(user)

        # Commit happens automatically on exit
        return user
```

## 🎨 Decorators

Decorators handle cross-cutting concerns:

### `@handle_integrity_errors`
Converts database constraint errors to domain exceptions.

```python
@handle_integrity_errors
async def execute(self, command: CreateUserCommand) -> User:
    # IntegrityError automatically converted to ValidationError
    return await self._repository.create(user)
```

### `@log_use_case_execution`
Logs use case execution for observability.

```python
@log_use_case_execution("CreateUser")
async def execute(self, command: CreateUserCommand) -> User:
    # Automatically logs: use_case_started, use_case_completed, duration
    return await self._repository.create(user)
```

### `@validate_tenant_isolation`
Enforces multi-tenant security.

```python
@validate_tenant_isolation
async def execute(self, query: GetUserQuery) -> User:
    # Automatically validates tenant_id matches
    return await self._repository.get_by_id(query.user_id)
```

## 📊 Event-Driven Architecture

### Event Bus

```python
# Publishing events
await event_bus.publish(UserCreatedEvent(
    aggregate_id=user.id,
    email=user.email,
))

# Subscribing to events
@event_bus.subscribe(UserCreatedEvent)
async def handler(event: UserCreatedEvent):
    await do_something(event)
```

### Benefits
- **Decoupling:** Use cases don't know about email, analytics, etc.
- **Extensibility:** Add new handlers without modifying use cases
- **Resilience:** Handler failures don't affect use case success
- **Observability:** Clear event trail for debugging

## 🧪 Testing

Use cases are tested with mocked repositories:

```python
@pytest.mark.asyncio
async def test_create_user_success():
    """Test create user use case."""
    # Arrange
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.create.return_value = user
    mock_event_bus = Mock(spec=IEventBus)

    use_case = CreateUserUseCase(mock_repo, mock_event_bus)
    command = CreateUserCommand(...)

    # Act
    result = await use_case.execute(command)

    # Assert
    assert result.email == command.email
    mock_repo.create.assert_called_once()
    mock_event_bus.publish.assert_called_once()
```

## 🚀 Examples

### Complete Use Case

```python
class UpdateUserUseCase:
    """Use case for updating user information."""

    def __init__(
        self,
        repository: IUserRepository,
        event_bus: IEventBus,
        cache: ICache,
    ):
        self._repository = repository
        self._event_bus = event_bus
        self._cache = cache

    @handle_integrity_errors
    @log_use_case_execution("UpdateUser")
    @validate_tenant_isolation
    async def execute(self, command: UpdateUserCommand) -> User:
        """Update user with optimistic locking."""
        # Fetch current user
        user = await self._repository.get_by_id(command.user_id)

        # Check version for optimistic locking
        if user.version != command.expected_version:
            raise BusinessRuleViolationError("User was modified by another process")

        # Apply updates
        if command.email:
            user.email = command.email
        if command.username:
            user.username = command.username

        # Persist
        updated_user = await self._repository.update(user)

        # Invalidate cache
        await self._cache.delete(f"user:{user.id}")

        # Publish event
        await self._event_bus.publish(UserUpdatedEvent(
            aggregate_id=updated_user.id,
            updated_by=command.commanded_by,
        ))

        return updated_user
```

## 📖 Further Reading

- [Use Case Driven Development](https://herbertograca.com/2017/10/19/from-crm-to-ddd-no-5-use-case-driven-development/)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)
- [Domain Events](https://martinfowler.com/eaaDev/DomainEvent.html)
- [Application Layer in Clean Architecture](../../docs/explanation/clean-architecture.md)

---

**Key Principle:** The application layer is the glue between the domain (what) and infrastructure (how). It defines **what** needs to happen without specifying **how** it happens.
