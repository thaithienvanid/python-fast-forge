# How-To: Add a New API Endpoint

**Time:** 5-10 minutes
**Difficulty:** Beginner
**Prerequisites:** Understanding of [Clean Architecture](../reference/architecture.md)

## Quick Reference

Follow these steps to add a new API endpoint:

1. [Create/update domain model](#step-1-domain-model)
2. [Create/update repository interface](#step-2-repository-interface)
3. [Implement repository](#step-3-repository-implementation)
4. [Create use case](#step-4-use-case)
5. [Create API schema](#step-5-api-schema)
6. [Create endpoint](#step-6-endpoint)
7. [Register in container](#step-7-dependency-injection)
8. [Register router](#step-8-router-registration)
9. [Test](#step-9-test)

## Complete Example: Add "Get User by Email" Endpoint

### Step 1: Domain Model

If the entity already exists, skip this step. Otherwise, create the model:

```python
# src/domain/models/user.py
class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

### Step 2: Repository Interface

Add method to the repository interface:

```python
# src/domain/interfaces.py
class IUserRepository(IRepository[User]):
    """User repository interface."""

    # Existing methods...
    async def get_by_id(self, user_id: UUID) -> User | None:
        ...

    # NEW METHOD
    async def get_by_email(self, email: str, tenant_id: UUID | None = None) -> User | None:
        """Get user by email with optional tenant filtering."""
        ...
```

### Step 3: Repository Implementation

Implement the method in the concrete repository:

```python
# src/infrastructure/repositories/user_repository.py
from sqlalchemy import select

class UserRepository(BaseRepository[User], IUserRepository):

    # NEW METHOD IMPLEMENTATION
    async def get_by_email(self, email: str, tenant_id: UUID | None = None) -> User | None:
        query = select(User).where(User.email == email)

        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)

        result = await self._session.execute(query)
        return result.scalar_one_or_none()
```

### Step 4: Use Case

Create a new use case for this operation:

```python
# src/app/usecases/user_usecases.py
class GetUserByEmailUseCase:
    """Use case for getting a user by email."""

    def __init__(self, user_repository: IUserRepository[User]) -> None:
        self._repository = user_repository

    async def execute(self, email: str, tenant_id: UUID | None = None) -> User:
        """Get user by email.

        Args:
            email: User's email address
            tenant_id: Optional tenant ID for isolation

        Returns:
            User entity

        Raises:
            EntityNotFoundError: If user not found
            ValidationError: If email format invalid
        """
        # Validate email format
        if "@" not in email:
            raise ValidationError("Invalid email format")

        # Get user
        user = await self._repository.get_by_email(email, tenant_id)

        if not user:
            raise EntityNotFoundError(f"User with email {email} not found")

        return user
```

**Export the use case:**

```python
# src/app/usecases/user_usecases.py
__all__ = [
    "GetUserByEmailUseCase",  # Add this
    # ... other use cases
]
```

### Step 5: API Schema

Use existing schemas or create new ones if needed:

```python
# src/presentation/schemas/user.py (already exists)
class UserResponse(BaseModel):
    """Schema for user response."""

    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

### Step 6: Endpoint

Add the endpoint to the existing router:

```python
# src/presentation/api/v1/endpoints/users.py
from src.app.usecases.user_usecases import GetUserByEmailUseCase  # Add import

@router.get(
    "/by-email",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get User by Email",
    description="Retrieve a user by their email address with optional tenant filtering",
    responses={
        status.HTTP_200_OK: {
            "description": "User found successfully",
            "model": UserResponse,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "User not found",
            "model": ErrorResponse,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid email format",
            "model": ErrorResponse,
        },
    },
)
@inject
async def get_user_by_email(
    email: Annotated[str, Query(description="User's email address", min_length=3)],
    use_case: Annotated[
        GetUserByEmailUseCase,
        Depends(Provide[Container.use_cases.get_user_by_email])
    ],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> UserResponse:
    """Get user by email address."""
    user = await use_case.execute(email=email, tenant_id=tenant_id)
    return UserResponse.model_validate(user)
```

### Step 7: Dependency Injection

Register the use case in the container:

```python
# src/container.py
from src.app.usecases.user_usecases import GetUserByEmailUseCase  # Add import

class Container(containers.DeclarativeContainer):
    # ... existing code ...

    # In use_cases provider:
    use_cases = providers.FactoryAggregate(
        # ... existing use cases ...
        get_user_by_email=providers.Factory(  # ADD THIS
            GetUserByEmailUseCase,
            user_repository=user_repository,
        ),
    )
```

### Step 8: Router Registration

Router should already be registered (users.router). If creating a new router:

```python
# src/presentation/api/v1/__init__.py
from src.presentation.api.v1.endpoints import users  # Already imported

api_router = APIRouter(prefix="/v1")
api_router.include_router(users.router)  # Already registered
```

### Step 9: Test

**Restart the application:**

```bash
docker-compose restart api
```

**Test with curl:**

```bash
curl "http://localhost:8000/api/v1/users/by-email?email=john@example.com"
```

**Expected response (200 OK):**
```json
{
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "email": "john@example.com",
  "username": "john_doe",
  "full_name": "John Doe",
  "is_active": true,
  "tenant_id": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**View in Swagger UI:** http://localhost:8000/docs

## Common Patterns

### GET Endpoint (Retrieve Resource)

```python
@router.get("/{resource_id}", response_model=ResourceResponse)
@inject
async def get_resource(
    resource_id: Annotated[UUID, Path(description="Resource ID")],
    use_case: Annotated[GetResourceUseCase, Depends(...)],
) -> ResourceResponse:
    resource = await use_case.execute(resource_id=resource_id)
    return ResourceResponse.model_validate(resource)
```

### POST Endpoint (Create Resource)

```python
@router.post("", response_model=ResourceResponse, status_code=201)
@inject
async def create_resource(
    input: ResourceCreate,  # Pydantic request schema
    use_case: Annotated[CreateResourceUseCase, Depends(...)],
) -> ResourceResponse:
    resource = await use_case.execute(**input.dict())
    return ResourceResponse.model_validate(resource)
```

### PUT Endpoint (Update Resource)

```python
@router.put("/{resource_id}", response_model=ResourceResponse)
@inject
async def update_resource(
    resource_id: Annotated[UUID, Path()],
    input: ResourceUpdate,
    use_case: Annotated[UpdateResourceUseCase, Depends(...)],
) -> ResourceResponse:
    resource = await use_case.execute(resource_id=resource_id, **input.dict(exclude_unset=True))
    return ResourceResponse.model_validate(resource)
```

### DELETE Endpoint (Delete Resource)

```python
@router.delete("/{resource_id}", status_code=204)
@inject
async def delete_resource(
    resource_id: Annotated[UUID, Path()],
    use_case: Annotated[DeleteResourceUseCase, Depends(...)],
) -> None:
    await use_case.execute(resource_id=resource_id)
    # 204 No Content - no return value
```

### LIST Endpoint (Get Multiple Resources)

```python
@router.get("", response_model=ResourceListResponse)
@inject
async def list_resources(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    use_case: Annotated[ListResourcesUseCase, Depends(...)],
) -> ResourceListResponse:
    resources = await use_case.execute(skip=skip, limit=limit)
    return ResourceListResponse(
        items=[ResourceResponse.model_validate(r) for r in resources],
        total=len(resources),
        skip=skip,
        limit=limit,
    )
```

## Advanced Patterns

### Multi-Tenancy Support

Always add `tenant_id` parameter for tenant isolation:

```python
@router.get("/{resource_id}")
@inject
async def get_resource(
    resource_id: Annotated[UUID, Path()],
    use_case: Annotated[GetResourceUseCase, Depends(...)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,  # ADD THIS
) -> ResourceResponse:
    resource = await use_case.execute(resource_id=resource_id, tenant_id=tenant_id)
    return ResourceResponse.model_validate(resource)
```

### Query Parameters with Filtering

```python
@router.get("", response_model=ResourceListResponse)
@inject
async def list_resources(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    status: Annotated[str | None, Query()] = None,  # Filter by status
    search: Annotated[str | None, Query(min_length=3)] = None,  # Search query
    use_case: Annotated[ListResourcesUseCase, Depends(...)],
) -> ResourceListResponse:
    resources = await use_case.execute(
        skip=skip,
        limit=limit,
        status=status,
        search=search,
    )
    return ResourceListResponse(...)
```

### File Upload

```python
from fastapi import File, UploadFile

@router.post("/upload", status_code=201)
@inject
async def upload_file(
    file: Annotated[UploadFile, File(description="File to upload")],
    use_case: Annotated[UploadFileUseCase, Depends(...)],
) -> dict:
    file_url = await use_case.execute(
        filename=file.filename,
        content=await file.read(),
        content_type=file.content_type,
    )
    return {"file_url": file_url}
```

### Background Task Trigger

```python
from fastapi import BackgroundTasks

@router.post("/send-email", status_code=202)
@inject
async def send_email(
    input: EmailRequest,
    background_tasks: BackgroundTasks,
    use_case: Annotated[SendEmailUseCase, Depends(...)],
) -> dict:
    # Trigger background task
    background_tasks.add_task(use_case.execute, email=input.email, message=input.message)
    return {"status": "Email queued for sending"}
```

## Checklist

Before committing your new endpoint:

- [ ] Domain model exists or created
- [ ] Repository interface method added
- [ ] Repository implementation added
- [ ] Use case created with business logic
- [ ] Use case exported in `__all__`
- [ ] API schemas defined (request + response)
- [ ] Endpoint created with proper decorators
- [ ] OpenAPI docs added (summary, description, responses)
- [ ] Use case registered in container
- [ ] Router registered (if new router)
- [ ] Endpoint tested with curl
- [ ] Endpoint visible in Swagger UI
- [ ] Multi-tenancy support added (if applicable)
- [ ] Error handling added (try/except if needed)
- [ ] Tests written (unit + integration)

## Troubleshooting

**Problem:** 404 Not Found

**Solutions:**
1. Check router is registered: `api_router.include_router(...)`
2. Check prefix is correct: `/api/v1/users`
3. Restart API: `docker-compose restart api`

**Problem:** Dependency injection fails

**Solutions:**
1. Check use case is registered in container
2. Check import path is correct
3. Check `@inject` decorator is present
4. Check wiring includes the module

**Problem:** 422 Validation Error

**Solutions:**
1. Check Pydantic schema matches request body
2. Check required fields are provided
3. Check field types match (UUID, int, str, etc.)
4. Use Swagger UI to see expected schema

**Problem:** 500 Internal Server Error

**Solutions:**
1. Check logs: `docker-compose logs api`
2. Check use case logic (exceptions not caught)
3. Check repository implementation
4. Enable DEBUG mode for detailed errors

## Next Steps

- **Write tests:** [Testing Guide](../reference/testing.md)
- **Add validation:** [Input Validation Best Practices](../explanation/validation.md)
- **Learn Clean Architecture:** [Architecture Reference](../reference/architecture.md)
- **Build tutorial:** [First API Tutorial](../tutorials/01-first-api.md)

## Further Reading

- [FastAPI Path Operations](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Pydantic Models](https://docs.pydantic.dev/latest/usage/models/)
- [Clean Architecture](../reference/architecture.md)
