"""Plugin system configuration settings.

Configures the plugin discovery, loading, and runtime behavior.
Includes configurations for builtin plugins (auth, email, storage).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PluginSettings(BaseSettings):
    """Plugin system configuration.

    Controls plugin discovery, loading behavior, and builtin plugin configurations.

    Example:
        ```python
        settings = PluginSettings()

        # Plugin discovery
        print(settings.plugin_dirs)  # ["src/infrastructure/plugins/builtin"]
        print(settings.plugin_discovery_enabled)  # True

        # Email plugin (SMTP)
        print(settings.smtp_host)  # "localhost"
        print(settings.smtp_port)  # 587

        # Storage plugin (S3)
        print(settings.s3_bucket)  # "my-app-storage"
        print(settings.s3_region)  # "us-east-1"
        ```
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PLUGIN_",  # All plugin settings can be prefixed with PLUGIN_
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================================
    # Plugin Discovery
    # ============================================================================

    plugin_dirs: list[str] = Field(
        default=["src/infrastructure/plugins/builtin"],
        description="Directories to scan for plugins on startup",
    )

    plugin_discovery_enabled: bool = Field(
        default=True,
        description="Enable automatic plugin discovery and loading on startup",
    )

    plugin_auto_activate: bool = Field(
        default=True,
        description="Automatically activate discovered plugins",
    )

    # ============================================================================
    # Auth Plugin (JWT + OAuth2)
    # ============================================================================

    jwt_secret_key: str = Field(
        default="dev-jwt-secret-change-in-production",
        description="Secret key for JWT signing (required for production)",
    )

    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm for JWT signing (HS256, RS256, etc.)",
    )

    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="JWT access token expiration in minutes",
    )

    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="JWT refresh token expiration in days",
    )

    oauth2_client_id: str | None = Field(
        default=None,
        description="OAuth2 client ID for third-party authentication",
    )

    oauth2_client_secret: str | None = Field(
        default=None,
        description="OAuth2 client secret",
    )

    oauth2_redirect_uri: str | None = Field(
        default=None,
        description="OAuth2 redirect URI after authentication",
    )

    # ============================================================================
    # Email Plugin (SMTP + SendGrid)
    # ============================================================================

    smtp_host: str = Field(
        default="localhost",
        description="SMTP server hostname",
    )

    smtp_port: int = Field(
        default=587,
        description="SMTP server port (587 for TLS, 465 for SSL, 25 for plain)",
    )

    smtp_username: str | None = Field(
        default=None,
        description="SMTP authentication username",
    )

    smtp_password: str | None = Field(
        default=None,
        description="SMTP authentication password",
    )

    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS encryption for SMTP connection",
    )

    smtp_use_ssl: bool = Field(
        default=False,
        description="Use SSL encryption for SMTP connection (mutually exclusive with TLS)",
    )

    smtp_from_email: str = Field(
        default="noreply@example.com",
        description="Default FROM email address for SMTP",
    )

    smtp_from_name: str = Field(
        default="Python Fast Forge",
        description="Default FROM name for SMTP emails",
    )

    sendgrid_api_key: str | None = Field(
        default=None,
        description="SendGrid API key for email delivery",
    )

    sendgrid_from_email: str | None = Field(
        default=None,
        description="Default FROM email for SendGrid (uses smtp_from_email if not set)",
    )

    # ============================================================================
    # Storage Plugin (Local + S3)
    # ============================================================================

    storage_local_path: str = Field(
        default="./storage",
        description="Local filesystem path for file storage",
    )

    storage_max_file_size_mb: int = Field(
        default=10,
        description="Maximum file upload size in megabytes",
    )

    s3_bucket: str | None = Field(
        default=None,
        description="AWS S3 bucket name for cloud storage",
    )

    s3_region: str = Field(
        default="us-east-1",
        description="AWS S3 region",
    )

    s3_access_key_id: str | None = Field(
        default=None,
        description="AWS access key ID (uses environment/IAM role if not set)",
    )

    s3_secret_access_key: str | None = Field(
        default=None,
        description="AWS secret access key",
    )

    s3_endpoint_url: str | None = Field(
        default=None,
        description="Custom S3-compatible endpoint URL (e.g., MinIO, DigitalOcean Spaces)",
    )

    s3_use_ssl: bool = Field(
        default=True,
        description="Use SSL for S3 connections",
    )

    s3_presigned_url_expiration_seconds: int = Field(
        default=3600,
        description="Presigned URL expiration time in seconds (default 1 hour)",
    )


__all__ = ["PluginSettings"]
