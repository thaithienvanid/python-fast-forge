"""Application configuration with environment variable support."""

from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Private: Cache for ephemeral JWT keys in development (not from env vars)
    _ephemeral_private_key: str | None = None
    _ephemeral_public_key: str | None = None

    # Application
    app_name: str = Field(default="python-fast-forge", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=1, alias="WORKERS")
    reload: bool = Field(default=False, alias="RELOAD")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], alias="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(
        default=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        alias="CORS_ALLOW_METHODS",
    )
    cors_allow_headers: list[str] = Field(
        default=[
            "Content-Type",
            "Authorization",
            "X-Trace-ID",  # W3C Trace Context standard
            "traceparent",  # W3C Trace Context (OpenTelemetry)
            "tracestate",  # W3C Trace Context state
            "CF-Ray",  # Cloudflare trace (cf-request-id discontinued in 2021)
            "X-API-Client-ID",  # API signature authentication
            "X-API-Timestamp",  # API signature authentication
            "X-API-Signature",  # API signature authentication
            "X-Tenant-Token",  # Multi-tenant JWT token
        ],
        alias="CORS_ALLOW_HEADERS",
    )
    cors_expose_headers: list[str] = Field(
        default=[
            "X-Trace-ID",  # Allow clients to read trace ID
        ],
        alias="CORS_EXPOSE_HEADERS",
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    # Security - JWT with ES256 (Elliptic Curve)
    jwt_algorithm: str = Field(
        default="ES256",
        alias="JWT_ALGORITHM",
        description="JWT signing algorithm (ES256 recommended for production)",
    )
    jwt_private_key: str | None = Field(
        default=None,
        alias="JWT_PRIVATE_KEY",
        description="EC private key in base64-encoded PEM format for JWT signing",
    )
    jwt_private_key_path: str | None = Field(
        default=None,
        alias="JWT_PRIVATE_KEY_PATH",
        description="Path to EC private key file (PEM format) for JWT signing",
    )
    jwt_public_key: str | None = Field(
        default=None,
        alias="JWT_PUBLIC_KEY",
        description="EC public key in base64-encoded PEM format for JWT verification",
    )
    jwt_public_key_path: str | None = Field(
        default=None,
        alias="JWT_PUBLIC_KEY_PATH",
        description="Path to EC public key file (PEM format) for JWT verification",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        description="Token expiration time in minutes",
    )

    # API Signature Authentication
    secret_key: str | None = Field(
        default=None,
        alias="SECRET_KEY",
        description="Secret key for API signature authentication (X-API-Signature header validation)",
    )

    # API
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    docs_url: str = Field(default="/docs", alias="DOCS_URL")
    redoc_url: str = Field(default="/redoc", alias="REDOC_URL")
    openapi_url: str = Field(default="/openapi.json", alias="OPENAPI_URL")

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="fastapi-boilerplate", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_exporter_otlp_insecure: bool = Field(default=True, alias="OTEL_EXPORTER_OTLP_INSECURE")
    otel_trace_sample_rate: float = Field(default=1.0, alias="OTEL_TRACE_SAMPLE_RATE")

    # Redis/Cache
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_ttl: int = Field(default=300, alias="CACHE_TTL")  # 5 minutes default

    # Temporal Workflow Engine
    temporal_host: str = Field(default="localhost:7233", alias="TEMPORAL_HOST")
    temporal_namespace: str = Field(default="default", alias="TEMPORAL_NAMESPACE")
    temporal_task_queue: str = Field(default="fastapi-tasks", alias="TEMPORAL_TASK_QUEUE")

    # External Services
    email_api_key: str = Field(
        default="dev-email-api-key-UNSAFE",
        alias="EMAIL_API_KEY",
        description="Email API key - MUST be set in production",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return cast("list[str]", v)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins_https(cls, v: list[str], info: Any) -> list[str]:
        """Validate CORS origins use HTTPS in production."""
        # Get app_env from validation info
        app_env = info.data.get("app_env", "development")
        if app_env.lower() == "production":
            for origin in v:
                if not origin.startswith("https://") and not origin.startswith("http://localhost"):
                    raise ValueError(
                        f"Production CORS origins must use HTTPS: {origin}. "
                        f"Only localhost is allowed with http:// for testing."
                    )
        return v

    @field_validator("rate_limit_per_minute")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        """Validate rate limit is within reasonable bounds."""
        if v < 1 or v > 10000:
            raise ValueError("Rate limit must be between 1 and 10000 per minute")
        return v

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Validate JWT algorithm is supported."""
        allowed = ["ES256", "ES384", "ES512", "HS256", "HS384", "HS512"]
        if v not in allowed:
            raise ValueError(
                f"JWT_ALGORITHM must be one of {allowed}. ES256 is recommended for production."
            )
        return v

    def get_jwt_private_key(self) -> str:
        """Get or generate JWT private key for signing.

        Returns:
            Private key in PEM format

        Priority:
            1. jwt_private_key (base64-encoded PEM)
            2. jwt_private_key_path (file path)
            3. Development: auto-generate ephemeral key
            4. Fallback to secret_key for HS256

        Note:
            In development, generates an ephemeral key if no key is provided.
            In production, requires either jwt_private_key or jwt_private_key_path for ES256.
        """
        # ES256 (Elliptic Curve)
        if self.jwt_algorithm.startswith("ES"):
            # Priority 1: Base64-encoded key
            if self.jwt_private_key:
                import base64  # noqa: PLC0415

                try:
                    decoded = base64.b64decode(self.jwt_private_key)
                    return decoded.decode("utf-8")
                except Exception as e:
                    raise ValueError(f"Failed to decode JWT_PRIVATE_KEY: {e}") from e

            # Priority 2: Load from file
            if self.jwt_private_key_path:
                private_key_path = Path(self.jwt_private_key_path)
                if not private_key_path.exists():
                    raise ValueError(f"JWT private key file not found: {self.jwt_private_key_path}")
                return private_key_path.read_text()

            # Priority 3: Development - generate ephemeral key (cached)
            if not self.is_production:
                # Cache key to ensure same key across multiple calls
                if self._ephemeral_private_key is None:
                    from cryptography.hazmat.backends import default_backend  # noqa: PLC0415

                    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
                    pem = private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                    self._ephemeral_private_key = pem.decode("utf-8")

                return self._ephemeral_private_key

            raise ValueError(
                "JWT_PRIVATE_KEY or JWT_PRIVATE_KEY_PATH must be set in production for ES256 algorithm"
            )

        # HS256 (symmetric key) - fallback to secret_key
        if self.secret_key:
            return self.secret_key

        raise ValueError(
            "Either jwt_private_key/jwt_private_key_path (for ES256) or secret_key (for HS256) must be set"
        )

    def get_jwt_public_key(self) -> str:
        """Get JWT public key for verification.

        Returns:
            Public key in PEM format (for ES256) or secret key (for HS256)

        Priority:
            1. jwt_public_key (base64-encoded PEM)
            2. jwt_public_key_path (file path)
            3. Derive from private key

        Note:
            For ES256, loads from base64/file or derives from private key.
            For HS256, returns the secret key (symmetric).
        """
        # ES256 (Elliptic Curve)
        if self.jwt_algorithm.startswith("ES"):
            # Priority 1: Base64-encoded key
            if self.jwt_public_key:
                import base64  # noqa: PLC0415

                try:
                    decoded = base64.b64decode(self.jwt_public_key)
                    return decoded.decode("utf-8")
                except Exception as e:
                    raise ValueError(f"Failed to decode JWT_PUBLIC_KEY: {e}") from e

            # Priority 2: Load from file
            if self.jwt_public_key_path:
                public_key_path = Path(self.jwt_public_key_path)
                if not public_key_path.exists():
                    raise ValueError(f"JWT public key file not found: {self.jwt_public_key_path}")
                return public_key_path.read_text()

            # Priority 3: Derive from private key
            from cryptography.hazmat.backends import default_backend  # noqa: PLC0415
            from cryptography.hazmat.primitives.serialization import (  # noqa: PLC0415
                load_pem_private_key,
            )

            private_key_pem = self.get_jwt_private_key()
            private_key = load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )

            # Extract public key
            if hasattr(private_key, "public_key"):
                public_key = private_key.public_key()
                pem = public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                return pem.decode("utf-8")

            raise ValueError("Could not extract public key from private key")

        # HS256 (symmetric key) - same as private key
        return self.get_jwt_private_key()

    @field_validator("email_api_key")
    @classmethod
    def validate_email_api_key(cls, v: str, info: Any) -> str:
        """Validate email API key in production."""
        app_env = info.data.get("app_env", "development")
        if app_env.lower() == "production":
            if "dev-email" in v.lower() or "unsafe" in v.lower():
                raise ValueError(
                    "EMAIL_API_KEY must be set to a real API key in production. "
                    "Default development key is not allowed."
                )
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
