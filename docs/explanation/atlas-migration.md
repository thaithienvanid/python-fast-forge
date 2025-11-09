# Understanding Atlas for Database Schema Management

This document explains why we use Atlas instead of Alembic and how it fits into the project architecture.

## What is Atlas?

Atlas is a modern database schema management tool that uses a **declarative, schema-as-code** approach. Instead of writing migration code, you define your schema in your ORM models (SQLAlchemy), and Atlas generates the necessary SQL migrations automatically.

Think of it as "Terraform for databases" - you declare the desired state, and Atlas figures out how to get there.

## Why Atlas Instead of Alembic?

This project migrated from Alembic to Atlas for several reasons:

### 1. Declarative vs Imperative

**Alembic (Imperative)**:
```python
# You write migration code
def upgrade():
    op.add_column('users', sa.Column('avatar_url', sa.String(500)))
    op.create_index('ix_users_avatar_url', 'users', ['avatar_url'])
```

**Atlas (Declarative)**:
```python
# You just update your model
class User(BaseEntity):
    avatar_url: Mapped[str | None] = mapped_column(String(500))
```

Atlas generates the migration automatically from the model change.

### 2. Advanced Database Feature Support

**Alembic limitations**:
- No native support for database functions
- No native support for stored procedures
- No native support for triggers
- Limited view support
- Extensions require manual SQL

**Atlas advantages**:
- Full support for PostgreSQL functions
- Stored procedures handled automatically
- Triggers detected and migrated
- Materialized views supported
- Extensions managed declaratively

### 3. Schema Drift Detection

**Problem with Alembic**:
- No way to detect when production database differs from codebase
- Manual schema changes go unnoticed
- Database and code can drift apart silently

**Atlas solution**:
```bash
make schema-drift  # Automatically detects differences
```

Atlas can:
- Compare production schema with your models
- Alert when manual changes were made
- Generate migrations to sync them back
- Run in CI to prevent drift

### 4. Better CI/CD Integration

**Alembic**:
- Requires custom scripts for validation
- No built-in safety checks
- Manual testing needed

**Atlas**:
- Native GitHub Actions support
- Built-in validation and safety checks
- Automatic PR checks
- Schema visualization in CI
- Advanced lint rules (requires Atlas Cloud)

### 5. Migration Safety

Atlas provides two levels of safety checks:

#### **Basic Validation (Free - Always Available)**

```bash
make migrate-validate
```

This validates:
- **Migration integrity**: Ensures migration files haven't been tampered with
- **Migration directory structure**: Verifies proper organization
- **Migration dependencies**: Checks for broken migration chains
- **SQL syntax**: Validates SQL correctness

#### **Advanced Linting (Requires Atlas Cloud)**

```bash
# Note: Requires Atlas Cloud authentication (paid plan)
atlas migrate lint --env sqlalchemy
```

Advanced linting detects:
- **Destructive changes**: `DROP TABLE`, `DROP COLUMN` operations
- **Data-dependent changes**: `ALTER COLUMN` type changes that may fail with existing data
- **Backward incompatible changes**: Schema changes that break existing application code
- **Concurrent index issues**: `CREATE INDEX` without `CONCURRENTLY` in production
- **Performance risks**: Large table alterations without proper safeguards

**Note**: The `lint` command requires an Atlas Cloud token and is automatically skipped in CI if not configured. The free `validate` command provides essential safety checks for most use cases.

### 6. Better Developer Experience

**Alembic workflow**:
1. Modify model
2. Generate migration
3. Review Python code
4. Manually edit if needed
5. Test
6. Apply

**Atlas workflow**:
1. Modify model
2. Generate migration (done)
3. Review clean SQL
4. Apply

Less steps, cleaner output, fewer errors.

## How Atlas Works

### Architecture

