"""Cache and Redis configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class CacheSettings(BaseSettings):
    """Redis and caching configuration.

    Handles all caching-related settings including Redis connection,
    connection pooling, and cache behavior.
    """

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        description="Redis connection URL",
    )
    redis_max_connections: int = Field(
        default=10,
        alias="REDIS_MAX_CONNECTIONS",
        description="Maximum connections in the Redis pool",
    )
    cache_enabled: bool = Field(
        default=True,
        alias="CACHE_ENABLED",
        description="Enable or disable caching globally",
    )
    cache_ttl: int = Field(
        default=300,
        alias="CACHE_TTL",
        description="Default cache TTL in seconds (5 minutes)",
    )
