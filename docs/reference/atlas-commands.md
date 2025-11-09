# Atlas Command Reference

Quick reference for Atlas CLI and Make commands for database schema management with SQLAlchemy models.

## Make Commands (Recommended)

| Command | Description |
|---------|-------------|
| `make migrate [env=ENV]` | Apply all pending migrations (default: local) |
| `make migrate-create m="msg"` | Create new migration from SQLAlchemy model changes |
| `make migrate-apply env=ENV` | Apply migrations to specific environment (requires env parameter) |
| `make migrate-dry-run [env=ENV]` | Preview migrations without applying (default: local) |
| `make migrate-downgrade [env=ENV] [n=N]` | Rollback N migrations (default: env=local, n=1) |
| `make migrate-status [env=ENV]` | Show current migration status (default: local) |
| `make migrate-hash` | Rehash migration directory (fixes atlas.sum) |
| `make migrate-validate` | Validate migration directory integrity |
| `make schema-inspect` | View current database schema |
| `make schema-viz` | Open interactive schema visualization in browser |
| `make schema-drift` | Check for schema drift between code and database |
| `make migrate-reset` | Reset database (⚠️ destroys all data) |

**Environment Flexibility:** Most commands now support optional `env` parameter to override the default `local` environment:

```bash
# Default to local
make migrate
make migrate-status

# Override with specific environment
make migrate env=production
make migrate-status env=production
make migrate-downgrade env=production n=2
```

## Atlas CLI Commands

### Migration Management

```bash
# Create migration from SQLAlchemy models
atlas migrate diff [name] --env sqlalchemy

# Apply migrations to local database
atlas migrate apply --env local

# Apply to production (requires DATABASE_URL env var)
atlas migrate apply --env production

# Dry run (preview changes without applying)
atlas migrate apply --env local --dry-run

# Rollback N migrations
atlas migrate down --env local [N]

# Show migration status
atlas migrate status --env local

# Validate migration directory
atlas migrate validate --env sqlalchemy

# Rehash migration directory
atlas migrate hash --dir file://migrations
```

### Schema Operations

```bash
# Inspect current schema
atlas schema inspect --env local

# Inspect with SQL format
atlas schema inspect --env local --format "{{ sql . }}"

# Interactive visualization (opens browser)
atlas schema inspect --env local -w

# Compare schemas (check drift)
atlas schema diff \
  --from "env://local" \
  --to "env://sqlalchemy"

# Save schema to file
atlas schema inspect --env local > current_schema.sql
```

### Environment Options

```bash
# Use specific environment from atlas.hcl
--env local        # Local development (relaxed lint rules, uses DATABASE_URL or fallback)
--env sqlalchemy   # Schema generation (for creating migrations)
--env production   # Production (strict rules, requires DATABASE_URL)
```

### Common Flags

```bash
# Dry run (preview changes without applying)
--dry-run

# Apply specific number of migrations
--amount N

# Apply up to specific version
--version 20251111120000

# Output format
--format "{{ sql . }}"      # SQL output
--format "{{ json . }}"     # JSON output

# Migration directory
--dir file://migrations

# Dev database for validation
--dev-url "docker://postgres/16/dev"

# Target database URL
--url "postgresql://user:pass@host:5432/db"
```

## Configuration File (atlas.hcl)

### External Schema Data Source

Atlas loads SQLAlchemy models dynamically using an external schema:

```hcl
// Define external schema - runs load_models.py
data "external_schema" "sqlalchemy" {
  program = [
    "uv",
    "run",
    "python",
    "load_models.py"
  ]
}
```

### Environment Structure

```hcl
env "sqlalchemy" {
  // Use SQLAlchemy models as source
  src = data.external_schema.sqlalchemy.url

  // Dev database for validation
  dev = "docker://postgres/16/dev?search_path=public"

  // Migration directory
  migration {
    dir = "file://migrations"
  }

  // Format configuration
  format {
    migrate {
      diff = "{{ sql . \"  \" }}"  // Two-space indentation
    }
  }

  // Lint rules
  lint {
    destructive { error = true }
    data_depend { error = true }
    incompatible { error = true }
  }
}
```

