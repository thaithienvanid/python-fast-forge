# Presentation Layer

The **Presentation Layer** handles HTTP communication - receiving requests, validating input, calling use cases, and formatting responses. This layer knows about FastAPI, HTTP, and REST conventions.

## 🎯 Purpose

The presentation layer provides the **HTTP API interface** to the application. It:
- Defines API routes and endpoints
- Validates HTTP requests with Pydantic schemas
- Transforms DTOs ↔ Domain entities
- Handles HTTP errors and status codes
- Manages API dependencies (authentication, pagination, etc.)
- Generates OpenAPI documentation

## 📂 Structure

```
presentation/
├── api/                    # FastAPI application
│   ├── main.py            # FastAPI app setup
│   ├── dependencies.py    # Shared dependencies
│   └── v1/                # API version 1
│       ├── router.py      # Version router
│       └── endpoints/     # API endpoints
│           ├── users.py   # User endpoints
│           ├── health.py  # Health check
│           ├── websocket.py
│           ├── sse.py
│           └── compliance.py
├── schemas/                # Request/Response DTOs
│   ├── user.py            # User DTOs
│   ├── pagination.py      # Pagination DTOs
│   └── error.py           # Error DTOs
├── mappers/                # DTO ↔ Domain mapping
│   └── user_mapper.py     # User DTO mapper
└── middleware/             # HTTP middleware
    ├── error_handler.py   # Exception handling
    ├── correlation_id.py  # Request correlation
    └── security_headers.py
```

## 🎯 Key Components

### API Routes

FastAPI route handlers that delegate to use cases.

**Example:**
```python
@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    request: CreateUserRequest,
    create_user_use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)],
) -> UserResponse:
    """Create a new user.

    **Security:** Requires valid X-Tenant-Token if multi-tenancy is enabled.

    **Returns:**
    - **201:** User created successfully
    - **400:** Invalid input data
    - **409:** Email or username already exists
    - **422:** Validation error
    """
    # Convert DTO to command
    command = CreateUserCommand(
        email=request.email,
        username=request.username,
        tenant_id=tenant_id,
        commanded_by=tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        correlation_id=uuid4(),
        idempotency_key=uuid4(),
    )

    # Execute use case
    user = await create_user_use_case.execute(command)

    # Convert domain entity to response DTO
    return UserMapper.to_response(user)
```

### Request/Response Schemas (DTOs)

Pydantic models for HTTP validation.

**Request DTO:**
```python
class CreateUserRequest(BaseModel):
    """Request schema for creating a user."""

    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique username (alphanumeric + _-)",
        examples=["john_doe"],
    )
    full_name: str | None = Field(
        None,
        max_length=255,
        description="Full name (optional)",
        examples=["John Doe"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "john@example.com",
                "username": "john_doe",
                "full_name": "John Doe",
            }
        }
    )
```

**Response DTO:**
```python
class UserResponse(BaseModel):
    """Response schema for user data."""

    id: UUID = Field(..., description="User identifier")
    email: str = Field(..., description="Email address")
    username: str = Field(..., description="Username")
    full_name: str | None = Field(None, description="Full name")
    is_active: bool = Field(..., description="Active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)
```

### Mappers

Convert between DTOs and domain entities.

**Example:**
```python
class UserMapper:
    """Map between User entity and DTOs."""

    @staticmethod
    def to_response(user: User) -> UserResponse:
        """Convert domain entity to response DTO."""
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    def to_list_response(users: list[User]) -> list[UserResponse]:
        """Convert list of entities to response DTOs."""
        return [UserMapper.to_response(user) for user in users]
```

### Dependencies

FastAPI dependency injection for common operations.

**Example:**
```python
async def get_tenant_id(
    x_tenant_token: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> UUID | None:
    """Extract tenant ID from JWT token in X-Tenant-Token header."""
    if x_tenant_token:
        claims = decode_tenant_token(x_tenant_token, settings)
        return claims.tenant_id
    return None

async def get_pagination(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
) -> PaginationParams:
    """Get pagination parameters from query string."""
    return PaginationParams(skip=skip, limit=limit)
```

## ✅ Design Rules

### Dependency Direction
- ✅ **Depends on:** All layers (domain, application, infrastructure)
- ✅ **HTTP-specific code only**
- ❌ **No business logic** (delegate to use cases)
- ❌ **No database access** (use repositories via use cases)

### Responsibilities

