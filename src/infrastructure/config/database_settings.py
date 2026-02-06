"""Database configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database connection and pool configuration.

    Handles all database-related settings including connection URL,
    pool sizing, and query logging.
    """

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db",
        alias="DATABASE_URL",
        description="PostgreSQL connection URL with asyncpg driver",
    )
    database_echo: bool = Field(
        default=False,
        alias="DATABASE_ECHO",
        description="Enable SQLAlchemy query logging",
    )
    database_pool_size: int = Field(
        default=5,
        alias="DATABASE_POOL_SIZE",
        description="Number of connections to keep in the pool",
    )
    database_max_overflow: int = Field(
        default=10,
        alias="DATABASE_MAX_OVERFLOW",
        description="Max connections above pool_size before blocking",
    )