### Variable Usage

```hcl
// Define variable
variable "database_url" {
  type    = string
  default = getenv("DATABASE_URL")
}

// Use variable in environment
env "production" {
  url = var.database_url
}
```

## Python Model Loader (load_models.py)

### Complete Structure

```python
"""Atlas model loader for SQLAlchemy models.

This script loads all SQLAlchemy models and prints the DDL schema
for Atlas to consume via the external_schema data source.
"""

# Import all models - add new models here as you create them
from src.domain.models.user import User
from src.domain.models.post import Post

from atlas_provider_sqlalchemy.ddl import print_ddl

if __name__ == "__main__":
    # Pass the dialect and list of model classes
    print_ddl(
        "postgresql",  # Database dialect
        [
            User,
            Post,
            # Add new models here
        ]
    )
```

### Supported Dialects

- `postgresql` - PostgreSQL (recommended)
- `mysql` - MySQL
- `mariadb` - MariaDB
- `sqlite` - SQLite
- `mssql` - Microsoft SQL Server
- `clickhouse` - ClickHouse

### Testing the Loader

```bash
# Test that models load correctly
uv run python load_models.py

# Should output SQL DDL statements
```

## Migration File Format

### Naming Convention

```
migrations/
├── 20251111120000_initial_schema.sql    # Timestamp + description
├── 20251111130000_add_posts_table.sql
└── atlas.sum                             # Checksum file
```

### SQL Migration Example

```sql
-- Create "posts" table
CREATE TABLE "posts" (
  "id" uuid NOT NULL,
  "title" character varying(255) NOT NULL,
  "content" text NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id")
);
-- Create index "ix_posts_created_at" to table: "posts"
CREATE INDEX "ix_posts_created_at" ON "posts" ("created_at");
```

## Common Options

### Database URLs

```bash
# PostgreSQL
postgresql://user:pass@localhost:5432/db?sslmode=disable

# PostgreSQL (async)
postgresql+asyncpg://user:pass@localhost:5432/db

# MySQL
mysql://user:pass@localhost:3306/db

# SQLite
sqlite://./database.db

# Docker dev database (PostgreSQL 16)
docker://postgres/16/dev?search_path=public
```

### Lint Rules

```hcl
lint {
  destructive {
    error = true  # Error on DROP operations
  }

  data_depend {
    error = true  # Error on data-dependent changes
  }

  incompatible {
    error = true  # Error on backward-incompatible changes
  }

  review = true  # Require manual review
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Lint errors detected |
| 3 | Schema drift detected |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Database connection string |
| `ATLAS_CLOUD_TOKEN` | Atlas Cloud token (optional) |

## Examples

### Example: Create and Apply Migration

```bash
# 1. Modify model
vim src/domain/models/user.py

# 2. Update loader
vim load_models.py

# 3. Create migration
make migrate-create m="add_user_avatar"

# 4. Review
cat migrations/$(ls -t migrations/*.sql | head -1)

# 5. Test
make migrate-dry-run

# 6. Apply
make migrate

# 7. Verify
make migrate-status
```

### Example: Check Schema Drift

```bash
# Compare database with models
make schema-drift

# If drift detected, create migration
make migrate-create m="sync_schema"
```

### Example: Rollback and Retry

```bash
# Apply failed, rollback
make migrate-downgrade

# Fix issue, regenerate
make migrate-create m="fixed_version"

# Apply again
make migrate
```

### Example: Schema Inspection

```bash
# View schema as SQL
make schema-inspect

# View as JSON
atlas schema inspect --env local --format "{{ json . }}"

# Interactive browser view
make schema-viz
```

## Related Documentation

- [How to Manage Migrations](../how-to/database-migrations.md)
- [Understanding Atlas](../explanation/atlas-migration.md)
- [Official Atlas Docs](https://atlasgo.io/)
