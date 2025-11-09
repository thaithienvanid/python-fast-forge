"""Partner API endpoints with signature authentication.

Example endpoints demonstrating API signature authentication for B2B partners.
These endpoints require HMAC-SHA256 request signatures for security.
"""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.infrastructure.security.api_signature import APIClient, verify_api_signature


logger = structlog.get_logger()

router = APIRouter(prefix="/partners", tags=["Partners (API Signature Auth)"])


# ============================================================================
# Request/Response Models
# ============================================================================


class WebhookPayload(BaseModel):
    """Example webhook payload from partner."""

    event_type: str = Field(..., description="Type of event (e.g., 'order.created')")
    event_id: str = Field(..., description="Unique event identifier")
    data: dict[str, Any] = Field(..., description="Event-specific data")


class WebhookResponse(BaseModel):
    """Response from webhook endpoint."""

    received: bool = Field(default=True, description="Whether webhook was received")
    event_id: str = Field(..., description="Event ID that was processed")
    message: str = Field(..., description="Response message")


class DataSyncRequest(BaseModel):
    """Example data synchronization request."""

    entity_type: str = Field(..., description="Type of entity to sync (e.g., 'users', 'products')")
    entity_ids: list[str] = Field(..., description="List of entity IDs to sync")
    sync_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional sync metadata"
    )


class DataSyncResponse(BaseModel):
    """Response from data sync endpoint."""

    sync_id: str = Field(..., description="Unique sync operation ID")
    entity_type: str = Field(..., description="Type of entity being synced")
    total_entities: int = Field(..., description="Total number of entities to sync")
    status: str = Field(default="queued", description="Sync status")


class PartnerStatusResponse(BaseModel):
    """Partner API status response."""

    partner_id: str = Field(..., description="Partner client ID")
    authenticated: bool = Field(default=True, description="Authentication status")
    allowed_ips: list[str] = Field(..., description="Whitelisted IP addresses")
    message: str = Field(..., description="Status message")


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/webhook", response_model=WebhookResponse, status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    payload: WebhookPayload,
    client: Annotated[APIClient, Depends(verify_api_signature)],
) -> WebhookResponse:
    """Receive webhook event from authenticated partner.

    This endpoint demonstrates API signature authentication for webhooks.
    Partners must sign their requests using HMAC-SHA256.

    **Authentication Required:**
    - X-API-Client-ID: Your client ID
    - X-API-Timestamp: ISO 8601 timestamp (within 5 minutes)
    - X-API-Signature: HMAC-SHA256 signature of request

    **Signature Calculation:**
    ```python
    import hmac
    import hashlib
    from datetime import datetime, timezone

    # Prepare signature components
    timestamp = datetime.now(timezone.utc).isoformat()
    method = "POST"
    path = "/api/v1/partners/webhook"
    body = json.dumps(payload).encode()

    # Create signature string
    signature_string = f"{client_id}:{timestamp}:{method}:{path}:{body.decode()}"

    # Calculate HMAC-SHA256
    signature = hmac.new(
        secret_key.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()
    ```

    **Example Request:**
    ```bash
    curl -X POST https://api.example.com/api/v1/partners/webhook \\
      -H "Content-Type: application/json" \\
      -H "X-API-Client-ID: partner-123" \\
      -H "X-API-Timestamp: 2025-01-15T10:30:00Z" \\
      -H "X-API-Signature: abc123..." \\
      -d '{"event_type": "order.created", "event_id": "evt_123", "data": {...}}'
    ```

    Args:
        request: FastAPI request object
        payload: Webhook event payload
        client: Authenticated API client (injected by dependency)

    Returns:
        WebhookResponse: Confirmation of webhook receipt

    Raises:
        HTTPException 401: Invalid or missing signature
        HTTPException 403: IP address not whitelisted
    """
    trace_id = request.state.trace_id
    client_ip = request.state.client_ip

    logger.info(
        "Webhook received from partner",
        partner_id=client.client_id,
        event_type=payload.event_type,
        event_id=payload.event_id,
        client_ip=client_ip,
    )

    # Process webhook (mock implementation)
    # In real implementation:
    # 1. Validate event_id is not duplicate
    # 2. Queue event for async processing
    # 3. Return 200 immediately (don't block webhook)

    logger.info(
        "Webhook processed successfully",
        partner_id=client.client_id,
        event_id=payload.event_id,
    )

    return WebhookResponse(
        received=True,
        event_id=payload.event_id,
        message=f"Webhook received and queued for processing (trace_id: {trace_id})",
    )


@router.post("/sync", response_model=DataSyncResponse, status_code=status.HTTP_202_ACCEPTED)
async def sync_data(
    request: Request,
    sync_request: DataSyncRequest,
    client: Annotated[APIClient, Depends(verify_api_signature)],
) -> DataSyncResponse:
    """Initiate data synchronization with authenticated partner.

    This endpoint demonstrates using API signature auth for data sync operations.
    Partners can request synchronization of specific entities.

    **Authentication Required:**
    Same signature authentication as webhook endpoint.

    Args:
        request: FastAPI request object
        sync_request: Data synchronization request
        client: Authenticated API client (injected by dependency)

    Returns:
        DataSyncResponse: Sync operation details

    Raises:
        HTTPException 401: Invalid or missing signature
        HTTPException 403: IP address not whitelisted
        HTTPException 400: Invalid entity type or IDs
    """
    trace_id = request.state.trace_id

    # Validate entity type
    allowed_entities = ["users", "products", "orders", "inventory"]
    if sync_request.entity_type not in allowed_entities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid entity type",
                "allowed_types": allowed_entities,
                "trace_id": trace_id,
            },
        )

    logger.info(
        "Data sync initiated",
        partner_id=client.client_id,
        entity_type=sync_request.entity_type,
        entity_count=len(sync_request.entity_ids),
    )

    # Create sync operation (mock implementation)
    # In real implementation:
    # 1. Create sync job in database
    # 2. Queue entities for async sync
    # 3. Return job ID for status checking
    sync_id = f"sync_{trace_id[:8]}"

    return DataSyncResponse(
        sync_id=sync_id,
        entity_type=sync_request.entity_type,
        total_entities=len(sync_request.entity_ids),
        status="queued",
    )


@router.get("/status", response_model=PartnerStatusResponse, status_code=status.HTTP_200_OK)
async def get_partner_status(
    client: Annotated[APIClient, Depends(verify_api_signature)],
) -> PartnerStatusResponse:
    """Get authenticated partner status and configuration.

    This endpoint demonstrates a simple GET request with signature auth.
    Useful for partners to verify their authentication is working correctly.

    **Authentication Required:**
    Same signature authentication, but with empty body for GET requests.

    **Note:** For GET requests, use empty string as body in signature calculation:
    ```python
    body = b""
    signature_string = f"{client_id}:{timestamp}:{method}:{path}:"
    ```

    Args:
        client: Authenticated API client (injected by dependency)

    Returns:
        PartnerStatusResponse: Partner configuration and status
    """
    logger.info("Partner status checked", partner_id=client.client_id)

    return PartnerStatusResponse(
        partner_id=client.client_id,
        authenticated=True,
        allowed_ips=client.allowed_ips if client.allowed_ips else ["*"],
        message="Authentication successful. Your API integration is working correctly.",
    )
