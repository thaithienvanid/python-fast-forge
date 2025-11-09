"""Tenant authentication utilities using JWT with ES256.

This module provides secure tenant authentication using JSON Web Tokens (JWT)
with ES256 (Elliptic Curve Digital Signature Algorithm with SHA-256).

ES256 provides:
- Asymmetric key cryptography (public/private key pair)
- Stronger security than symmetric algorithms (HS256)
- Ability to distribute public keys for verification without exposing signing key
- Industry-standard algorithm (NIST P-256 curve)
"""

import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from authlib.jose import JoseError, JsonWebToken
from structlog import get_logger

from src.domain.tenant_claims import TenantTokenClaims
from src.infrastructure.config import Settings, get_settings


logger = get_logger(__name__)


def create_tenant_token(
    tenant_id: UUID,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    """Create a JWT token with tenant_id claim using ES256.

    Args:
        tenant_id: The tenant UUID to embed in the token
        expires_delta: Optional custom expiration time delta. If not provided,
                      uses access_token_expire_minutes from settings
        settings: Optional settings instance. If not provided, uses get_settings()

    Returns:
        Encoded JWT token string signed with ES256

    Raises:
        ValueError: If key configuration is invalid

    Example:
        ```python
        from uuid import uuid4
        from datetime import timedelta

        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)
        # Token valid for 30 minutes (default)

        # Custom expiration
        token = create_tenant_token(tenant_id, expires_delta=timedelta(hours=1))
        ```
    """
    if settings is None:
        settings = get_settings()

    # Calculate expiration time
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.now(UTC)
    expire = now + expires_delta

    # Create claims model
    claims = TenantTokenClaims(
        tenant_id=tenant_id,
        exp=expire,
        iat=now,
        type="tenant_access",
    )

    # Convert to JWT payload
    payload = claims.to_jwt_payload()

    # Get signing key
    private_key = settings.get_jwt_private_key()

    # Encode token with configured algorithm
    jwt_instance = JsonWebToken([settings.jwt_algorithm])
    header = {"alg": settings.jwt_algorithm}
    token_bytes = jwt_instance.encode(header, payload, private_key)
    token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes

    logger.debug(
        "tenant_token_created",
        tenant_id=str(tenant_id),
        algorithm=settings.jwt_algorithm,
        expires_in_minutes=expires_delta.total_seconds() / 60,
    )

    return token


def decode_tenant_token(
    token: str,
    settings: Settings | None = None,
) -> TenantTokenClaims:
    """Decode and validate a tenant JWT token using ES256.

    Args:
        token: The JWT token string to decode
        settings: Optional settings instance. If not provided, uses get_settings()

    Returns:
        Validated TenantTokenClaims object

    Raises:
        JoseError: If token has expired or is invalid (signature, format, etc.)
        ValueError: If claims are invalid

    Example:
        ```python
        try:
            claims = decode_tenant_token(token)
            tenant_id = claims.tenant_id
            print(f"Token valid for tenant: {tenant_id}")
        except JoseError as e:
            print(f"Invalid token: {e}")
        ```
    """
    if settings is None:
        settings = get_settings()

    # Get verification key
    public_key = settings.get_jwt_public_key()

    # Decode with validation using configured algorithm
    jwt_instance = JsonWebToken([settings.jwt_algorithm])
    claims_obj = jwt_instance.decode(token, public_key)

    # Validate expiration manually
    if "exp" in claims_obj:
        exp_timestamp = claims_obj["exp"]
        if (
            isinstance(exp_timestamp, (int, float))
            and datetime.now(UTC).timestamp() >= exp_timestamp
        ):
            raise JoseError("Signature has expired")

    # Authlib validates signature automatically
    payload = claims_obj

    # Convert to claims model
    claims = TenantTokenClaims.from_jwt_payload(payload)

    logger.debug(
        "tenant_token_decoded",
        tenant_id=str(claims.tenant_id),
        algorithm=settings.jwt_algorithm,
    )

    return claims


def refresh_tenant_token(
    old_token: str,
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    """Refresh a tenant token by creating a new one with the same tenant_id.

    This is useful for token rotation strategies where you want to issue a new token
    before the old one expires.

    Args:
        old_token: The existing JWT token to refresh
        expires_delta: Optional custom expiration for the new token
        settings: Optional settings instance

    Returns:
        New JWT token string with same tenant_id but new expiration

    Raises:
        JoseError: If old token has expired or is invalid

    Example:
        ```python
        # Refresh token before expiration
        new_token = refresh_tenant_token(old_token)

        # Refresh with custom expiration
        from datetime import timedelta

        new_token = refresh_tenant_token(old_token, expires_delta=timedelta(hours=2))
        ```
    """
    if settings is None:
        settings = get_settings()

    # Decode old token to get claims
    claims = decode_tenant_token(old_token, settings)

    # Add a small delay to ensure iat timestamp is different
    time.sleep(0.001)

    # Create new token with same tenant_id
    new_token = create_tenant_token(claims.tenant_id, expires_delta, settings)

    logger.info(
        "tenant_token_refreshed",
        tenant_id=str(claims.tenant_id),
        algorithm=settings.jwt_algorithm,
    )

    return new_token


def get_token_expiration(token: str, settings: Settings | None = None) -> datetime:
    """Get the expiration datetime of a JWT token.

    Args:
        token: The JWT token string
        settings: Optional settings instance

    Returns:
        Expiration datetime in UTC

    Raises:
        JoseError: If token is invalid

    Example:
        ```python
        from datetime import datetime, UTC

        exp = get_token_expiration(token)
        time_left = exp - datetime.now(UTC)
        print(f"Token expires in {time_left.total_seconds()} seconds")
        ```
    """
    if settings is None:
        settings = get_settings()

    claims = decode_tenant_token(token, settings)
    return claims.exp


def is_token_expired(token: str, settings: Settings | None = None) -> bool:
    """Check if a JWT token is expired.

    Args:
        token: The JWT token string
        settings: Optional settings instance

    Returns:
        True if token is expired, False otherwise

    Example:
        ```python
        if is_token_expired(token):
            token = refresh_tenant_token(token)
        ```
    """
    try:
        exp = get_token_expiration(token, settings)
        return datetime.now(UTC) >= exp
    except JoseError:
        # If token is invalid for any reason, consider it expired
        return True


def verify_tenant_token(
    token: str,
    expected_tenant_id: UUID | None = None,
    settings: Settings | None = None,
) -> TenantTokenClaims:
    """Verify a tenant token and optionally check tenant_id.

    Args:
        token: The JWT token string to verify
        expected_tenant_id: Optional UUID to verify against token's tenant_id
        settings: Optional settings instance

    Returns:
        Validated TenantTokenClaims object

    Raises:
        JoseError: If token is invalid
        ValueError: If expected_tenant_id doesn't match

    Example:
        ```python
        from uuid import UUID

        tenant_id = UUID("...")
        claims = verify_tenant_token(token, expected_tenant_id=tenant_id)
        ```
    """
    claims = decode_tenant_token(token, settings)

    if expected_tenant_id and claims.tenant_id != expected_tenant_id:
        raise ValueError(
            f"Token tenant_id {claims.tenant_id} does not match expected {expected_tenant_id}"
        )

    return claims