**DO:**
- Handle HTTP requests/responses
- Validate input with Pydantic
- Transform DTOs ↔ Domain entities
- Return appropriate HTTP status codes
- Generate OpenAPI documentation
- Handle HTTP errors

**DON'T:**
- Implement business logic (use use cases)
- Access database directly (use repositories)
- Make external API calls (use services)
- Contain domain rules

## 🔧 Common Patterns

### CRUD Endpoints

```python
@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    use_case: Annotated[GetUserUseCase, Depends(get_get_user_use_case)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)],
) -> UserResponse:
    """Get user by ID."""
    query = UserDetailQuery(user_id=user_id, tenant_id=tenant_id)
    user = await use_case.execute(query)
    return UserMapper.to_response(user)

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)],
    use_case: Annotated[ListUsersUseCase, Depends(get_list_users_use_case)],
) -> list[UserResponse]:
    """List users with pagination."""
    query = UserListQuery(
        skip=pagination.skip,
        limit=pagination.limit,
        tenant_id=tenant_id,
    )
    users = await use_case.execute(query)
    return UserMapper.to_list_response(users)

@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    use_case: Annotated[UpdateUserUseCase, Depends(get_update_user_use_case)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)],
) -> UserResponse:
    """Update user."""
    command = UpdateUserCommand(
        user_id=user_id,
        email=request.email,
        username=request.username,
        tenant_id=tenant_id,
        commanded_by=tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        correlation_id=uuid4(),
    )
    user = await use_case.execute(command)
    return UserMapper.to_response(user)

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    use_case: Annotated[DeleteUserUseCase, Depends(get_delete_user_use_case)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)],
) -> None:
    """Soft delete user."""
    command = DeleteUserCommand(
        user_id=user_id,
        tenant_id=tenant_id,
        commanded_by=tenant_id or UUID("00000000-0000-0000-0000-000000000000"),
        correlation_id=uuid4(),
    )
    await use_case.execute(command)
```

### Error Handling

```python
@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(
    request: Request,
    exc: EntityNotFoundError,
) -> JSONResponse:
    """Handle entity not found errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ).model_dump(),
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(
    request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ).model_dump(),
    )
```

### Pagination

```python
class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int
    skip: int
    limit: int
    has_more: bool

@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users_paginated(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> PaginatedResponse[UserResponse]:
    """List users with pagination metadata."""
    users, total = await use_case.execute_with_count(query)

    return PaginatedResponse(
        items=UserMapper.to_list_response(users),
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        has_more=(pagination.skip + len(users)) < total,
    )
```

## 🧪 Testing

Presentation tests use FastAPI's test client:

```python
@pytest.mark.asyncio
async def test_create_user_success(client: AsyncClient):
    """Test creating user via API."""
    # Arrange
    payload = {
        "email": "test@example.com",
        "username": "testuser",
    }

    # Act
    response = await client.post("/api/v1/users", json=payload)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data
    assert "created_at" in data

@pytest.mark.asyncio
async def test_create_user_duplicate_email(client: AsyncClient):
    """Test creating user with duplicate email returns 409."""
    # Create first user
    await client.post("/api/v1/users", json={"email": "test@example.com", "username": "user1"})

    # Try to create duplicate
    response = await client.post("/api/v1/users", json={"email": "test@example.com", "username": "user2"})

    # Assert
    assert response.status_code == 409
    assert "already exists" in response.json()["message"].lower()
```

## 📊 API Versioning

```python
# v1 router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(users_router)
v1_router.include_router(health_router)

# Main app
app = FastAPI(title="Python Fast Forge")
app.include_router(v1_router, prefix="/api")

# Future v2 would be:
# v2_router = APIRouter(prefix="/v2", tags=["v2"])
# app.include_router(v2_router, prefix="/api")
```

## 🔒 Security

### Authentication

```python
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Get current authenticated user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication")

    token = authorization.replace("Bearer ", "")
    claims = decode_jwt_token(token)

    user = await user_repository.get_by_id(claims.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user
```

### Rate Limiting

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/users")
@limiter.limit("10/minute")
async def create_user(request: Request, ...):
    """Create user (rate limited to 10/min)."""
    ...
```

## 📖 Further Reading

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [REST API Best Practices](https://restfulapi.net/)
- [API Versioning](../../docs/explanation/api-versioning.md)
- [OpenAPI Specification](https://swagger.io/specification/)

---

**Key Principle:** The presentation layer is a **thin adapter** between HTTP and your use cases. Keep it simple - validate input, call use cases, return responses.
