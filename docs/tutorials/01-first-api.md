# Tutorial: Build Your First API Endpoint

**Time:** 15 minutes
**Difficulty:** Beginner
**Prerequisites:** [Installation Tutorial](00-installation.md) completed

## What You'll Build

In this tutorial, you'll create a complete API endpoint for managing "Tasks" (a simple to-do item). You'll learn:

- How to create domain models
- How to define API schemas
- How to implement use cases
- How to create API endpoints
- How to test your endpoint

By the end, you'll have a working `/api/v1/tasks` endpoint that supports CRUD operations.

## Step 1: Create the Domain Model

Domain models represent your core business entities. They live in `src/domain/models/`.

Create `src/domain/models/task.py`:

```python
"""Task domain model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import Base, TenantMixin, TimestampMixin


class Task(Base, TimestampMixin, TenantMixin):
    """Task entity for to-do items.

    Attributes:
        id: Unique task identifier (UUIDv7)
        title: Task title (required, max 200 chars)
        description: Detailed task description (optional)
        completed: Whether task is completed (default: False)
        tenant_id: Tenant identifier for multi-tenancy isolation
        created_at: Timestamp when task was created
        updated_at: Timestamp when task was last updated
    """

    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

**What's happening:**
- `Base` provides the primary key (`id`) and table setup
- `TimestampMixin` adds `created_at` and `updated_at` fields
- `TenantMixin` adds `tenant_id` for multi-tenancy support
- We use SQLAlchemy 2.0 style with `Mapped` type hints

**Verify:** The model compiles without errors (no need to run yet).

## Step 2: Register the Model

Update `src/domain/models/__init__.py` to export your model:

```python
"""Domain models."""

from src.domain.models.task import Task  # Add this line
from src.domain.models.user import User

__all__ = ["Task", "User"]  # Add "Task" here
```

## Step 3: Create Database Migration

Generate a migration for your new table:

```bash
# Make sure services are running
docker-compose up -d

# Generate and apply migration
make migrate-create DESC="add tasks table"
make migrate
```

**Expected output:**
```
Migrating to version 20240115120000 from 20240115110000 (1 migrations):
  -- migrating version 20240115120000
    -> CREATE TABLE tasks (
    ...
  -- ok (25.5ms)
```

**Verify migration:**
```bash
docker-compose exec db psql -U forge_user -d forge_db -c "SELECT * FROM atlas_schema_revisions ORDER BY executed_at DESC LIMIT 1;"
```

You should see your migration listed.

## Step 4: Create API Schemas

API schemas define the structure of requests and responses. Create `src/presentation/schemas/task.py`:

```python
"""Task API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """Schema for creating a task."""

    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: str | None = Field(None, description="Task description")
    completed: bool = Field(False, description="Task completion status")


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None


class TaskResponse(BaseModel):
    """Schema for task response."""

    id: UUID
    title: str
    description: str | None
    completed: bool
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Schema for task list response."""

    items: list[TaskResponse]
    total: int
    skip: int
    limit: int
```

**What's happening:**
- `TaskCreate`: Used for POST requests (creating tasks)
- `TaskUpdate`: Used for PUT/PATCH requests (updating tasks)
- `TaskResponse`: Used for API responses (returning task data)
- `TaskListResponse`: Used for paginated list responses
- `from_attributes = True`: Allows conversion from SQLAlchemy models

## Step 5: Create the Repository Interface

Add a repository interface in `src/domain/interfaces.py`:

```python
# Add this to the existing interfaces.py file
from src.domain.models.task import Task  # Add import


class ITaskRepository(IRepository[Task]):
    """Task repository interface."""

    async def get_by_title(self, title: str, tenant_id: UUID | None = None) -> Task | None:
        """Get task by title."""
        ...
```

## Step 6: Implement the Repository

Create `src/infrastructure/repositories/task_repository.py`:

```python
"""Task repository implementation."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces import ITaskRepository
from src.domain.models.task import Task
from src.infrastructure.repositories.base_repository import BaseRepository


class TaskRepository(BaseRepository[Task], ITaskRepository):
    """Task repository with database operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Task)

    async def get_by_title(self, title: str, tenant_id: UUID | None = None) -> Task | None:
        """Get task by title with optional tenant filtering."""
        query = select(Task).where(Task.title == title)

        if tenant_id:
            query = query.where(Task.tenant_id == tenant_id)

        result = await self._session.execute(query)
        return result.scalar_one_or_none()
```

## Step 7: Create Use Cases

Create `src/app/usecases/task_usecases.py`:

```python
"""Task use cases implementing business logic."""

from uuid import UUID

from src.domain.exceptions import EntityNotFoundError, ValidationError
from src.domain.interfaces import ITaskRepository
from src.domain.models.task import Task


class CreateTaskUseCase:
    """Use case for creating a new task."""

    def __init__(self, task_repository: ITaskRepository) -> None:
        self._repository = task_repository

    async def execute(
        self,
        title: str,
        description: str | None = None,
        completed: bool = False,
        tenant_id: UUID | None = None,
    ) -> Task:
        """Create a new task."""
        # Business logic: Validate title is unique per tenant
        existing = await self._repository.get_by_title(title, tenant_id)
        if existing:
            raise ValidationError(f"Task with title '{title}' already exists")

        task = Task(
            title=title,
            description=description,
            completed=completed,
            tenant_id=tenant_id,
        )

        return await self._repository.add(task)


