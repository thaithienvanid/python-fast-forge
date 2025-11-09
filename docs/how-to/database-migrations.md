# How to Manage Database Migrations

This guide shows you how to manage database schema migrations using Atlas with SQLAlchemy models.

## Prerequisites

- Atlas CLI installed (`curl -sSf https://atlasgo.sh | sh` or `brew install ariga/tap/atlas`)
- Docker running (for dev database validation)
- Database connection configured in `.env`
- Python dependencies installed (`uv sync`)

## How Atlas Works

Atlas uses an **external schema** approach:
1. Runs `load_models.py` to generate DDL from your SQLAlchemy models
2. Compares the generated schema with existing migrations
3. Creates new migration files with the differences
4. No intermediate files needed - everything happens dynamically

**Configuration:** See `atlas.hcl` for the complete setup.

## Performance Optimizations

This project includes **partial indexes** for soft delete queries, providing 5-10x performance improvement:

- **ix_users_active_only**: Partial index for active records (WHERE deleted_at IS NULL)
- **ix_users_tenant_active**: Composite index (tenant_id, deleted_at) for multi-tenant queries
- **ix_users_active_status**: Composite index (is_active, deleted_at) for status filtering
- **ix_users_deleted_records**: Partial index for deleted records (admin/restore features)

These indexes optimize 99% of queries which filter for active (non-deleted) records by being much smaller and faster than full table indexes.

**Implementation:** See `src/domain/models/user.py` for the `__table_args__` configuration with Index() definitions.

## Common Tasks

### Create a New Migration

When you modify a SQLAlchemy model, generate a migration:

```bash
# Create migration (recommended)
make migrate-create m="add_user_avatar_field"

# Or use Atlas directly
atlas migrate diff --env sqlalchemy add_user_avatar_field
```

**What happens:**
- Atlas runs `uv run python load_models.py` to get your schema
- Compares it with the current migration directory
- Generates a timestamped SQL file in `migrations/`

**Example output:**
```
migrations/
├── 20251111120000_add_user_avatar_field.sql
└── atlas.sum
```

### Apply Migrations

Apply pending migrations to your database:

```bash
# Apply to local database (default)
make migrate

# Apply to specific environment with env parameter
make migrate env=production

# Or use migrate-apply (requires env parameter)
make migrate-apply env=production

# Preview what would be applied (dry run)
make migrate-dry-run
```

### Check Migration Status

View current migration state:

```bash
# Check local database status (default)
make migrate-status

# Check specific environment
make migrate-status env=production
```

**Example output:**
```
Migration Status: PENDING
  -- Current Version: 20251111120000
  -- Next Version:    20251111130000
  -- Executed Files:  1
  -- Pending Files:   1
```

### Rollback a Migration

Undo the last migration:

```bash
# Rollback last migration from local database (default)
make migrate-downgrade

# Rollback from specific environment
make migrate-downgrade env=production

# Rollback multiple migrations (n=number to rollback)
make migrate-downgrade env=local n=3
```

### Validate Migrations

Validate migration directory integrity:

```bash
# Validate migrations
make migrate-validate

# Rehash migration directory (if needed)
make migrate-hash
```

## Workflow: Adding a New Model

### 1. Create the Model

Create a new model in `src/domain/models/`:

```python
# src/domain/models/post.py
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.domain.models.base import BaseEntity
from uuid import UUID

class Post(BaseEntity):
    """Blog post entity."""
    
    __tablename__ = "posts"

    title: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        comment="Post title"
    )
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="Post content in markdown"
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Author user ID"
    )
    
    # Relationships
    author: Mapped["User"] = relationship(back_populates="posts")
```

### 2. Update load_models.py

Import the new model so Atlas can detect it:

```python
# load_models.py
"""Atlas model loader for SQLAlchemy models.

This script loads all SQLAlchemy models and prints the DDL schema
for Atlas to consume. Atlas uses this to understand the current
schema definition from your SQLAlchemy models.
"""

# Import all models - add new models here as you create them
from src.domain.models.user import User
from src.domain.models.post import Post  # ← Add this

from atlas_provider_sqlalchemy.ddl import print_ddl

if __name__ == "__main__":
    # Pass the dialect and list of model classes
    print_ddl(
        "postgresql",  # Database dialect
        [
            User,
            Post,  # ← Add this
        ]
    )
```

### 3. Generate Migration

Create a migration from your model changes:

```bash
make migrate-create m="add_posts_table"
```

**What Atlas does:**
1. Runs `load_models.py` to get current schema from your models
2. Compares with existing migrations
3. Generates SQL for the difference
4. Creates timestamped migration file

### 4. Review Generated SQL

Check the generated migration file:

