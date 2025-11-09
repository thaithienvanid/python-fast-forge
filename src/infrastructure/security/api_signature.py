"""API signature authentication for external partners/services.

This module implements HMAC-based request signature authentication,
commonly used for secure API-to-API communication with external partners.
"""

import hashlib
import hmac
import time
from typing import Annotated

from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel, Field


class APIClient(BaseModel):
    """API client configuration.

    Represents an external partner or service that can access the API.
    """

    client_id: str = Field(..., description="Unique client identifier")
    secret_key: str = Field(..., description="Secret key for HMAC signature")
    is_active: bool = Field(default=True, description="Whether client is active")
    allowed_ips: list[str] = Field(
        default_factory=list,
        description="Allowed IP addresses (empty = all IPs allowed)",
    )


class SignatureValidator:
    """Validates HMAC-based API request signatures.

    Authentication Flow:
    1. Client creates signature: HMAC-SHA256(secret_key, payload)
    2. Payload = timestamp + method + path + body
    3. Client sends: X-API-Client-ID, X-API-Timestamp, X-API-Signature
    4. Server validates timestamp (prevents replay attacks)
    5. Server recomputes signature and compares
    """

    def __init__(self, api_clients: dict[str, APIClient], timestamp_tolerance: int = 300):
        """Initialize signature validator.

        Args:
            api_clients: Dictionary of client_id -> APIClient
            timestamp_tolerance: Maximum age of request in seconds (default: 5 minutes)
        """
        self._clients = api_clients
        self._timestamp_tolerance = timestamp_tolerance

    def _create_signature_payload(
        self,
        timestamp: str,
        method: str,
        path: str,
        body: bytes,
    ) -> str:
        """Create signature payload from request components.

        Args:
            timestamp: Unix timestamp as string
            method: HTTP method (GET, POST, etc.)
            path: Request path including query params
            body: Request body as bytes

        Returns:
            Signature payload string
        """
        # Normalize method to uppercase
        method = method.upper()

        # Include body hash for non-GET requests
        if body:
            body_hash = hashlib.sha256(body).hexdigest()
        else:
            body_hash = ""

        # Create payload: timestamp + method + path + body_hash
        return f"{timestamp}:{method}:{path}:{body_hash}"

    def _compute_signature(self, secret_key: str, payload: str) -> str:
        """Compute HMAC-SHA256 signature.

        Args:
            secret_key: Client's secret key
            payload: Signature payload

        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def validate_signature(
        self,
        client_id: str,
        timestamp: str,
        signature: str,
        method: str,
        path: str,
        body: bytes,
        client_ip: str | None = None,
    ) -> APIClient:
        """Validate request signature.

        Args:
            client_id: Client identifier from X-API-Client-ID header
            timestamp: Unix timestamp from X-API-Timestamp header
            signature: HMAC signature from X-API-Signature header
            method: HTTP method
            path: Request path
            body: Request body
            client_ip: Client IP address (optional)

        Returns:
            APIClient if signature is valid

        Raises:
            HTTPException: If validation fails
        """
        # Check if client exists
        client = self._clients.get(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API client ID",
            )

        # Check if client is active
        if not client.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API client is inactive",
            )

        # Check IP whitelist
        if client.allowed_ips and client_ip and client_ip not in client.allowed_ips:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP address not allowed",
            )

        # Validate timestamp
        try:
            request_time = int(timestamp)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid timestamp format",
            ) from None

        current_time = int(time.time())
        time_diff = abs(current_time - request_time)

        if time_diff > self._timestamp_tolerance:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Request timestamp too old or in future (tolerance: {self._timestamp_tolerance}s)",
            )

        # Compute expected signature
        payload = self._create_signature_payload(timestamp, method, path, body)
        expected_signature = self._compute_signature(client.secret_key, payload)

        # Compare signatures (constant-time comparison to prevent timing attacks)
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        return client


# Global validator instance (configure in app startup)
_signature_validator: SignatureValidator | None = None


def init_signature_validator(api_clients: dict[str, APIClient]) -> None:
    """Initialize global signature validator.

    Call this during app startup to configure API clients.

    Example:
        api_clients = {
            "partner1": APIClient(
                client_id="partner1",
                secret_key="super-secret-key",
                allowed_ips=["192.168.1.100"],
            ),
        }
        init_signature_validator(api_clients)
    """
    global _signature_validator
    _signature_validator = SignatureValidator(api_clients)


async def verify_api_signature(
    request: Request,
    x_api_client_id: Annotated[str, Header(..., description="API Client ID")],
    x_api_timestamp: Annotated[str, Header(..., description="Unix timestamp")],
    x_api_signature: Annotated[str, Header(..., description="HMAC-SHA256 signature")],
) -> APIClient:
    """FastAPI dependency for verifying API signatures.

    Usage:
        @app.post("/api/external/webhook")
        async def webhook(
            data: dict,
            client: APIClient = Depends(verify_api_signature)
        ):
            # Request is authenticated
            return {"status": "ok"}

    Args:
        request: FastAPI request object
        x_api_client_id: Client ID from header
        x_api_timestamp: Timestamp from header
        x_api_signature: Signature from header

    Returns:
        Validated APIClient

    Raises:
        HTTPException: If signature is invalid
    """
    if not _signature_validator:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API signature validation not configured",
        )

    # Read request body
    body = await request.body()

    # Get client IP
    client_ip = request.client.host if request.client else None

    # Build full path with query params
    path = str(request.url.path)
    if request.url.query:
        path = f"{path}?{request.url.query}"

    # Validate signature
    return _signature_validator.validate_signature(
        client_id=x_api_client_id,
        timestamp=x_api_timestamp,
        signature=x_api_signature,
        method=request.method,
        path=path,
        body=body,
        client_ip=client_ip,
    )


def create_signature(
    client_id: str,
    secret_key: str,
    method: str,
    path: str,
    body: bytes = b"",
) -> tuple[str, str, str]:
    """Helper function to create API signature (for clients/testing).

    Args:
        client_id: API client ID
        secret_key: Secret key
        method: HTTP method
        path: Request path
        body: Request body

    Returns:
        Tuple of (client_id, timestamp, signature)

    Example:
        >>> client_id, timestamp, signature = create_signature(
        ...     "partner1", "secret", "POST", "/api/external/webhook", b'{"data":"value"}'
        ... )
        >>> headers = {
        ...     "X-API-Client-ID": client_id,
        ...     "X-API-Timestamp": timestamp,
        ...     "X-API-Signature": signature,
        ... }
    """
    timestamp = str(int(time.time()))

    # Create payload
    method = method.upper()
    body_hash = hashlib.sha256(body).hexdigest() if body else ""
    payload = f"{timestamp}:{method}:{path}:{body_hash}"

    # Compute signature
    signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return client_id, timestamp, signature