class GetTaskUseCase:
    """Use case for getting a task by ID."""

    def __init__(self, task_repository: ITaskRepository) -> None:
        self._repository = task_repository

    async def execute(self, task_id: UUID, tenant_id: UUID | None = None) -> Task:
        """Get task by ID with tenant isolation."""
        task = await self._repository.get_by_id(task_id)

        if not task:
            raise EntityNotFoundError(f"Task with ID {task_id} not found")

        # Enforce tenant isolation
        if tenant_id and task.tenant_id != tenant_id:
            raise EntityNotFoundError(f"Task with ID {task_id} not found")

        return task


class ListTasksUseCase:
    """Use case for listing tasks with pagination."""

    def __init__(self, task_repository: ITaskRepository) -> None:
        self._repository = task_repository

    async def execute(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
    ) -> list[Task]:
        """List tasks with pagination."""
        if skip < 0:
            raise ValidationError("Skip must be non-negative")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        return await self._repository.get_all(skip=skip, limit=limit, tenant_id=tenant_id)


class UpdateTaskUseCase:
    """Use case for updating a task."""

    def __init__(self, task_repository: ITaskRepository) -> None:
        self._repository = task_repository

    async def execute(
        self,
        task_id: UUID,
        title: str | None = None,
        description: str | None = None,
        completed: bool | None = None,
        tenant_id: UUID | None = None,
    ) -> Task:
        """Update task with tenant isolation."""
        task = await self._repository.get_by_id(task_id)

        if not task:
            raise EntityNotFoundError(f"Task with ID {task_id} not found")

        # Enforce tenant isolation
        if tenant_id and task.tenant_id != tenant_id:
            raise EntityNotFoundError(f"Task with ID {task_id} not found")

        # Update fields if provided
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if completed is not None:
            task.completed = completed

        return await self._repository.update(task)


class DeleteTaskUseCase:
    """Use case for deleting a task."""

    def __init__(self, task_repository: ITaskRepository) -> None:
        self._repository = task_repository

    async def execute(self, task_id: UUID, tenant_id: UUID | None = None) -> None:
        """Delete task with tenant isolation."""
        task = await self._repository.get_by_id(task_id)

        if not task:
            raise EntityNotFoundError(f"Task with ID {task_id} not found")

        # Enforce tenant isolation
        if tenant_id and task.tenant_id != tenant_id:
            raise EntityNotFoundError(f"Task with ID {task_id} not found")

        await self._repository.delete(task_id)