```
┌─────────────────┐
│ SQLAlchemy      │
│ Models          │ <- Source of truth
│ (src/domain/)   │
└────────┬────────┘
         │
         ├─ load_models.py (exports schema)
         │
         v
┌─────────────────┐
│ Atlas CLI       │
│ - Reads models  │
│ - Compares DB   │
│ - Generates SQL │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Migration Files │
│ (migrations/)   │ <- Pure SQL
└────────┬────────┘
         │
         v
┌─────────────────┐
│ PostgreSQL      │
│ Database        │
└─────────────────┘
```

### Key Components

**1. SQLAlchemy Models** (`src/domain/models/`)
- Single source of truth
- Define schema declaratively
- Familiar Python syntax

**2. Model Loader** (`load_models.py`)
- Imports all models
- Uses `atlas-provider-sqlalchemy`
- Exports schema for Atlas

**3. Atlas Configuration** (`atlas.hcl`)
- Defines environments (local, production)
- Configures lint rules
- Sets up drift detection

**4. Migration Files** (`migrations/`)
- Pure SQL files
- Timestamped for ordering
- Version controlled
- Human-readable

### Migration Generation Process

1. **Read current state**: Atlas inspects the database
2. **Read desired state**: Atlas loads your SQLAlchemy models via `load_models.py`
3. **Calculate diff**: Atlas compares the two states
4. **Generate SQL**: Atlas creates SQL statements to migrate from current to desired
5. **Lint**: Atlas checks for issues
6. **Save**: Atlas writes timestamped SQL file

### Migration Application Process

1. **Check status**: Atlas queries `atlas_schema_revisions` table
2. **Find pending**: Atlas identifies unapplied migrations
3. **Validate**: Atlas ensures migrations are in order
4. **Apply**: Atlas executes SQL statements
5. **Record**: Atlas updates revision table

## Atlas vs Alembic Comparison

| Feature | Alembic | Atlas |
|---------|---------|-------|
| **Approach** | Imperative (code) | Declarative (schema) |
| **Migration Format** | Python | SQL |
| **Auto-generation** | Partial | Full |
| **Drift Detection** | ❌ | ✅ |
| **DB Functions** | ❌ | ✅ |
| **Stored Procedures** | ❌ | ✅ |
| **Triggers** | ❌ | ✅ |
| **Views** | Limited | ✅ |
| **Safety Linting** | ❌ | ✅ |
| **CI/CD Integration** | Manual | Native |
| **Schema Visualization** | ❌ | ✅ |
| **Rollback Support** | ✅ | ✅ |
| **Learning Curve** | Medium | Low |
| **Production Ready** | ✅ | ✅ |

## Use Cases Where Atlas Excels

### 1. Complex PostgreSQL Schemas

If you need:
- Database functions for computed columns
- Triggers for audit logging
- Materialized views for performance
- Full-text search indexes

Atlas handles these automatically. Alembic requires manual SQL.

### 2. Multiple Environments

With different environments (dev, staging, prod), Atlas can:
- Apply different validation and lint rules per environment (lint requires Atlas Cloud)
- Detect drift between environments
- Ensure consistency across deployments

### 3. Large Teams

Atlas provides:
- Clear SQL migrations (easy to review)
- Automatic conflict detection
- CI checks before merge
- Schema documentation

### 4. Continuous Deployment

Atlas integrates with:
- GitHub Actions (automatic checks)
- GitLab CI (native support)
- CircleCI (built-in orbs)
- ArgoCD (Kubernetes deployments)

## Migration Philosophy

### Schema as Code

Your SQLAlchemy models are the **single source of truth**:

```python
# src/domain/models/user.py
class User(BaseEntity):
    username: Mapped[str] = mapped_column(String(100), unique=True)
```

Not migration files. Migrations are **derived** from models.

### Reproducibility

Given the same models and database state, Atlas always generates the same migration. This ensures:
- Consistent migrations across developers
- Reproducible deployments
- Reliable rollbacks

### Safety First

