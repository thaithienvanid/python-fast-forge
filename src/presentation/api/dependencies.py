"""Common API dependencies for tenant isolation."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from pydantic import ValidationError
from structlog import get_logger

from src.infrastructure.config import Settings, get_settings
from src.presentation.schemas.error import ErrorDetail
from src.utils.tenant_auth import decode_tenant_token


logger = get_logger(__name__)


async def get_tenant_id(
    x_tenant_token: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> UUID | None:
    """Extract tenant ID from request using X-Tenant-Token (JWT with ES256).

    This provides secure tenant isolation by validating JWT tokens signed with ES256
    (Elliptic Curve Digital Signature Algorithm) and extracting the tenant_id claim.
    Returns None if no token is provided (no tenant isolation).

    The JWT token must:
    - Be signed with ES256 algorithm
    - Contain a valid 'tenant_id' claim with UUID
    - Not be expired
    - Have a valid signature

    Args:
        x_tenant_token: Optional JWT token containing tenant_id claim
        settings: Application settings with JWT keys and algorithm

    Returns:
        UUID of tenant if authentication successful, None otherwise

    Raises:
        401: If token is invalid, expired, or missing tenant_id claim

    Security:
        - Tokens use ES256 (asymmetric key cryptography)
        - Public/private key pair prevents token forgery
        - Token expiration checked automatically
        - Invalid signatures rejected
        - Malformed tokens return 401 Unauthorized

    Example:
        ```python
        # API request with JWT tenant token
        curl -H "X-Tenant-Token: eyJhbGc..." /api/v1/users
        ```
    """
    if x_tenant_token:
        try:
            # Get settings if not provided (for testing)
            if settings is None:
                settings = get_settings()

            # Decode and validate JWT token
            claims = decode_tenant_token(x_tenant_token, settings)

            # Extract tenant_id
            tenant_id = claims.tenant_id

            logger.debug(
                "tenant_id_extracted",
                tenant_id=str(tenant_id),
                algorithm=settings.jwt_algorithm,
                message="Successfully extracted tenant ID from JWT",
            )
            return tenant_id

        except JWTError as e:
            # Handle JWT-specific errors
            error_msg = str(e).lower()

            if "expired" in error_msg or "signature has expired" in error_msg:
                logger.warning(
                    "tenant_token_expired",
                    message="X-Tenant-Token has expired",
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetail(
                        code="TENANT_TOKEN_EXPIRED",
                        message="Tenant token has expired",
                    ).model_dump(),
                ) from None

            if "signature" in error_msg:
                logger.warning(
                    "tenant_token_invalid_signature",
                    message="X-Tenant-Token has invalid signature",
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=ErrorDetail(
                        code="TENANT_TOKEN_INVALID_SIGNATURE",
                        message="Invalid tenant token signature",
                    ).model_dump(),
                ) from None

            # Generic JWT error
            logger.warning(
                "tenant_token_invalid",
                error=str(e),
                message="X-Tenant-Token validation failed",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorDetail(
                    code="TENANT_TOKEN_MALFORMED",
                    message="Malformed tenant token",
                ).model_dump(),
            ) from None

        except (ValueError, ValidationError, KeyError) as e:
            # Handle validation errors from claims model (missing/invalid claims)
            logger.warning(
                "tenant_token_claims_invalid",
                error=str(e),
                message="tenant_id claim is invalid",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorDetail(
                    code="TENANT_TOKEN_INVALID_CLAIMS",
                    message="Invalid tenant token claims",
                    details={"error": str(e)},
                ).model_dump(),
            ) from None

        except HTTPException:
            raise

        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(
                "tenant_token_validation_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorDetail(
                    code="TENANT_TOKEN_VALIDATION_FAILED",
                    message="Invalid tenant token",
                ).model_dump(),
            ) from e

    # No tenant isolation - return None
    logger.debug("no_tenant_isolation", message="No X-Tenant-Token provided")
    return None