```

**What's happening:**
- Each use case handles one business operation
- Use cases contain business logic (validation, rules)
- Use cases are independent of HTTP/FastAPI
- Use cases interact with domain models and repositories

## Step 8: Configure Dependency Injection

Update `src/container.py` to register your task services:

```python
# Add these imports
from src.app.usecases.task_usecases import (
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from src.infrastructure.repositories.task_repository import TaskRepository

# In the Container class, add a new provider group:

class Container(containers.DeclarativeContainer):
    # ... existing code ...

    # Task repositories
    task_repository = providers.Factory(
        TaskRepository,
        session=db.session,
    )

    # Task use cases (add this section)
    task_use_cases = providers.FactoryAggregate(
        create_task=providers.Factory(
            CreateTaskUseCase,
            task_repository=task_repository,
        ),
        get_task=providers.Factory(
            GetTaskUseCase,
            task_repository=task_repository,
        ),
        list_tasks=providers.Factory(
            ListTasksUseCase,
            task_repository=task_repository,
        ),
        update_task=providers.Factory(
            UpdateTaskUseCase,
            task_repository=task_repository,
        ),
        delete_task=providers.Factory(
            DeleteTaskUseCase,
            task_repository=task_repository,
        ),
    )
```

## Step 9: Create API Endpoints

Create `src/presentation/api/v1/endpoints/tasks.py`:

```python
"""Task API endpoints."""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path, Query, status

from src.app.usecases.task_usecases import (
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from src.container import Container
from src.presentation.api.dependencies import get_tenant_id
from src.presentation.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Task",
    description="Create a new task with optional tenant isolation",
)
@inject
async def create_task(
    input: TaskCreate,
    use_case: Annotated[CreateTaskUseCase, Depends(Provide[Container.task_use_cases.create_task])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> TaskResponse:
    """Create a new task."""
    task = await use_case.execute(
        title=input.title,
        description=input.description,
        completed=input.completed,
        tenant_id=tenant_id,
    )
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Tasks",
    description="Get a list of tasks with pagination and optional tenant filtering",
)
@inject
async def list_tasks(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    use_case: Annotated[ListTasksUseCase, Depends(Provide[Container.task_use_cases.list_tasks])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> TaskListResponse:
    """List tasks with pagination."""
    tasks = await use_case.execute(skip=skip, limit=limit, tenant_id=tenant_id)
    return TaskListResponse(
        items=[TaskResponse.model_validate(task) for task in tasks],
        total=len(tasks),
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Task",
    description="Get a specific task by ID with optional tenant filtering",
)
@inject
async def get_task(
    task_id: Annotated[UUID, Path(description="Task ID")],
    use_case: Annotated[GetTaskUseCase, Depends(Provide[Container.task_use_cases.get_task])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> TaskResponse:
    """Get task by ID."""
    task = await use_case.execute(task_id=task_id, tenant_id=tenant_id)
    return TaskResponse.model_validate(task)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Task",
    description="Update an existing task with optional tenant filtering",
)
@inject
async def update_task(
    task_id: Annotated[UUID, Path(description="Task ID")],
    input: TaskUpdate,
    use_case: Annotated[UpdateTaskUseCase, Depends(Provide[Container.task_use_cases.update_task])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> TaskResponse:
    """Update task."""
    task = await use_case.execute(
        task_id=task_id,
        title=input.title,
        description=input.description,
        completed=input.completed,
        tenant_id=tenant_id,
    )
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Task",
    description="Delete a task by ID with optional tenant filtering",
)
@inject
async def delete_task(
    task_id: Annotated[UUID, Path(description="Task ID")],
    use_case: Annotated[DeleteTaskUseCase, Depends(Provide[Container.task_use_cases.delete_task])],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
) -> None:
    """Delete task."""
    await use_case.execute(task_id=task_id, tenant_id=tenant_id)
```

## Step 10: Register the Router

Update `src/presentation/api/v1/__init__.py` to include the tasks router:

```python
"""API v1 router configuration."""

from fastapi import APIRouter

from src.presentation.api.v1.endpoints import health, partners, tasks, users  # Add tasks

api_router = APIRouter(prefix="/v1")

api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(partners.router)
api_router.include_router(tasks.router)  # Add this line
```

## Step 11: Wire Up Dependency Injection

Update the wiring configuration in your main application file to include the new tasks module. In `src/presentation/api/application.py` or wherever you configure wiring:

```python
# Make sure tasks endpoint module is wired
container.wire(modules=[
    "src.presentation.api.v1.endpoints.users",
    "src.presentation.api.v1.endpoints.partners",
    "src.presentation.api.v1.endpoints.tasks",  # Add this
    "src.presentation.api.dependencies",
])
```

## Step 12: Test Your Endpoint

Restart the application:

```bash
docker-compose restart api
```

**Test creating a task:**

```bash
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Buy groceries",
    "description": "Milk, eggs, bread",
    "completed": false
  }'
```

**Expected response (200 OK):**
```json
{
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "completed": false,
  "tenant_id": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Test listing tasks:**

```bash
curl "http://localhost:8000/api/v1/tasks"
```

**Test with tenant isolation:**

```bash
curl -X POST "http://localhost:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: 01234567-89ab-cdef-0123-456789abcdef" \
  -d '{"title": "Team task", "completed": false}'
```

## Step 13: View API Documentation

Open your browser and visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

You should see your new `/api/v1/tasks` endpoints documented with:
- Request/response schemas
- Parameter descriptions
- Example payloads
- Status codes

## What You've Learned

✅ **Clean Architecture layers:**
- Domain models (entities)
- Repository interfaces and implementations
- Use cases (business logic)
- API schemas and endpoints

✅ **FastAPI concepts:**
- Routers and path operations
- Request validation with Pydantic
- Response models
- Query parameters and path parameters

✅ **Dependency Injection:**
- Container configuration
- Provider factories
- Wiring modules

✅ **Best Practices:**
- Separation of concerns
- Tenant isolation
- Input validation
- Error handling

## Next Steps

Now that you understand the basics, try:

1. **Add more fields** to the Task model (e.g., `due_date`, `priority`)
2. **Add filtering** - filter tasks by completion status
3. **Add search** - search tasks by title
4. **Write tests** - see [Testing Guide](../reference/testing.md)
5. **Learn about background jobs** - [Background Jobs Tutorial](03-background-jobs.md)

## Common Issues

**Problem:** Migration fails with "relation already exists"

**Solution:** Drop and recreate the database:
```bash
docker-compose down -v
docker-compose up -d
make migrate
```

**Problem:** Endpoint returns 404 Not Found

**Solution:**
1. Check router is registered in `__init__.py`
2. Check module is wired in application setup
3. Restart the API: `docker-compose restart api`

**Problem:** Dependency injection fails

**Solution:** Make sure:
1. Container has the provider registered
2. Module is in the wiring list
3. Using `@inject` decorator on endpoint functions

## Summary

You've successfully created a complete CRUD API endpoint following Clean Architecture principles! The key pattern is:

```
Request → Endpoint → Use Case → Repository → Database
Response ← Endpoint ← Use Case ← Repository ← Database
```

Each layer has a single responsibility and can be tested independently.

**Continue learning:**
- [Database Models Tutorial](02-database-model.md)
- [Background Jobs Tutorial](03-background-jobs.md)
- [How to Add an Endpoint](../how-to/add-endpoint.md)
