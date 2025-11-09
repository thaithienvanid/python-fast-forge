"""Integration tests for partner API endpoints with signature authentication."""

import json

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.infrastructure.security.api_signature import (
    APIClient,
    create_signature,
    init_signature_validator,
)
from src.presentation.api.v1.endpoints.partners import router


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_clients() -> dict[str, APIClient]:
    """Create test API clients for partners with different configurations."""
    return {
        "partner1": APIClient(
            client_id="partner1",
            secret_key="test-secret-key-123",
            is_active=True,
            allowed_ips=[],  # No IP restrictions for testing
        ),
        "partner2": APIClient(
            client_id="partner2",
            secret_key="another-secret-key",
            is_active=True,
        ),
    }


@pytest.fixture
def test_app(api_clients: dict[str, APIClient]) -> TestClient:
    """Create test FastAPI app with partner routes and mock middleware."""
    from fastapi import FastAPI

    # Initialize signature validator
    init_signature_validator(api_clients)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Mock request state middleware
    @app.middleware("http")
    async def mock_request_state(request, call_next):
        request.state.trace_id = "test-trace-123"
        request.state.client_ip = "127.0.0.1"
        response = await call_next(request)
        return response

    return TestClient(app)


def create_auth_headers(
    client_id: str,
    secret_key: str,
    method: str,
    path: str,
    body: bytes = b"",
) -> dict[str, str]:
    """Create authentication headers with valid HMAC signature."""
    _, timestamp, signature = create_signature(
        client_id=client_id,
        secret_key=secret_key,
        method=method,
        path=path,
        body=body,
    )

    return {
        "X-API-Client-ID": client_id,
        "X-API-Timestamp": timestamp,
        "X-API-Signature": signature,
    }


# ============================================================================
# Webhook Endpoint Tests
# ============================================================================


