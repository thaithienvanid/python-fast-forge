"""Atlas model loader for SQLAlchemy models.

This script loads all SQLAlchemy models and prints the DDL schema
for Atlas to consume. Atlas uses this to understand the current
schema definition from your SQLAlchemy models.
"""

# Import all models - add new models here as you create them
from src.domain.models.user import User

# This is required - all models must be imported before calling print_ddl
from atlas_provider_sqlalchemy.ddl import print_ddl


# Print the DDL for Atlas to consume
if __name__ == "__main__":
    # Pass the dialect and list of model classes
    print_ddl(
        "postgresql",  # Database dialect (postgresql, mysql, sqlite, mssql, mariadb)
        [
            User,
            # Add new models here as you create them
        ]
    )
