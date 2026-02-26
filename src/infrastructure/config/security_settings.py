"""Security configuration including JWT, CORS, and rate limiting."""

from pathlib import Path
from typing import Any, cast

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """Security configuration for authentication, authorization, and API protection.

    Handles JWT configuration, CORS policies, rate limiting, and API keys.
    Provides methods for JWT key management and validation.
    """

    # JWT configuration with ES256 (Elliptic Curve)
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

    # Compliance Data Encryption
    compliance_encryption_key: str | None = Field(
        default=None,
        alias="COMPLIANCE_ENCRYPTION_KEY",
        description="32-byte (or longer) encryption key for compliance data (GDPR, HIPAA, etc.). Required length: 32 bytes minimum.",
    )

    # CORS configuration
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="CORS_ORIGINS",
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        alias="CORS_ALLOW_CREDENTIALS",
        description="Allow credentials in CORS requests",
    )
    cors_allow_methods: list[str] = Field(
        default=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        alias="CORS_ALLOW_METHODS",
        description="Allowed HTTP methods for CORS",
    )
    cors_allow_headers: list[str] = Field(
        default=[
            "Content-Type",
            "Authorization",
            "X-Trace-ID",  # W3C Trace Context standard
            "traceparent",  # W3C Trace Context (OpenTelemetry)
            "tracestate",  # W3C Trace Context state
            "CF-Ray",  # Cloudflare trace
            "X-API-Client-ID",  # API signature authentication
            "X-API-Timestamp",  # API signature authentication
            "X-API-Signature",  # API signature authentication
            "X-Tenant-Token",  # Multi-tenant JWT token
        ],
        alias="CORS_ALLOW_HEADERS",
        description="Allowed request headers for CORS",
    )
    cors_expose_headers: list[str] = Field(
        default=["X-Trace-ID"],
        alias="CORS_EXPOSE_HEADERS",
        description="Headers exposed to the browser",
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(
        default=True,
        alias="RATE_LIMIT_ENABLED",
        description="Enable rate limiting for API endpoints",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        alias="RATE_LIMIT_PER_MINUTE",
        description="Maximum requests per minute per client",
    )

    # Environment flag (needed for validation)
    is_production: bool = Field(
        default=False,
        description="Production environment flag (set internally)",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return cast("list[str]", v)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins_https(cls, v: list[str], info: Any) -> list[str]:
        """Validate CORS origins use HTTPS in production."""
        is_production = info.data.get("is_production", False)
        if is_production:
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

            # Priority 3: Development - generate ephemeral in-memory key
            if not self.is_production:
                # Generate ephemeral key (process-scoped, not persisted)
                # This avoids filesystem writes and is more secure for development
                from cryptography.hazmat.backends import default_backend  # noqa: PLC0415

                # Check if we already generated one for this instance
                if not hasattr(self, "_ephemeral_private_key"):
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