class TestWebhookEndpoint:
    """Test POST /api/v1/partners/webhook endpoint for receiving events."""

    def test_receives_webhook_successfully(self, test_app: TestClient) -> None:
        """Test successful webhook event reception with valid signature.

        Arrange: Valid webhook payload with authentication headers
        Act: POST /api/v1/partners/webhook
        Assert: Returns 200 with confirmation and trace_id
        """
        # Arrange
        payload = {
            "event_type": "order.created",
            "event_id": "evt_123456",
            "data": {"order_id": "ord_789", "amount": 99.99},
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/webhook",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/webhook",
            content=body,  # Use content to send exact body for signature
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["received"] is True
        assert data["event_id"] == "evt_123456"
        assert "trace_id" in data["message"]

    def test_rejects_webhook_without_authentication_headers(self, test_app: TestClient) -> None:
        """Test webhook fails when authentication headers are missing.

        Arrange: Valid payload but no auth headers
        Act: POST /api/v1/partners/webhook
        Assert: Returns 422 validation error
        """
        # Arrange
        payload = {
            "event_type": "order.created",
            "event_id": "evt_123",
            "data": {},
        }

        # Act
        response = test_app.post("/api/v1/partners/webhook", json=payload)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_webhook_with_invalid_signature(self, test_app: TestClient) -> None:
        """Test webhook fails with incorrect signature hash.

        Arrange: Valid payload with invalid signature
        Act: POST /api/v1/partners/webhook
        Assert: Returns 401 unauthorized error
        """
        # Arrange
        payload = {
            "event_type": "order.created",
            "event_id": "evt_123",
            "data": {},
        }

        headers = {
            "X-API-Client-ID": "partner1",
            "X-API-Timestamp": "1234567890",
            "X-API-Signature": "invalid-signature-here",
        }

        # Act
        response = test_app.post(
            "/api/v1/partners/webhook",
            json=payload,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_accepts_webhook_from_different_partner(self, test_app: TestClient) -> None:
        """Test webhook works with different partner credentials.

        Arrange: Valid payload from partner2 with correct signature
        Act: POST /api/v1/partners/webhook
        Assert: Returns 200 with event_id confirmation
        """
        # Arrange
        payload = {
            "event_type": "user.updated",
            "event_id": "evt_789",
            "data": {"user_id": "usr_456"},
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner2",
            secret_key="another-secret-key",
            method="POST",
            path="/api/v1/partners/webhook",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/webhook",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["event_id"] == "evt_789"

    def test_rejects_webhook_with_missing_required_fields(self, test_app: TestClient) -> None:
        """Test webhook fails validation with incomplete payload.

        Arrange: Payload missing required event_id and data fields
        Act: POST /api/v1/partners/webhook
        Assert: Returns 422 validation error
        """
        # Arrange
        payload = {
            "event_type": "test",
            # Missing event_id and data
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/webhook",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/webhook",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_webhook_includes_logging(self, test_app: TestClient, caplog) -> None:
        """Test webhook endpoint logs events correctly.

        Arrange: Valid webhook payload with logging enabled
        Act: POST /api/v1/partners/webhook
        Assert: Returns 200 and logs event
        """
        # Arrange
        import logging

        caplog.set_level(logging.INFO)

        payload = {
            "event_type": "test.event",
            "event_id": "evt_integration",
            "data": {"test": "data"},
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/webhook",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/webhook",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Data Sync Endpoint Tests
# ============================================================================


class TestDataSyncEndpoint:
    """Test POST /api/v1/partners/sync endpoint for data synchronization."""

    def test_queues_sync_successfully(self, test_app: TestClient) -> None:
        """Test successful data sync request queuing.

        Arrange: Valid sync payload with entity type and IDs
        Act: POST /api/v1/partners/sync
        Assert: Returns 202 with sync_id and status=queued
        """
        # Arrange
        payload = {
            "entity_type": "users",
            "entity_ids": ["usr_1", "usr_2", "usr_3"],
            "sync_metadata": {"priority": "high"},
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/sync",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/sync",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["sync_id"].startswith("sync_")
        assert data["entity_type"] == "users"
        assert data["total_entities"] == 3
        assert data["status"] == "queued"

    def test_rejects_invalid_entity_type(self, test_app: TestClient) -> None:
        """Test sync fails with unsupported entity type.

        Arrange: Payload with invalid entity_type
        Act: POST /api/v1/partners/sync
        Assert: Returns 400 with error and allowed_types
        """
        # Arrange
        payload = {
            "entity_type": "invalid_type",
            "entity_ids": ["id1", "id2"],
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/sync",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/sync",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid entity type" in data["detail"]["error"]
        assert "allowed_types" in data["detail"]

    @pytest.mark.parametrize(
        "entity_type",
        ["users", "products", "orders", "inventory"],
    )
    def test_accepts_all_valid_entity_types(self, test_app: TestClient, entity_type: str) -> None:
        """Test sync accepts all supported entity types.

        Arrange: Payload with each valid entity type
        Act: POST /api/v1/partners/sync
        Assert: Returns 202 with correct entity_type
        """
        # Arrange
        payload = {
            "entity_type": entity_type,
            "entity_ids": ["id1", "id2"],
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/sync",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/sync",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["entity_type"] == entity_type

    def test_works_without_sync_metadata(self, test_app: TestClient) -> None:
        """Test sync succeeds without optional sync_metadata field.

        Arrange: Payload with only required fields
        Act: POST /api/v1/partners/sync
        Assert: Returns 202 accepted
        """
        # Arrange
        payload = {
            "entity_type": "products",
            "entity_ids": ["prod_1"],
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/sync",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/sync",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_rejects_sync_with_missing_required_fields(self, test_app: TestClient) -> None:
        """Test sync fails validation without entity_ids field.

        Arrange: Payload missing required entity_ids
        Act: POST /api/v1/partners/sync
        Assert: Returns 422 validation error
        """
        # Arrange
        payload = {
            "entity_type": "users",
            # Missing entity_ids
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/sync",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/sync",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_includes_trace_id_in_sync_id(self, test_app: TestClient) -> None:
        """Test sync_id is derived from request trace_id.

        Arrange: Valid sync payload
        Act: POST /api/v1/partners/sync
        Assert: sync_id starts with sync_ prefix from trace
        """
        # Arrange
        payload = {
            "entity_type": "orders",
            "entity_ids": ["ord_1"],
        }

        body = json.dumps(payload).encode()
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="POST",
            path="/api/v1/partners/sync",
            body=body,
        )
        headers["Content-Type"] = "application/json"

        # Act
        response = test_app.post(
            "/api/v1/partners/sync",
            content=body,
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["sync_id"].startswith("sync_")


# ============================================================================
# Partner Status Endpoint Tests
# ============================================================================


class TestPartnerStatusEndpoint:
    """Test GET /api/v1/partners/status endpoint for authentication verification."""

    def test_returns_partner_status_successfully(self, test_app: TestClient) -> None:
        """Test status endpoint returns partner information.

        Arrange: Valid authentication headers
        Act: GET /api/v1/partners/status
        Assert: Returns 200 with partner_id and auth confirmation
        """
        # Arrange
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="GET",
            path="/api/v1/partners/status",
            body=b"",
        )

        # Act
        response = test_app.get("/api/v1/partners/status", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["partner_id"] == "partner1"
        assert data["authenticated"] is True
        assert "allowed_ips" in data
        assert "working correctly" in data["message"]

    def test_shows_ip_restrictions_in_status(self, test_app: TestClient) -> None:
        """Test status endpoint displays IP restriction information.

        Arrange: Valid auth for partner with no IP restrictions
        Act: GET /api/v1/partners/status
        Assert: Returns allowed_ips as ["*"] (no restrictions)
        """
        # Arrange
        headers = create_auth_headers(
            client_id="partner1",
            secret_key="test-secret-key-123",
            method="GET",
            path="/api/v1/partners/status",
            body=b"",
        )

        # Act
        response = test_app.get("/api/v1/partners/status", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Empty allowed_ips shows as ["*"]
        assert data["allowed_ips"] == ["*"]

    def test_returns_status_for_different_partner(self, test_app: TestClient) -> None:
        """Test status endpoint works for multiple partners.

        Arrange: Valid auth for partner2
        Act: GET /api/v1/partners/status
        Assert: Returns status for partner2
        """
        # Arrange
        headers = create_auth_headers(
            client_id="partner2",
            secret_key="another-secret-key",
            method="GET",
            path="/api/v1/partners/status",
            body=b"",
        )

        # Act
        response = test_app.get("/api/v1/partners/status", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["partner_id"] == "partner2"

    def test_rejects_status_with_invalid_auth(self, test_app: TestClient) -> None:
        """Test status endpoint fails with invalid signature.

        Arrange: Invalid signature in auth headers
        Act: GET /api/v1/partners/status
        Assert: Returns 401 unauthorized error
        """
        # Arrange
        headers = {
            "X-API-Client-ID": "partner1",
            "X-API-Timestamp": "1234567890",
            "X-API-Signature": "wrong-signature",
        }

        # Act
        response = test_app.get("/api/v1/partners/status", headers=headers)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# Integration Tests
# ============================================================================


class TestMultiEndpointIntegration:
    """Test partner can access multiple endpoints with same credentials."""

    def test_same_partner_accesses_all_endpoints(self, test_app: TestClient) -> None:
        """Test partner1 can successfully call webhook, sync, and status.

        Arrange: Valid credentials for partner1
        Act: Call all three endpoints sequentially
        Assert: All requests succeed with appropriate status codes
        """
        # Arrange & Act - Webhook
        webhook_payload = {
            "event_type": "test",
            "event_id": "evt_1",
            "data": {},
        }
        body1 = json.dumps(webhook_payload).encode()
        headers1 = create_auth_headers(
            "partner1", "test-secret-key-123", "POST", "/api/v1/partners/webhook", body1
        )
        headers1["Content-Type"] = "application/json"

        response1 = test_app.post("/api/v1/partners/webhook", content=body1, headers=headers1)

        # Assert webhook
        assert response1.status_code == status.HTTP_200_OK

        # Act - Sync
        sync_payload = {
            "entity_type": "users",
            "entity_ids": ["u1"],
        }
        body2 = json.dumps(sync_payload).encode()
        headers2 = create_auth_headers(
            "partner1", "test-secret-key-123", "POST", "/api/v1/partners/sync", body2
        )
        headers2["Content-Type"] = "application/json"

        response2 = test_app.post("/api/v1/partners/sync", content=body2, headers=headers2)

        # Assert sync
        assert response2.status_code == status.HTTP_202_ACCEPTED

        # Act - Status
        headers3 = create_auth_headers(
            "partner1", "test-secret-key-123", "GET", "/api/v1/partners/status", b""
        )

        response3 = test_app.get("/api/v1/partners/status", headers=headers3)

        # Assert status
        assert response3.status_code == status.HTTP_200_OK