Atlas assumes migrations are potentially dangerous:
- Lint rules catch issues early
- Dry-run mode for testing
- Clear SQL for human review
- Rollback support for recovery

## Integration with Clean Architecture

Atlas fits naturally into the project's clean architecture:

```
Domain Layer (src/domain/)
├── models/         <- Define schema here (single source of truth)
│   ├── base.py
│   └── user.py

Infrastructure Layer (src/infrastructure/)
├── persistence/    <- Atlas manages this layer
│   └── database.py

Tools (root)
├── atlas.hcl      <- Configuration
├── load_models.py <- Bridge between domain and Atlas
└── migrations/    <- Generated SQL
```

**Domain layer** defines the schema.
**Atlas** manages the infrastructure.

Clean separation of concerns.

## Common Patterns

### Pattern 1: Adding a Field

```python
# 1. Update model
class User(BaseEntity):
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

# 2. Generate migration
make migrate-create m="add_user_bio"

# 3. Apply
make migrate
```

### Pattern 2: Relationship Changes

```python
# 1. Add relationship
class Post(BaseEntity):
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship("User", back_populates="posts")

# 2. Update other side
class User(BaseEntity):
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="author")

# 3. Update loader
# load_models.py
print_ddl("postgresql", [User, Post])

# 4. Generate migration
make migrate-create m="add_post_author_relationship"
```

### Pattern 3: Index Optimization

```python
# 1. Add index to model
class User(BaseEntity):
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True  # Add index
    )

# 2. Generate migration
make migrate-create m="add_user_email_index"

# Atlas automatically detects the index need
```

## Best Practices

### 1. Keep Models Updated

Always update `load_models.py` when adding models:

```python
from src.domain.models.user import User
from src.domain.models.post import Post  # Add new models
from src.domain.models.comment import Comment

print_ddl("postgresql", [User, Post, Comment])
```

### 2. Review Generated SQL

Always review before applying:

```bash
cat migrations/$(ls -t migrations/*.sql | head -1)
```

Ensure it does what you expect.

### 3. Test Migrations Locally

Always test before deploying:

```bash
# Dry run first
make migrate-dry-run

# Apply locally
make migrate

# Test rollback
make migrate-downgrade
make migrate  # Reapply
```

### 4. Use Descriptive Names

```bash
# Good
make migrate-create m="add_user_avatar_url_and_bio"
make migrate-create m="create_posts_table_with_author_fk"

# Bad
make migrate-create m="update"
make migrate-create m="fix"
```

### 5. Commit Migrations

Always commit migrations with model changes:

```bash
git add migrations/ load_models.py src/domain/models/
git commit -m "Add Post model with author relationship"
```

## Troubleshooting Philosophy

### If Migration Generation Fails

1. **Check model loader**: Does `uv run python load_models.py` work?
2. **Check database connection**: Can Atlas connect to dev database?
3. **Check for conflicts**: Are there pending manual changes in the database?

### If Migration Application Fails

1. **Review the SQL**: Is the migration trying to do something invalid?
2. **Check database state**: Is the database in the expected state?
3. **Check for data issues**: Will the migration fail due to existing data?

### If Drift is Detected

1. **Review the diff**: What changed?
2. **Decide**: Keep manual change or revert it?
3. **Generate migration**: Sync the change into migrations

## Future Considerations

### Upcoming Atlas Features

- Enhanced CI/CD integrations
- Better schema documentation
- Improved visualization
- More database support

### Project Roadmap

- [ ] Add schema versioning to API responses
- [ ] Implement blue-green deployments with schema checks
- [ ] Add automated rollback on deployment failure
- [ ] Create schema documentation website

## Further Reading

- [Atlas Documentation](https://atlasgo.io/)
- [SQLAlchemy Integration Guide](https://atlasgo.io/guides/orms/sqlalchemy)
- [Migration Best Practices](https://atlasgo.io/guides/best-practices)
- [Clean Architecture](clean-architecture.md)
