"""Tenant token claims models for JWT authentication.

This module defines the structure of JWT claims used for tenant authentication,
providing type safety and validation through Pydantic models.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TenantTokenClaims(BaseModel):
    """JWT claims for tenant authentication tokens.

    This model defines the structure of JWT claims used for multi-tenant authentication.
    It includes required claims for tenant identification and standard JWT claims for
    security and token management.

    Attributes:
        tenant_id: UUID of the tenant (required)
        exp: Token expiration timestamp (Unix timestamp)
        iat: Token issued at timestamp (Unix timestamp)
        nbf: Token not valid before timestamp (optional, Unix timestamp)
        type: Token type identifier (default: "tenant_access")
        jti: JWT ID for token tracking (optional, for future use)

    Example:
        ```python
        from uuid import uuid4
        from datetime import datetime, timedelta, UTC

        claims = TenantTokenClaims(
            tenant_id=uuid4(),
            exp=datetime.now(UTC) + timedelta(minutes=30),
            iat=datetime.now(UTC),
            type="tenant_access",
        )
        ```
    """

    tenant_id: UUID = Field(
        ...,
        description="UUID of the tenant this token grants access to",
    )
    exp: datetime = Field(
        ...,
        description="Token expiration time (Unix timestamp)",
    )
    iat: datetime = Field(
        ...,
        description="Token issued at time (Unix timestamp)",
    )
    nbf: datetime | None = Field(
        default=None,
        description="Token not valid before time (optional, Unix timestamp)",
    )
    type: Literal["tenant_access"] = Field(
        default="tenant_access",
        description="Type of token (always 'tenant_access' for tenant tokens)",
    )
    jti: str | None = Field(
        default=None,
        description="JWT ID for token tracking (optional, for future revocation)",
    )

    @field_validator("tenant_id", mode="before")
    @classmethod
    def validate_tenant_id(cls, v: UUID | str) -> UUID:
        """Validate and convert tenant_id to UUID.

        Args:
            v: UUID object or string representation

        Returns:
            UUID object

        Raises:
            ValueError: If the value cannot be converted to UUID
        """
        if isinstance(v, str):
            return UUID(v)
        return v

    def to_jwt_payload(self) -> dict[str, str | int]:
        """Convert claims to JWT payload format.

        Returns:
            Dictionary with JWT payload, converting datetime to Unix timestamps
            and UUID to string.

        Example:
            ```python
            claims = TenantTokenClaims(...)
            payload = claims.to_jwt_payload()
            # {"tenant_id": "...", "exp": 1234567890, "iat": 1234567800, ...}
            ```
        """
        payload: dict[str, str | int] = {
            "tenant_id": str(self.tenant_id),
            "exp": int(self.exp.timestamp()),
            "iat": int(self.iat.timestamp()),
            "type": self.type,
        }

        if self.nbf is not None:
            payload["nbf"] = int(self.nbf.timestamp())

        if self.jti is not None:
            payload["jti"] = self.jti

        return payload

    @classmethod
    def from_jwt_payload(cls, payload: dict[str, int | str]) -> "TenantTokenClaims":
        """Create claims from JWT payload.

        Args:
            payload: JWT payload dictionary with Unix timestamps

        Returns:
            TenantTokenClaims instance

        Example:
            ```python
            payload = {"tenant_id": "...", "exp": 1234567890, ...}
            claims = TenantTokenClaims.from_jwt_payload(payload)
            ```
        """
        # Convert timestamps to datetime
        exp_timestamp = payload["exp"]
        iat_timestamp = payload["iat"]

        # Handle both int and float timestamps
        exp = datetime.fromtimestamp(
            float(exp_timestamp) if isinstance(exp_timestamp, (int, float)) else 0,
            UTC,
        )
        iat = datetime.fromtimestamp(
            float(iat_timestamp) if isinstance(iat_timestamp, (int, float)) else 0,
            UTC,
        )

        # Optional nbf
        nbf = None
        if "nbf" in payload:
            nbf_timestamp = payload["nbf"]
            nbf = datetime.fromtimestamp(
                float(nbf_timestamp) if isinstance(nbf_timestamp, (int, float)) else 0,
                UTC,
            )

        return cls(
            tenant_id=UUID(str(payload["tenant_id"])),
            exp=exp,
            iat=iat,
            nbf=nbf,
            type=str(payload.get("type", "tenant_access")),  # type: ignore[arg-type]
            jti=str(payload["jti"]) if "jti" in payload else None,
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenant_id": "018c5e9e-1234-7000-8000-000000000001",
                    "exp": 1734567890,
                    "iat": 1734565890,
                    "type": "tenant_access",
                }
            ]
        }
    }