```bash
# View the latest migration
cat migrations/$(ls -t migrations/*.sql | head -1)
```

**Example output:**
```sql
-- Create "posts" table
CREATE TABLE "posts" (
  "id" uuid NOT NULL,
  "title" character varying(255) NOT NULL,
  "content" text NOT NULL,
  "author_id" uuid NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  "deleted_at" timestamptz NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "posts_author_id_fkey" FOREIGN KEY ("author_id") 
    REFERENCES "users" ("id") ON DELETE CASCADE
);
-- Create index "ix_posts_author_id" to table: "posts"
CREATE INDEX "ix_posts_author_id" ON "posts" ("author_id");
```

### 5. Test Migration

Test before applying:

```bash
# Dry run to preview changes
make migrate-dry-run

# Apply if everything looks good
make migrate
```

### 6. Verify

Confirm migration applied successfully:

```bash
# Check migration status
make migrate-status

# Inspect current database schema
make schema-inspect
```

### 7. Commit

Add to version control:

```bash
git add migrations/ load_models.py src/domain/models/post.py
git commit -m "feat: add Post model and migration"
```
git add migrations/ load_models.py src/domain/models/
git commit -m "Add Post model and migration"
```

## Workflow: Modifying an Existing Model

### 1. Edit the Model

Modify an existing model in `src/domain/models/`:

```python
# src/domain/models/user.py
class User(BaseEntity):
    # ... existing fields ...

    # Add new field
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="URL to user's avatar image"
    )
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User biography"
    )
```

### 2. Generate Migration

Atlas will detect the changes automatically:

```bash
make migrate-create m="add_user_avatar_and_bio"
```

### 3. Review, Test, Apply

Follow the same steps as adding a new model (steps 4-7 above).

## Troubleshooting

### "Atlas command not found"

Install Atlas CLI:

```bash
# Linux/macOS
curl -sSf https://atlasgo.sh | sh

# macOS (Homebrew)
brew install ariga/tap/atlas

# Windows
# Download from https://github.com/ariga/atlas/releases

# Verify installation
atlas version
```

**Expected output:**
```
atlas version v0.XX.X
```

### "Failed to load models"

**Problem:** Atlas can't run `load_models.py`

**Solution:**

1. Test the loader directly:
```bash
uv run python load_models.py
```

2. Should output SQL DDL. If it fails:
   - Check all models are imported in `load_models.py`
   - Verify Python dependencies are installed (`uv sync`)
   - Check for syntax errors in your models

### "Dev database error"

**Problem:** `failed to connect to dev database`

**Solution:**

Atlas needs a dev database for validation. Options:

1. **Use Docker** (recommended - automatic):
   ```bash
   # Ensure Docker is running
   docker ps
   
   # Atlas will automatically spin up temporary PostgreSQL
   ```

2. **Use dedicated database** - edit `atlas.hcl`:
   ```hcl
   dev = "postgresql://user:pass@localhost:5432/atlas_dev?sslmode=disable"
   ```

### "Schema drift detected"

**Problem:** Your models differ from migrations

**Solution:**

```bash
# Generate migration for uncommitted changes
make migrate-create m="sync_schema"

