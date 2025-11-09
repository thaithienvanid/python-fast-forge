/*
 * Atlas Configuration for Python Fast Forge
 *
 * This file configures Atlas schema management for the FastAPI application.
 * Atlas uses this configuration to:
 * - Load SQLAlchemy models via the Python provider (external_schema)
 * - Generate migrations from model changes
 * - Apply migrations to the database
 * - Detect schema drift in production
 *
 * Documentation: https://atlasgo.io/guides/orms/sqlalchemy
 */

// External schema data source - loads SQLAlchemy models dynamically
// This runs the load_models.py script to generate DDL from your models
data "external_schema" "sqlalchemy" {
  program = [
    "uv",
    "run",
    "python",
    "load_models.py"
  ]
}

// Define the SQLAlchemy environment (default for development)
env "sqlalchemy" {
  // Use SQLAlchemy models as the source of truth for schema
  // This references the external_schema data source defined above
  src = data.external_schema.sqlalchemy.url

  // Dev database for schema validation and diff calculations
  // Atlas uses this to validate schema changes before applying
  // Using docker:// allows Atlas to spin up temporary databases for validation
  dev = "docker://postgres/16/dev?search_path=public"

  // Migration directory configuration
  migration {
    // Directory where Atlas stores migration files
    dir = "file://migrations"
  }

  // Format configuration for generated migration files
  format {
    migrate {
      // Use two-space indentation for SQL statements
      diff = "{{ sql . \"  \" }}"
    }
  }

  // Diff policy - how Atlas compares schemas
  diff {
    // Skip destructive changes by default (require explicit confirmation)
    skip {
      drop_table   = false
      drop_column  = false
      drop_index   = false
      drop_schema  = false
    }
  }

  // Lint configuration for migration safety
  lint {
    // Detect destructive changes
    destructive {
      error = true
    }

    // Detect data-dependent changes (type changes that may fail)
    data_depend {
      error = true
    }

    // Detect backward incompatible changes
    incompatible {
      error = true
    }
  }
}

// Production environment (inherits from sqlalchemy)
env "production" {
  // Use SQLAlchemy models as source
  src = data.external_schema.sqlalchemy.url

  // Production database URL (must be provided via environment variable)
  url = var.database_url

  // Dev database for validation (same as sqlalchemy env)
  dev = "docker://postgres/16/dev?search_path=public"

  // Use the same migration directory
  migration {
    dir = "file://migrations"
  }

  // Format configuration (same as sqlalchemy env)
  format {
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }

  // Stricter lint rules for production
  lint {
    destructive {
      error = true
    }
    data_depend {
      error = true
    }
    incompatible {
      error = true
    }

    // Review required for production changes
    review = true
  }

  // Drift detection configuration
  drift {
    // Detect when production schema differs from codebase
    enabled = true

    // Ignore certain schema differences
    ignore {
      // Ignore differences in these schemas
      # schema = ["information_schema", "pg_catalog"]
    }
  }
}

// Local development environment
env "local" {
  // Use SQLAlchemy models as source
  src = data.external_schema.sqlalchemy.url

  // Local database connection (uses DATABASE_URL env var or fallback)
  url = var.database_url

  // Dev database for validation
  dev = "docker://postgres/16/dev?search_path=public"

  // Use the same migration directory
  migration {
    dir = "file://migrations"
  }

  // Format configuration (same as sqlalchemy env)
  format {
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }

  // Relaxed lint rules for local development
  lint {
    destructive {
      error = false
    }
  }
}

// Variable definitions (for advanced usage)
variable "database_url" {
  type = string
  // Convert SQLAlchemy async driver URL to standard PostgreSQL URL for Atlas
  // DATABASE_URL format: postgresql+asyncpg://user:pass@host:port/db
  // Atlas expects: postgresql://user:pass@host:port/db?param=value
  // If DATABASE_URL is not set, use localhost default
  default = getenv("DATABASE_URL") != "" ? replace(
    getenv("DATABASE_URL"),
    "postgresql+asyncpg://",
    "postgresql://"
  ) : "postgresql://postgres:postgres@localhost:5432/postgres?search_path=public&sslmode=disable"
}
