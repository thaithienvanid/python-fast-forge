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
- PluginSettings: Plugin system and builtin plugin configuration

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
from .plugin_settings import PluginSettings
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
    plugins: PluginSettings = Field(default_factory=PluginSettings)

    def model_post_init(self, __context: object) -> None:
        """Post-initialization hook to sync production flag across settings."""
        # Sync production flag to settings that need it for validation
        is_prod = self.app.is_production
        self.security.is_production = is_prod
        self.external_services.is_production = is_prod

        # Validate email_api_key in production (runs after is_production is synced)
        if is_prod and (
            "dev-email" in self.external_services.email_api_key.lower()
            or "unsafe" in self.external_services.email_api_key.lower()
        ):
            raise ValueError(
                "EMAIL_API_KEY must be set to a real API key in production. "
                "Default development key is not allowed."
            )

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

    @app_env.setter
    def app_env(self, value: str) -> None:
        """Setter for app_env to allow test fixtures to modify it."""
        self.app.app_env = value

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

    # Database backward compatibility
    @property
    def database_echo(self) -> bool:
        """Backward compatibility: database_echo."""
        return self.database.database_echo

    @database_echo.setter
    def database_echo(self, value: bool) -> None:
        """Setter for database_echo to allow test fixtures to modify it."""
        self.database.database_echo = value

    @property
    def database_pool_size(self) -> int:
        """Backward compatibility: database_pool_size."""
        return self.database.database_pool_size

    @property
    def database_max_overflow(self) -> int:
        """Backward compatibility: database_max_overflow."""
        return self.database.database_max_overflow

    # Application backward compatibility
    @property
    def log_level(self) -> str:
        """Backward compatibility: log_level."""
        return self.app.log_level

    @property
    def port(self) -> int:
        """Backward compatibility: port."""
        return self.app.port

    @property
    def host(self) -> str:
        """Backward compatibility: host."""
        return self.app.host

    # Security backward compatibility
    @property
    def secret_key(self) -> str | None:
        """Backward compatibility: secret_key."""
        return self.security.secret_key

    @secret_key.setter
    def secret_key(self, value: str | None) -> None:
        """Setter for secret_key to allow test fixtures to modify it."""
        self.security.secret_key = value

    # External services backward compatibility
    @property
    def email_api_key(self) -> str:
        """Backward compatibility: email_api_key."""
        return self.external_services.email_api_key

    # Security backward compatibility (continued)
    @property
    def rate_limit_enabled(self) -> bool:
        """Backward compatibility: rate_limit_enabled."""
        return self.security.rate_limit_enabled

    @property
    def rate_limit_per_minute(self) -> int:
        """Backward compatibility: rate_limit_per_minute."""
        return self.security.rate_limit_per_minute

    @property
    def cors_allow_credentials(self) -> bool:
        """Backward compatibility: cors_allow_credentials."""
        return self.security.cors_allow_credentials

    @property
    def cors_allow_methods(self) -> list[str]:
        """Backward compatibility: cors_allow_methods."""
        return self.security.cors_allow_methods

    @property
    def cors_allow_headers(self) -> list[str]:
        """Backward compatibility: cors_allow_headers."""
        return self.security.cors_allow_headers

    @property
    def cors_expose_headers(self) -> list[str]:
        """Backward compatibility: cors_expose_headers."""
        return self.security.cors_expose_headers

    # Workflow backward compatibility
    @property
    def temporal_host(self) -> str:
        """Backward compatibility: temporal_host."""
        return self.workflow.temporal_host

    @property
    def temporal_namespace(self) -> str:
        """Backward compatibility: temporal_namespace."""
        return self.workflow.temporal_namespace

    # Observability backward compatibility
    @property
    def otel_enabled(self) -> bool:
        """Backward compatibility: otel_enabled."""
        return self.observability.otel_enabled

    @property
    def otel_service_name(self) -> str:
        """Backward compatibility: otel_service_name."""
        return self.observability.otel_service_name

    @property
    def otel_trace_sample_rate(self) -> float:
        """Backward compatibility: otel_trace_sample_rate."""
        return self.observability.otel_trace_sample_rate

    @property
    def otel_exporter_otlp_endpoint(self) -> str:
        """Backward compatibility: otel_exporter_otlp_endpoint."""
        return self.observability.otel_exporter_otlp_endpoint

    @property
    def otel_exporter_otlp_insecure(self) -> bool:
        """Backward compatibility: otel_exporter_otlp_insecure."""
        return self.observability.otel_exporter_otlp_insecure

    # Cache backward compatibility
    @property
    def redis_max_connections(self) -> int:
        """Backward compatibility: redis_max_connections."""
        return self.cache.redis_max_connections

    # API backward compatibility
    @property
    def docs_url(self) -> str:
        """Backward compatibility: docs_url."""
        return self.app.docs_url

    @property
    def redoc_url(self) -> str:
        """Backward compatibility: redoc_url."""
        return self.app.redoc_url

    @property
    def openapi_url(self) -> str:
        """Backward compatibility: openapi_url."""
        return self.app.openapi_url

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
    "AppSettings",
    "CacheSettings",
    "DatabaseSettings",
    "ExternalServicesSettings",
    "ObservabilitySettings",
    "PluginSettings",
    "SecuritySettings",
    "Settings",
    "WorkflowSettings",
    "get_settings",
]
