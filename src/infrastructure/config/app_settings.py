"""Application and server configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application and server runtime configuration.

    Handles application metadata, server configuration, and runtime behavior.
    Separated from other settings to follow Single Responsibility Principle.
    """

    # Application metadata
    app_name: str = Field(default="python-fast-forge", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server configuration
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=1, alias="WORKERS")
    reload: bool = Field(default=False, alias="RELOAD")

    # API configuration
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    docs_url: str = Field(default="/docs", alias="DOCS_URL")
    redoc_url: str = Field(default="/redoc", alias="REDOC_URL")
    openapi_url: str = Field(default="/openapi.json", alias="OPENAPI_URL")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"
