# Tutorial: Advanced Database Modeling

**Time**: 20 minutes
**Prerequisite**: Complete [First API Tutorial](01-first-api.md)

Learn how to create advanced database models with relationships, migrations, and multi-tenancy support.

## What You'll Build

A complete **Project Management** system with:
- Projects (one-to-many with Tasks)
- Tasks (many-to-many with Tags)
- Tags (reusable across tasks)
- Multi-tenant isolation
- Optimized queries

## Table of Contents

1. [Create Domain Models](#step-1-create-domain-models)
2. [Define Relationships](#step-2-define-relationships)
3. [Create Database Migration](#step-3-create-database-migration)
4. [Implement Repository](#step-4-implement-repository)
5. [Add API Schemas](#step-5-add-api-schemas)
6. [Create Use Cases](#step-6-create-use-cases)
7. [Build API Endpoints](#step-7-build-api-endpoints)
8. [Test the API](#step-8-test-the-api)
9. [Query Optimization](#step-9-query-optimization)

---

## Step 1: Create Domain Models

Create three SQLAlchemy models with relationships.

### 1.1 Create Project Model

```python
# src/core/domain/models/project.py
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING
import uuid

from src.core.infrastructure.database.base import BaseModel

if TYPE_CHECKING:
    from .task import Task

class Project(BaseModel):
    """Project model with one-to-many relationship to tasks."""

    __tablename__ = "projects"

    # Fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Multi-tenancy
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin"  # Avoid N+1 queries
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"
```

### 1.2 Create Task Model

```python
# src/core/domain/models/task.py
from sqlalchemy import String, Text, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING
import uuid

from src.core.infrastructure.database.base import BaseModel

if TYPE_CHECKING:
    from .project import Project
    from .tag import Tag

# Association table for many-to-many relationship
task_tags = Table(
    "task_tags",
    BaseModel.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class Task(BaseModel):
    """Task model with many-to-many relationship to tags."""

    __tablename__ = "tasks"

    # Fields
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Foreign keys
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Multi-tenancy
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary=task_tags,
        back_populates="tasks",
        lazy="selectin"  # Avoid N+1 queries
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, status={self.status})>"
```

### 1.3 Create Tag Model

```python
# src/core/domain/models/tag.py
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING
import uuid

from src.core.infrastructure.database.base import BaseModel

if TYPE_CHECKING:
    from .task import Task, task_tags

class Tag(BaseModel):
    """Tag model for categorizing tasks."""

    __tablename__ = "tags"

    # Fields
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color

    # Multi-tenancy
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        secondary="task_tags",
        back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name={self.name})>"
```

**What we did:**
- ✅ Created three models with SQLAlchemy 2.0 syntax
- ✅ Defined one-to-many (Project → Tasks)
- ✅ Defined many-to-many (Tasks ↔ Tags) with association table
- ✅ Added multi-tenancy to all models
- ✅ Used `lazy="selectin"` to prevent N+1 queries

---

## Step 2: Define Relationships

### Understanding Relationship Types

#### One-to-Many (Project → Tasks)

```python
# On Project model (parent)
tasks: Mapped[List["Task"]] = relationship(
    "Task",
    back_populates="project",
    cascade="all, delete-orphan",  # Delete tasks when project deleted
    lazy="selectin"  # Load tasks eagerly to avoid N+1
)

# On Task model (child)
project: Mapped["Project"] = relationship("Project", back_populates="tasks")
project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
```

#### Many-to-Many (Tasks ↔ Tags)

```python
# Association table (no model needed)
task_tags = Table(
    "task_tags",
    BaseModel.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE")),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE")),
)

# On both models
tags: Mapped[List["Tag"]] = relationship("Tag", secondary=task_tags, back_populates="tasks")
tasks: Mapped[List["Task"]] = relationship("Task", secondary=task_tags, back_populates="tags")
```

### Cascade Options

- `all, delete-orphan`: Delete children when parent deleted
- `save-update`: Automatically save related objects
- `delete`: Delete children when parent deleted
- `merge`: Merge related objects

### Lazy Loading Options

- `select` (default): Load on access (causes N+1!)
- `selectin`: Load with single query (recommended)
- `joined`: Load with JOIN (good for one-to-one)
- `subquery`: Load with subquery

---

## Step 3: Create Database Migration

Generate and apply Alembic migration.

### 3.1 Generate Migration

```bash
# In Docker container
docker compose exec api alembic revision --autogenerate -m "add_project_task_tag_models"
```

### 3.2 Review Migration

```python
# migrations/versions/xxxx_add_project_task_tag_models.py
def upgrade() -> None:
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_tenant_id', 'projects', ['tenant_id'])

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tasks_project_id', 'tasks', ['project_id'])
    op.create_index('ix_tasks_tenant_id', 'tasks', ['tenant_id'])

    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tags_tenant_id', 'tags', ['tenant_id'])

    # Create association table
    op.create_table(
        'task_tags',
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('task_id', 'tag_id')
    )
```

### 3.3 Apply Migration

```bash
docker compose exec api alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade ... -> xxxx, add_project_task_tag_models
```

---

## Step 4: Implement Repository

Create repository with relationship queries.

```python
# src/core/infrastructure/persistence/repositories/project_repository.py
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from src.core.domain.models.project import Project
from src.core.infrastructure.persistence.repositories.base import BaseRepository

class ProjectRepository(BaseRepository[Project]):
    """Repository for Project model with eager loading of relationships."""

    def __init__(self):
        super().__init__(Project)

    async def get_with_tasks(self, project_id: uuid.UUID, tenant_id: uuid.UUID) -> Project | None:
        """Get project with all tasks eagerly loaded."""
        stmt = (
            select(Project)
            .options(selectinload(Project.tasks))  # Eager load tasks
            .where(Project.id == project_id, Project.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_task_count(self, tenant_id: uuid.UUID) -> List[tuple[Project, int]]:
        """List projects with task count."""
        from sqlalchemy import func
        from src.core.domain.models.task import Task

        stmt = (
            select(Project, func.count(Task.id).label("task_count"))
            .outerjoin(Task)
            .where(Project.tenant_id == tenant_id)
            .group_by(Project.id)
        )
        result = await self.session.execute(stmt)
        return result.all()
```

---

## Step 5: Add API Schemas

```python
# src/api/v1/schemas/project.py
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None

class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    tags: list[TagResponse] = []
    created_at: datetime
    updated_at: datetime

class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    tasks: list[TaskResponse] = []
    created_at: datetime
    updated_at: datetime

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
```

---

## Step 6: Create Use Cases

```python
# src/core/application/use_cases/project/create_project.py
from dataclasses import dataclass
import uuid

from src.core.domain.models.project import Project
from src.core.infrastructure.persistence.repositories.project_repository import ProjectRepository
from src.core.infrastructure.persistence.unit_of_work import UnitOfWork

@dataclass
class CreateProjectCommand:
    name: str
    description: str | None
    tenant_id: uuid.UUID

class CreateProjectUseCase:
    """Use case for creating a new project."""

    def __init__(self, repository: ProjectRepository, uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    async def execute(self, command: CreateProjectCommand) -> Project:
        """Create a new project."""
        # Create project
        project = Project(
            name=command.name,
            description=command.description,
            tenant_id=command.tenant_id
        )

        # Save with Unit of Work
        async with self.uow:
            await self.repository.add(project)
            await self.uow.commit()
            return project
```

---

## Step 7: Build API Endpoints

```python
# src/api/v1/endpoints/projects.py
from fastapi import APIRouter, Depends, status
from typing import List
import uuid

from src.api.v1.schemas.project import ProjectResponse, ProjectCreate
from src.core.application.use_cases.project.create_project import CreateProjectUseCase, CreateProjectCommand
from src.core.infrastructure.dependencies import get_tenant_id

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    use_case: CreateProjectUseCase = Depends()
) -> ProjectResponse:
    """Create a new project."""
    command = CreateProjectCommand(
        name=data.name,
        description=data.description,
        tenant_id=tenant_id
    )
    project = await use_case.execute(command)
    return ProjectResponse.model_validate(project)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    repository: ProjectRepository = Depends()
) -> ProjectResponse:
    """Get project with all tasks and tags."""
    project = await repository.get_with_tasks(project_id, tenant_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)
```

---

## Step 8: Test the API

### 8.1 Create Project

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEifQ.signature" \
  -d '{
    "name": "Website Redesign",
    "description": "Redesign company website"
  }'
```

**Expected response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Website Redesign",
  "description": "Redesign company website",
  "tasks": [],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### 8.2 Get Project with Tasks

```bash
curl http://localhost:8000/api/v1/projects/123e4567-e89b-12d3-a456-426614174000 \
  -H "X-Tenant-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEifQ.signature"
```

---

## Step 9: Query Optimization

### Avoid N+1 Queries

**Bad (N+1 problem):**
```python
# This will execute 1 + N queries!
projects = await repository.list()  # 1 query
for project in projects:
    print(project.tasks)  # N queries (one per project)
```

**Good (Single query with selectinload):**
```python
stmt = select(Project).options(selectinload(Project.tasks))
projects = await session.execute(stmt)
# Only 2 queries total: 1 for projects, 1 for all tasks
```

### Use Indexes

```python
# Add indexes in migration
op.create_index('ix_tasks_project_id', 'tasks', ['project_id'])
op.create_index('ix_tasks_tenant_id', 'tasks', ['tenant_id'])
op.create_index('ix_tasks_status', 'tasks', ['status'])
```

### Pagination for Large Datasets

```python
async def list_projects(skip: int = 0, limit: int = 10):
    stmt = (
        select(Project)
        .where(Project.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
```

---

## Troubleshooting

### Issue: "Cannot delete parent row" error

**Problem:** Foreign key constraint prevents deletion.

**Solution:** Use `ondelete="CASCADE"` in ForeignKey:
```python
project_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("projects.id", ondelete="CASCADE")
)
```

### Issue: N+1 query performance

**Problem:** Multiple queries for relationships.

**Solution:** Use `selectinload` or `joined`:
```python
stmt = select(Project).options(selectinload(Project.tasks))
```

### Issue: "relationship() could not determine parent/child" error

**Problem:** Missing `back_populates` parameter.

**Solution:** Always set `back_populates` on both sides:
```python
# Parent
tasks: Mapped[List["Task"]] = relationship("Task", back_populates="project")

# Child
project: Mapped["Project"] = relationship("Project", back_populates="tasks")
```

---

## Next Steps

- 📘 [Background Jobs Tutorial](03-background-jobs.md) - Add async processing with Temporal
- 📖 [Architecture Reference](../reference/architecture.md) - Deep dive into Clean Architecture
- 🔧 [Add Endpoint Guide](../how-to/add-endpoint.md) - Quick reference for adding endpoints

---

## Summary

You learned:
- ✅ Create models with one-to-many and many-to-many relationships
- ✅ Use SQLAlchemy 2.0 typed syntax
- ✅ Generate and apply Alembic migrations
- ✅ Implement repositories with relationship queries
- ✅ Optimize queries to prevent N+1 problems
- ✅ Build complete API with relationships
- ✅ Handle multi-tenancy across related models