# Review the changes
cat migrations/$(ls -t migrations/*.sql | head -1)

# Apply and commit
make migrate
git add migrations/
git commit -m "chore: sync schema with models"
```

### Migration Failed to Apply

**Problem:** Migration fails when running `make migrate`

**Solution:**

1. **Check the error message:**
   ```bash
   make migrate  # Read the error carefully
   ```

2. **Check migration status:**
   ```bash
   make migrate-status
   ```

3. **Rollback if needed:**
   ```bash
   make migrate-downgrade
   ```

4. **Fix and regenerate:**
   ```bash
   # Remove the problematic migration
   rm migrations/20251111_bad_migration.sql
   
   # Fix your model
   vim src/domain/models/user.py
   
   # Regenerate migration
   make migrate-create m="fixed_version"
   
   # Rehash migration directory
   make migrate-hash
   ```

### "Command Exited with Code 1"

**Problem:** Generic Atlas error

**Common causes and solutions:**

1. **Docker not running:**
   ```bash
   docker ps  # Should show containers
   ```

2. **Invalid SQL in models:**
   ```bash
   uv run python load_models.py  # Test model loading
   ```

3. **Missing imports in load_models.py:**
   ```python
   # Ensure all models are imported
   from src.domain.models.user import User
   from src.domain.models.post import Post  # Don't forget new models!
   ```

## Advanced Usage

### Inspect Database Schema

View current database schema:

```bash
# Text output (pipes through PAGER)
make schema-inspect

# Save to file
atlas schema inspect --env local > schema.sql

# Interactive visualization (opens browser)
make schema-viz
```

### Check Schema Drift

Compare database with your models:

```bash
make schema-drift
```

**Useful for:**
- Detecting manual database changes
- Ensuring migrations are up-to-date
- CI/CD validation

### Apply to Production

**⚠️ Always test in staging first!**

```bash
# Set environment variable
export DATABASE_URL="postgresql://user:pass@prod-host:5432/prod_db?sslmode=require"

# Apply migrations
make migrate-apply env=production

# Or use Atlas directly with dry-run
atlas migrate apply \
  --env production \
  --url "$DATABASE_URL" \
  --dry-run
```

### Validate Migration Directory

Check migration integrity:

```bash
# Validate all migrations
make migrate-validate

# Rehash if atlas.sum is out of sync
make migrate-hash
```

## Environment-Specific Configuration

Atlas supports multiple environments in `atlas.hcl`:

| Environment | Purpose | Use Case |
|-------------|---------|----------|
| **sqlalchemy** | Schema generation | Creating migrations from models |
| **local** | Local development | Testing migrations locally |
| **production** | Production deployment | Applying to production database |

### Using Different Environments

```bash
# Generate migration (uses sqlalchemy env)
make migrate-create m="add_feature"

# Apply to local database
make migrate

# Apply to production (with DATABASE_URL set)
export DATABASE_URL="postgresql://user:pass@prod:5432/db"
make migrate-apply env=production

# Dry run for production
atlas migrate apply --env production --dry-run
```

## Best Practices

### ✅ Do

1. **Always review generated SQL** before applying
   ```bash
   cat migrations/$(ls -t migrations/*.sql | head -1)
   ```

2. **Test with dry-run first**
   ```bash
   make migrate-dry-run
   ```

3. **Keep load_models.py up to date**
   - Import all new models immediately
   - Verify with `uv run python load_models.py`

4. **Use descriptive migration names**
   ```bash
   make migrate-create m="add_user_avatar_field"
   # NOT: make migrate-create m="update"
   ```

5. **Commit migrations with your code**
   ```bash
   git add migrations/ load_models.py src/domain/models/
   git commit -m "feat: add Post model with author relationship"
   ```

6. **Validate migrations**
   ```bash
   make migrate-validate
   ```

7. **Test rollbacks in dev**
   ```bash
   make migrate-downgrade
   make migrate  # Re-apply to verify
   ```

### ❌ Don't

1. **Never manually edit generated migrations** - Regenerate instead
2. **Don't skip dry-run** in production
3. **Don't forget to update load_models.py** when adding models
4. **Don't apply untested migrations** to production
5. **Don't ignore migration validation errors**

## Migration File Format

Atlas generates SQL migrations with this format:

```
migrations/
├── 20251111120000_initial_schema.sql
├── 20251111130000_add_posts_table.sql
├── 20251111140000_add_user_avatar.sql
└── atlas.sum  # Integrity hash file
```

**Naming convention:**
- Timestamp: `YYYYMMDDHHMMSS`
- Underscore separator: `_`
- Description: Snake case slug

**Example migration file:**
```sql
-- Create "posts" table
CREATE TABLE "posts" (
  "id" uuid NOT NULL,
  "title" character varying(255) NOT NULL,
  "content" text NOT NULL,
  PRIMARY KEY ("id")
);
-- Create index "ix_posts_title" to table: "posts"
CREATE INDEX "ix_posts_title" ON "posts" ("title");
```

## Workflow Summary

### Daily Development

```bash
# 1. Modify model
vim src/domain/models/user.py

# 2. Update loader
vim load_models.py

# 3. Generate migration
make migrate-create m="add_user_bio_field"

# 4. Review
cat migrations/$(ls -t migrations/*.sql | head -1)

# 5. Apply
make migrate

# 6. Commit
git add migrations/ load_models.py src/
git commit -m "feat: add user bio field"
```

### Before Deploying to Production

```bash
# 1. Validate migrations
make migrate-validate

# 2. Test on staging (with staging DATABASE_URL)
export DATABASE_URL="postgresql://staging..."
make migrate-apply env=production --dry-run

# 3. Apply to staging
make migrate-apply env=production

# 4. Verify
atlas migrate status --env production

# 5. Apply to production (with production DATABASE_URL)
export DATABASE_URL="postgresql://production..."
make migrate-apply env=production
```

## Next Steps

- **[Add a Database Model](../tutorials/02-database-model.md)** - Step-by-step tutorial
- **[Atlas Command Reference](../reference/atlas-commands.md)** - Complete command list
- **[Understanding Atlas Migration](../explanation/atlas-migration.md)** - How it works
- **[Atlas Official Docs](https://atlasgo.io/guides/orms/sqlalchemy)** - SQLAlchemy guide
