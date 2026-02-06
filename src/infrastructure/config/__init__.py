"""Configuration module with domain-specific settings classes.

This module provides a composable configuration system following the
Single Responsibility Principle. Instead of a monolithic Settings class,
configuration is split into domain-specific classes that are composed
together.

Architecture:
- AppSettings: Application and server configuration
- DatabaseSettings: Database connection and pooling
- SecuritySettings: JWT, CORS, rate limiting, API keys
- CacheSettings: Redis and caching configuration
- ObservabilitySettings: OpenTelemetry and tracing
- WorkflowSettings: Temporal workflow engine
- ExternalServicesSettings: Third-party service integrations

Usage:
    ```python
    from src.infrastructure.config import get_settings

    settings = get_settings()

    # Access domain-specific settings
    print(settings.app.app_name)
    print(settings.database.database_url)
    print(settings.security.jwt_algorithm)
    print(settings.cache.redis_url)
    ```

Benefits:
- Single Responsibility: Each settings class has one reason to change
- Composability: Settings can be easily extended or replaced
- Testability: Domain-specific settings can be mocked independently
- Maintainability: Clear organization and separation of concerns
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .app_settings import AppSettings
from .cache_settings import CacheSettings
from .database_settings import DatabaseSettings
from .external_services_settings import ExternalServicesSettings
from .observability_settings import ObservabilitySettings
from .security_settings import SecuritySettings
from .workflow_settings import WorkflowSettings


class Settings(BaseSettings):
    """Unified application settings composed of domain-specific configuration classes.

    This class acts as a composition root for all configuration, bringing together
    domain-specific settings classes. It maintains backward compatibility while
    providing better organization through composition.

    Design Pattern: Composite + Facade
    - Composite: Multiple settings objects composed into one
    - Facade: Simplified interface to complex subsystems

    Example:
        ```python
        settings = Settings()

        # Access domain-specific settings
        app_name = settings.app.app_name
        db_url = settings.database.database_url
        jwt_key = settings.security.get_jwt_private_key()
        cache_enabled = settings.cache.cache_enabled
        ```
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Compose domain-specific settings
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)
    external_services: ExternalServicesSettings = Field(default_factory=ExternalServicesSettings)

    def model_post_init(self, __context: object) -> None:
        """Post-initialization hook to sync production flag across settings."""
        # Sync production flag to settings that need it for validation
        is_prod = self.app.is_production
        self.security.is_production = is_prod
        self.external_services.is_production = is_prod

    # Backward compatibility properties for commonly accessed settings
    @property
    def app_name(self) -> str:
        """Backward compatibility: app_name."""
        return self.app.app_name

    @property
    def app_version(self) -> str:
        """Backward compatibility: app_version."""
        return self.app.app_version

    @property
    def app_env(self) -> str:
        """Backward compatibility: app_env."""
        return self.app.app_env

    @property
    def debug(self) -> bool:
        """Backward compatibility: debug."""
        return self.app.debug

    @property
    def is_production(self) -> bool:
        """Backward compatibility: is_production."""
        return self.app.is_production

    @property
    def is_development(self) -> bool:
        """Backward compatibility: is_development."""
        return self.app.is_development

    @property
    def database_url(self) -> str:
        """Backward compatibility: database_url."""
        return self.database.database_url

    @property
    def redis_url(self) -> str:
        """Backward compatibility: redis_url."""
        return self.cache.redis_url

    @property
    def cache_enabled(self) -> bool:
        """Backward compatibility: cache_enabled."""
        return self.cache.cache_enabled

    @property
    def api_v1_prefix(self) -> str:
        """Backward compatibility: api_v1_prefix."""
        return self.app.api_v1_prefix

    @property
    def cors_origins(self) -> list[str]:
        """Backward compatibility: cors_origins."""
        return self.security.cors_origins

    @property
    def jwt_algorithm(self) -> str:
        """Backward compatibility: jwt_algorithm."""
        return self.security.jwt_algorithm

    @property
    def access_token_expire_minutes(self) -> int:
        """Backward compatibility: access_token_expire_minutes."""
        return self.security.access_token_expire_minutes

    def get_jwt_private_key(self) -> str:
        """Backward compatibility: get_jwt_private_key."""
        return self.security.get_jwt_private_key()

    def get_jwt_public_key(self) -> str:
        """Backward compatibility: get_jwt_public_key."""
        return self.security.get_jwt_public_key()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses functools.lru_cache to ensure settings are loaded only once
    and reused across the application lifetime.

    Returns:
        Singleton Settings instance with all configuration loaded
    """
    return Settings()


__all__ = [
    "Settings",
    "get_settings",
    "AppSettings",
    "DatabaseSettings",
    "SecuritySettings",
    "CacheSettings",
    "ObservabilitySettings",
    "WorkflowSettings",
    "ExternalServicesSettings",
]
