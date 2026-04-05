# Domain Layer

The **Domain Layer** is the core of the application, containing business entities, rules, and logic that are completely independent of any framework, database, or external service.

## 🎯 Purpose

The domain layer represents the **business domain** - the problem space we're solving. It contains:
- **Entities:** Core business objects with identity
- **Value Objects:** Immutable objects defined by their attributes
- **Domain Events:** Things that happened in the domain
- **Business Rules:** Constraints and validations
- **Exceptions:** Domain-specific errors

## 📂 Structure

```
domain/
├── models/              # Domain entities (User, etc.)
│   ├── base.py         # Base entity class
│   └── user.py         # User entity
├── events/             # Domain events
│   ├── base.py         # Base event class
│   └── user_events.py  # User-related events
├── exceptions.py       # Domain exceptions
└── pagination.py       # Pagination value objects
```

## 🧱 Core Concepts

### Entities

Entities are objects with identity that persist over time.

**Characteristics:**
- Have unique identifier (usually UUID)
- Mutable (can change state)
- Defined by identity, not attributes
- Contain business logic and invariants

**Example:**
```python
class User(BaseEntity):
    """User entity with business rules."""

    id: UUID
    email: str
    username: str
    is_active: bool

    def activate(self) -> None:
        """Business rule: Activate user account."""
        self.is_active = True
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """Business rule: Deactivate user account."""
        self.is_active = False
        self.updated_at = datetime.now(UTC)
```

### Value Objects

Value objects are immutable objects defined by their attributes.

**Characteristics:**
- Immutable (frozen)
- No identity
- Compared by value, not ID
- Encapsulate business logic

**Example:**
```python
@dataclass(frozen=True)
class CursorPaginationRequest:
    """Cursor pagination value object."""

    cursor: str | None
    limit: int

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
```

### Domain Events

Events represent something that happened in the domain.

**Characteristics:**
- Immutable (frozen)
- Named in past tense
- Contain event metadata
- Trigger side effects

**Example:**
```python
class UserCreatedEvent(DomainEvent):
    """Event raised when a user is created."""

    user_id: UUID
    email: str
    username: str
    tenant_id: UUID | None
```

### Domain Exceptions

Exceptions specific to domain logic.

**Types:**
- `EntityNotFoundError` - Entity doesn't exist
- `ValidationError` - Business rule violation
- `BusinessRuleViolationError` - Workflow violation

**Example:**
```python
raise ValidationError(
    "User with this email already exists",
    details={"email": email}
)
```

## ✅ Design Rules

### Independence
- ✅ **No framework dependencies** (no FastAPI, SQLAlchemy)
- ✅ **Pure Python only**
- ✅ **No infrastructure concerns** (no database, cache, HTTP)
- ✅ **Testable without mocks**

### Responsibilities
- ✅ **Enforce business rules**
- ✅ **Validate invariants**
- ✅ **Encapsulate business logic**
- ❌ **NOT responsible for persistence, HTTP, etc.**

## 📋 Best Practices

### Entities

**DO:**
```python
class User(BaseEntity):
    email: str

    @validates("email")
    def normalize_email(self, key, value):
        """Business rule: Emails are case-insensitive."""
        return value.lower()
```

**DON'T:**
```python
class User(BaseEntity):
    email: str

    def save_to_database(self):  # ❌ Infrastructure concern
        db.session.add(self)
        db.session.commit()
```

### Business Rules

Business rules belong in the domain layer:
- Email normalization (lowercase)
- Username validation (alphanumeric + _-)
- Account activation/deactivation
- Soft delete semantics

### Validation

Validation should happen at domain boundaries:

```python
class User(BaseEntity):
    username: str

    @validates("username")
    def validate_username(self, key, value):
        """Enforce username business rules."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise ValidationError("Username must be alphanumeric")
        if len(value) < 3:
            raise ValidationError("Username must be at least 3 characters")
        return value
```

## 🧪 Testing

Domain layer tests are pure unit tests with no mocks needed:

```python
def test_user_email_normalization():
    """Test email normalization business rule."""
    user = User(
        id=uuid4(),
        email="User@EXAMPLE.COM",
        username="testuser"
    )

    # Business rule: Email should be lowercase
    assert user.email == "user@example.com"
```

## 📊 Relationships

### With Other Layers

**Application Layer:**
- Uses domain entities in use cases
- Emits domain events
- Catches domain exceptions

**Infrastructure Layer:**
- Maps domain entities to database models
- Implements repository interfaces
- Persists domain events

**Presentation Layer:**
- Converts domain entities to DTOs
- Maps DTOs to domain entities
- Translates domain exceptions to HTTP responses

## 🚀 Examples

### Complete Entity

```python
class User(BaseEntity):
    """User entity with full business logic."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[UUID | None] = mapped_column(UUID, nullable=True)

    @validates("email")
    def normalize_email(self, key, value):
        return value.lower()

    def activate(self) -> None:
        """Activate user account (business rule)."""
        if self.is_active:
            raise BusinessRuleViolationError("User is already active")
        self.is_active = True

    def belongs_to_tenant(self, tenant_id: UUID) -> bool:
        """Check if user belongs to given tenant."""
        return self.tenant_id == tenant_id
```

### Domain Event

```python
class UserActivatedEvent(DomainEvent):
    """Event raised when user is activated."""

    user_id: UUID
    email: str
    activated_by: UUID
    reason: str | None = None
```

## 📖 Further Reading

- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [Entities vs Value Objects](https://martinfowler.com/bliki/EvansClassification.html)
- [Domain Events](https://martinfowler.com/eaaDev/DomainEvent.html)
- [Clean Architecture - Domain Layer](../../docs/explanation/clean-architecture.md)

---

**Remember:** The domain layer should be understandable by domain experts who may not be programmers. Keep it pure, simple, and focused on business logic.
