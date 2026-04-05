# Source Code Structure

This directory contains the core source code organized according to **Clean Architecture** principles with clear layer separation.

## 📐 Architecture Overview

The codebase follows a 4-layer Clean Architecture pattern:

```
┌─────────────────────────────────────────────────────────┐
│                  Presentation Layer                     │
│         (API routes, schemas, DTOs, mappers)            │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                  Application Layer                      │
│      (Use cases, orchestration, event handlers)         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                Infrastructure Layer                     │
│   (Database, cache, external APIs, implementations)     │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│                   Domain Layer                          │
│        (Entities, value objects, business rules)        │
└─────────────────────────────────────────────────────────┘
```

## 📂 Directory Structure

```
src/
├── domain/                 # Domain Layer (Core Business Logic)
│   ├── models/            # Domain entities (User, etc.)
│   ├── events/            # Domain events
│   ├── exceptions.py      # Domain-specific exceptions
│   └── pagination.py      # Pagination value objects
│
├── app/                   # Application Layer (Use Cases & Orchestration)
│   ├── usecases/         # Business use cases
│   ├── commands/         # CQRS command models
│   ├── queries/          # CQRS query models
│   ├── events/           # Event handlers
│   ├── tasks/            # Background tasks (Temporal)
│   └── decorators.py     # Cross-cutting concerns
│
├── infrastructure/        # Infrastructure Layer (Technical Implementations)
│   ├── persistence/      # Database configuration
│   ├── repositories/     # Data access repositories
│   ├── cache/           # Redis caching
│   ├── security/        # Security implementations
│   ├── compliance/      # HIPAA, GDPR, ISO 27001, SOC 2
│   ├── config/          # Application settings
│   ├── telemetry/       # OpenTelemetry tracing
│   ├── logging/         # Structured logging
│   ├── patterns/        # Circuit breaker, etc.
│   ├── plugins/         # Plugin system
│   ├── queue/           # Message queue (RabbitMQ, Redis)
│   ├── scheduler/       # Job scheduler
│   └── streaming/       # WebSocket, SSE
│
├── presentation/          # Presentation Layer (API Interface)
│   ├── api/              # FastAPI routes
│   │   └── v1/          # API version 1
│   │       └── endpoints/  # Endpoint handlers
│   ├── schemas/          # Request/response DTOs
│   ├── mappers/          # DTO ↔ Domain mapping
│   └── dependencies.py   # FastAPI dependencies
│
├── external/              # External Service Clients
│   └── email/            # Email service integrations
│
├── utils/                 # Shared Utilities
│   ├── json_encoder.py   # Custom JSON encoding
│   ├── correlation_id.py # Request correlation
│   └── tenant_auth.py    # Multi-tenant JWT auth
│
└── container.py           # Dependency Injection Container
```

## 🎯 Layer Responsibilities

### Domain Layer (`domain/`)
**Purpose:** Core business logic and entities
**Dependencies:** None (Pure Python)
**Examples:**
- User entity with business rules
- Value objects (Email, Money, etc.)
- Domain events (UserCreated, OrderPlaced)
- Domain exceptions

**Rules:**
- ✅ No external dependencies (frameworks, databases)
- ✅ Pure business logic only
- ✅ Framework-agnostic
- ❌ No infrastructure code (no SQLAlchemy, FastAPI, etc.)

### Application Layer (`app/`)
**Purpose:** Orchestrate use cases and workflows
**Dependencies:** Domain layer only
**Examples:**
- CreateUserUseCase
- SendWelcomeEmailTask
- UserEventHandlers
- CQRS commands/queries

**Rules:**
- ✅ Depends on domain layer
- ✅ Defines interfaces (repositories, services)
- ✅ Orchestrates business workflows
- ❌ No implementation details (how data is stored)

### Infrastructure Layer (`infrastructure/`)
**Purpose:** Technical implementations and external integrations
**Dependencies:** Domain & Application layers
**Examples:**
- PostgreSQL repository implementation
- Redis cache implementation
- OpenTelemetry tracing setup
- SMTP email sender

**Rules:**
- ✅ Implements interfaces from application layer
- ✅ Framework and library code
- ✅ External service integrations
- ✅ Technical configurations

### Presentation Layer (`presentation/`)
**Purpose:** API interface and data transformation
**Dependencies:** All layers
**Examples:**
- FastAPI route handlers
- Request/response schemas (DTOs)
- DTO ↔ Domain mappers
- API dependencies

**Rules:**
- ✅ HTTP-specific code
- ✅ Data validation (Pydantic)
- ✅ Request/response transformation
- ❌ No business logic (delegate to use cases)

## 🔀 Data Flow

**Request → Response:**
```
1. API Route (Presentation)
   ↓ validates request
2. DTO Mapper (Presentation)
   ↓ converts to command/query
3. Use Case (Application)
   ↓ executes business logic
4. Repository (Infrastructure)
   ↓ fetches/persists data
5. Domain Entity (Domain)
   ↓ enforces business rules
6. DTO Mapper (Presentation)
   ↓ converts to response schema
7. API Response (Presentation)
```

## 🧩 Key Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Repository** | `infrastructure/repositories/` | Abstract data access |
| **Unit of Work** | `infrastructure/persistence/` | Manage transactions |
| **Factory** | `container.py` | Dependency injection |
| **Decorator** | `app/decorators.py` | Cross-cutting concerns |
| **Event-Driven** | `app/events/` | Decouple business logic |
| **CQRS** | `app/commands/`, `app/queries/` | Separate reads/writes |
| **Circuit Breaker** | `infrastructure/patterns/` | Resilience |
| **Plugin System** | `infrastructure/plugins/` | Extensibility |

## 📖 Further Reading

- [Clean Architecture Guide](../docs/explanation/clean-architecture.md)
- [Architecture Reference](../docs/reference/architecture.md)
- [Design Decisions](../docs/explanation/design-decisions.md)
- [How to Add an Endpoint](../docs/how-to/add-endpoint.md)
- [How to Add a Model](../docs/how-to/add-model.md)

## 🚀 Getting Started

1. **Read the domain layer** (`domain/`) to understand business entities
2. **Check use cases** (`app/usecases/`) to see business workflows
3. **Review API routes** (`presentation/api/`) for HTTP endpoints
4. **Understand repositories** (`infrastructure/repositories/`) for data access

## ✅ Best Practices

### Adding New Features
1. Start with domain model (if needed)
2. Create use case in application layer
3. Implement repository/service in infrastructure
4. Add API endpoint in presentation layer
5. Write tests for all layers

### Dependency Rules
- **Outer layers** can depend on **inner layers**
- **Inner layers** NEVER depend on outer layers
- Use interfaces to invert dependencies

### Testing Strategy
- **Domain:** Unit tests (pure logic)
- **Application:** Unit tests with mocks
- **Infrastructure:** Integration tests
- **Presentation:** API tests with test client

---

**Note:** This structure ensures testability, maintainability, and clear separation of concerns. Changes to frameworks, databases, or external services should only affect the infrastructure layer, leaving business logic intact.
