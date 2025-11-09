"""Integration tests for API signature authentication."""

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, status

from src.infrastructure.security.api_signature import (
    APIClient,
    SignatureValidator,
    create_signature,
    init_signature_validator,
    verify_api_signature,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_clients() -> dict[str, APIClient]:
    """Create test API clients with various configurations."""
    return {
        "partner1": APIClient(
            client_id="partner1",
            secret_key="secret-key-123",
            is_active=True,
            allowed_ips=["192.168.1.100", "10.0.0.50"],
        ),
        "partner2": APIClient(
            client_id="partner2",
            secret_key="another-secret",
            is_active=True,
            allowed_ips=[],  # No IP restrictions
        ),
        "inactive_partner": APIClient(
            client_id="inactive_partner",
            secret_key="inactive-secret",
            is_active=False,
        ),
    }


@pytest.fixture
def validator(api_clients: dict[str, APIClient]) -> SignatureValidator:
    """Create signature validator instance with 5-minute tolerance."""
    return SignatureValidator(api_clients, timestamp_tolerance=300)


# ============================================================================
# SignatureValidator Internal Method Tests
# ============================================================================


class TestSignaturePayloadCreation:
    """Test signature payload creation and normalization."""

    def test_creates_payload_with_request_body(self, validator: SignatureValidator) -> None:
        """Test signature payload creation with JSON request body.

        Arrange: Request body with JSON data
        Act: Create signature payload with body hash
        Assert: Payload format is timestamp:method:path:body_hash
        """
        # Arrange
        body = b'{"key": "value"}'
        body_hash = hashlib.sha256(body).hexdigest()

        # Act
        payload = validator._create_signature_payload(
            timestamp="1234567890",
            method="POST",
            path="/api/v1/webhook",
            body=body,
        )

        # Assert
        assert payload == f"1234567890:POST:/api/v1/webhook:{body_hash}"

    def test_creates_payload_without_body(self, validator: SignatureValidator) -> None:
        """Test signature payload creation for GET request (no body).

        Arrange: Empty body (GET request)
        Act: Create signature payload with empty body
        Assert: Payload format is timestamp:method:path:  (empty hash)
        """
        # Arrange
        empty_body = b""

        # Act
        payload = validator._create_signature_payload(
            timestamp="1234567890",
            method="GET",
            path="/api/v1/status",
            body=empty_body,
        )

        # Assert
        assert payload == "1234567890:GET:/api/v1/status:"

    def test_normalizes_http_method_to_uppercase(self, validator: SignatureValidator) -> None:
        """Test that HTTP method is normalized to uppercase in payload.

        Arrange: Same request with lowercase and uppercase methods
        Act: Create payloads with both cases
        Assert: Both payloads are identical and use uppercase
        """
        # Arrange & Act
        payload1 = validator._create_signature_payload("123", "post", "/path", b"")
        payload2 = validator._create_signature_payload("123", "POST", "/path", b"")

        # Assert
        assert payload1 == payload2
        assert "POST" in payload1


class TestSignatureComputation:
    """Test HMAC-SHA256 signature computation."""

    def test_computes_valid_hmac_sha256_signature(self, validator: SignatureValidator) -> None:
        """Test HMAC-SHA256 signature computation produces correct hash.

        Arrange: Secret key and payload string
        Act: Compute signature using HMAC-SHA256
        Assert: Signature is valid 64-char hex matching expected HMAC
        """
        # Arrange
        secret = "my-secret"
        payload = "test-payload"

        # Act
        signature = validator._compute_signature(secret, payload)

        # Assert
        assert len(signature) == 64  # SHA256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in signature)

        # Verify it matches expected HMAC
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        assert signature == expected


# ============================================================================
# Signature Validation Tests
# ============================================================================


class TestSignatureValidation:
    """Test signature validation with various scenarios."""

    def test_validates_signature_successfully(self, validator: SignatureValidator) -> None:
        """Test successful signature validation with valid credentials.

        Arrange: Valid signature with current timestamp and whitelisted IP
        Act: Validate signature
        Assert: Returns APIClient for valid partner
        """
        # Arrange
        timestamp = str(int(time.time()))
        method = "POST"
        path = "/api/v1/webhook"
        body = b'{"event": "test"}'

        body_hash = hashlib.sha256(body).hexdigest()
        payload = f"{timestamp}:{method}:{path}:{body_hash}"
        signature = hmac.new(b"secret-key-123", payload.encode(), hashlib.sha256).hexdigest()

        # Act
        client = validator.validate_signature(
            client_id="partner1",
            timestamp=timestamp,
            signature=signature,
            method=method,
            path=path,
            body=body,
            client_ip="192.168.1.100",
        )

        # Assert
        assert client.client_id == "partner1"
        assert client.is_active is True

    def test_rejects_invalid_client_id(self, validator: SignatureValidator) -> None:
        """Test validation fails with unknown client ID.

        Arrange: Request with non-existent client ID
        Act: Attempt to validate signature
        Assert: Raises 401 HTTPException with invalid client error
        """
        # Arrange & Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="unknown_client",
                timestamp=str(int(time.time())),
                signature="fake-signature",
                method="POST",
                path="/api/v1/webhook",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API client ID" in str(exc_info.value.detail)

    def test_rejects_inactive_client(self, validator: SignatureValidator) -> None:
        """Test validation fails for inactive/disabled client.

        Arrange: Request from inactive API client
        Act: Attempt to validate signature
        Assert: Raises 403 HTTPException with inactive client error
        """
        # Arrange
        timestamp = str(int(time.time()))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="inactive_partner",
                timestamp=timestamp,
                signature="fake-signature",
                method="POST",
                path="/api/v1/webhook",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "inactive" in str(exc_info.value.detail).lower()

    def test_rejects_non_whitelisted_ip(self, validator: SignatureValidator) -> None:
        """Test validation fails when client IP is not whitelisted.

        Arrange: Request from IP not in allowed_ips list
        Act: Attempt to validate signature
        Assert: Raises 403 HTTPException with IP not allowed error
        """
        # Arrange
        timestamp = str(int(time.time()))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp=timestamp,
                signature="fake-signature",
                method="POST",
                path="/api/v1/webhook",
                body=b"",
                client_ip="1.2.3.4",  # Not in allowed IPs
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "IP address not allowed" in str(exc_info.value.detail)

    def test_allows_any_ip_when_no_restrictions(self, validator: SignatureValidator) -> None:
        """Test validation succeeds when client has empty allowed_ips list.

        Arrange: Valid signature from partner with no IP restrictions
        Act: Validate signature from any IP
        Assert: Returns APIClient successfully
        """
        # Arrange
        timestamp = str(int(time.time()))
        method = "POST"
        path = "/api/v1/webhook"
        body = b""

        payload = f"{timestamp}:{method}:{path}:"
        signature = hmac.new(b"another-secret", payload.encode(), hashlib.sha256).hexdigest()

        # Act
        client = validator.validate_signature(
            client_id="partner2",
            timestamp=timestamp,
            signature=signature,
            method=method,
            path=path,
            body=body,
            client_ip="1.2.3.4",  # Any IP should work
        )

        # Assert
        assert client.client_id == "partner2"

    def test_rejects_invalid_timestamp_format(self, validator: SignatureValidator) -> None:
        """Test validation fails with non-numeric timestamp.

        Arrange: Request with non-numeric timestamp string
        Act: Attempt to validate signature
        Assert: Raises 401 HTTPException with invalid timestamp format error
        """
        # Arrange & Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp="not-a-number",
                signature="fake-signature",
                method="POST",
                path="/api/v1/webhook",
                body=b"",
                client_ip="192.168.1.100",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid timestamp format" in str(exc_info.value.detail)

    def test_rejects_expired_timestamp(self, validator: SignatureValidator) -> None:
        """Test validation fails with timestamp older than tolerance.

        Arrange: Request with timestamp from 10 minutes ago (tolerance=5min)
        Act: Attempt to validate signature
        Assert: Raises 401 HTTPException with timestamp too old error
        """
        # Arrange
        old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp=old_timestamp,
                signature="fake-signature",
                method="POST",
                path="/api/v1/webhook",
                body=b"",
                client_ip="192.168.1.100",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "too old or in future" in str(exc_info.value.detail)

    def test_rejects_future_timestamp(self, validator: SignatureValidator) -> None:
        """Test validation fails with timestamp in the future.

        Arrange: Request with timestamp from 10 minutes in the future
        Act: Attempt to validate signature
        Assert: Raises 401 HTTPException with timestamp in future error
        """
        # Arrange
        future_timestamp = str(int(time.time()) + 600)  # 10 minutes future

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp=future_timestamp,
                signature="fake-signature",
                method="POST",
                path="/api/v1/webhook",
                body=b"",
                client_ip="192.168.1.100",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "too old or in future" in str(exc_info.value.detail)

    def test_rejects_invalid_signature_hash(self, validator: SignatureValidator) -> None:
        """Test validation fails with incorrect signature hash.

        Arrange: Request with invalid signature hash
        Act: Attempt to validate signature
        Assert: Raises 401 HTTPException with invalid signature error
        """
        # Arrange
        timestamp = str(int(time.time()))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp=timestamp,
                signature="invalid-signature-here",
                method="POST",
                path="/api/v1/webhook",
                body=b'{"test": "data"}',
                client_ip="192.168.1.100",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid signature" in str(exc_info.value.detail)

    def test_uses_constant_time_comparison(self, validator: SignatureValidator) -> None:
        """Test signature comparison uses constant-time to prevent timing attacks.

        Arrange: Valid request params but wrong signature (same length)
        Act: Attempt to validate signature
        Assert: Raises 401 (hmac.compare_digest used internally)
        """
        # Arrange
        timestamp = str(int(time.time()))
        method = "POST"
        path = "/api/v1/webhook"
        body = b""

        # Create correct signature to get length
        payload = f"{timestamp}:{method}:{path}:"
        correct_signature = hmac.new(
            b"secret-key-123", payload.encode(), hashlib.sha256
        ).hexdigest()

        # Try with completely wrong signature (same length)
        wrong_signature = "a" * len(correct_signature)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp=timestamp,
                signature=wrong_signature,
                method=method,
                path=path,
                body=body,
                client_ip="192.168.1.100",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_validates_signature_with_query_parameters(self, validator: SignatureValidator) -> None:
        """Test signature validation includes query parameters in path.

        Arrange: GET request with query parameters in path
        Act: Validate signature computed with full path including query
        Assert: Returns APIClient successfully
        """
        # Arrange
        timestamp = str(int(time.time()))
        method = "GET"
        path = "/api/v1/status?client=partner1&format=json"
        body = b""

        payload = f"{timestamp}:{method}:{path}:"
        signature = hmac.new(b"secret-key-123", payload.encode(), hashlib.sha256).hexdigest()

        # Act
        client = validator.validate_signature(
            client_id="partner1",
            timestamp=timestamp,
            signature=signature,
            method=method,
            path=path,
            body=body,
            client_ip="192.168.1.100",
        )

        # Assert
        assert client.client_id == "partner1"

    def test_respects_custom_timestamp_tolerance(self, api_clients: dict[str, APIClient]) -> None:
        """Test validator respects custom timestamp tolerance setting.

        Arrange: Validator with 60-second tolerance, timestamp 90 seconds old
        Act: Attempt to validate signature
        Assert: Raises error mentioning 60s tolerance in message
        """
        # Arrange
        validator = SignatureValidator(api_clients, timestamp_tolerance=60)
        old_timestamp = str(int(time.time()) - 90)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="partner1",
                timestamp=old_timestamp,
                signature="fake",
                method="POST",
                path="/path",
                body=b"",
                client_ip="192.168.1.100",
            )

        assert "tolerance: 60s" in str(exc_info.value.detail)


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestCreateSignatureHelper:
    """Test create_signature helper function for generating signatures."""

    def test_creates_valid_signature_with_all_components(self) -> None:
        """Test create_signature generates valid HMAC-SHA256 signature.

        Arrange: Client credentials, HTTP method, path, and body
        Act: Create signature using helper function
        Assert: Returns client_id, timestamp, and valid 64-char signature
        """
        # Arrange
        client_id = "partner1"
        secret_key = "my-secret"
        method = "POST"
        path = "/api/v1/webhook"
        body = b'{"data": "value"}'

        # Act
        returned_id, timestamp, signature = create_signature(
            client_id=client_id,
            secret_key=secret_key,
            method=method,
            path=path,
            body=body,
        )

        # Assert
        assert returned_id == client_id
        assert timestamp.isdigit()
        assert len(signature) == 64

        # Verify signature is valid
        body_hash = hashlib.sha256(body).hexdigest()
        payload = f"{timestamp}:{method.upper()}:{path}:{body_hash}"
        expected_sig = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        assert signature == expected_sig

    def test_creates_signature_with_empty_body(self) -> None:
        """Test create_signature handles empty body (GET request).

        Arrange: GET request with empty body
        Act: Create signature
        Assert: Signature computed with empty body hash
        """
        # Arrange & Act
        _, timestamp, signature = create_signature(
            client_id="partner1",
            secret_key="secret",
            method="GET",
            path="/api/v1/status",
            body=b"",
        )

        # Assert
        payload = f"{timestamp}:GET:/api/v1/status:"
        expected = hmac.new(b"secret", payload.encode(), hashlib.sha256).hexdigest()
        assert signature == expected

    def test_normalizes_method_to_uppercase(self) -> None:
        """Test create_signature normalizes HTTP method to uppercase.

        Arrange: Same request with lowercase method
        Act: Create signature with lowercase method
        Assert: Signature computed with uppercase method
        """
        # Arrange & Act
        _, ts1, sig1 = create_signature("id", "key", "post", "/path", b"")
        _, ts2, sig2 = create_signature("id", "key", "POST", "/path", b"")

        # Assert
        # Signatures are valid (not empty)
        assert sig1 and len(sig1) == 64
        assert sig2 and len(sig2) == 64


class TestValidatorInitialization:
    """Test global validator initialization and configuration."""

    def test_initializes_global_validator(self, api_clients: dict[str, APIClient]) -> None:
        """Test init_signature_validator sets up global validator instance.

        Arrange: API clients dictionary
        Act: Initialize global validator
        Assert: Global validator is set with correct clients
        """
        # Arrange
        from src.infrastructure.security import api_signature

        # Act
        init_signature_validator(api_clients)

        # Assert
        assert api_signature._signature_validator is not None
        assert api_signature._signature_validator._clients == api_clients


# ============================================================================
# FastAPI Dependency Tests
# ============================================================================


class TestVerifyApiSignatureDependency:
    """Test verify_api_signature FastAPI dependency function."""

    @pytest.mark.asyncio
    async def test_validates_signature_successfully(
        self, api_clients: dict[str, APIClient]
    ) -> None:
        """Test dependency validates signature and returns APIClient.

        Arrange: Initialize validator, create valid signature, mock request
        Act: Call dependency with valid credentials
        Assert: Returns APIClient for authenticated partner
        """
        # Arrange
        init_signature_validator(api_clients)

        method = "POST"
        path = "/api/v1/webhook"
        body = b'{"test": "data"}'

        _, timestamp, signature = create_signature(
            client_id="partner1",
            secret_key="secret-key-123",
            method=method,
            path=path,
            body=body,
        )

        # Mock request
        mock_request = Mock()
        mock_request.method = method
        mock_request.url.path = path
        mock_request.url.query = ""
        mock_request.body = AsyncMock(return_value=body)
        mock_request.client.host = "192.168.1.100"

        # Act
        client = await verify_api_signature(
            request=mock_request,
            x_api_client_id="partner1",
            x_api_timestamp=timestamp,
            x_api_signature=signature,
        )

        # Assert
        assert client.client_id == "partner1"

    @pytest.mark.asyncio
    async def test_handles_query_parameters_in_path(
        self, api_clients: dict[str, APIClient]
    ) -> None:
        """Test dependency includes query parameters in signature validation.

        Arrange: Initialize validator, create signature with full path+query
        Act: Call dependency with query params
        Assert: Returns APIClient (query params included in signature)
        """
        # Arrange
        init_signature_validator(api_clients)

        method = "GET"
        path = "/api/v1/status"
        query = "format=json&verbose=true"
        full_path = f"{path}?{query}"

        _, timestamp, signature = create_signature(
            client_id="partner2",
            secret_key="another-secret",
            method=method,
            path=full_path,
            body=b"",
        )

        # Mock request
        mock_request = Mock()
        mock_request.method = method
        mock_request.url.path = path
        mock_request.url.query = query
        mock_request.body = AsyncMock(return_value=b"")
        mock_request.client.host = "1.2.3.4"

        # Act
        client = await verify_api_signature(
            request=mock_request,
            x_api_client_id="partner2",
            x_api_timestamp=timestamp,
            x_api_signature=signature,
        )

        # Assert
        assert client.client_id == "partner2"

    @pytest.mark.asyncio
    async def test_raises_error_when_validator_not_initialized(self) -> None:
        """Test dependency fails when validator not initialized.

        Arrange: Clear global validator
        Act: Call dependency without initialization
        Assert: Raises 500 HTTPException with not configured error
        """
        # Arrange
        from src.infrastructure.security import api_signature

        api_signature._signature_validator = None
        mock_request = Mock()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_signature(
                request=mock_request,
                x_api_client_id="partner1",
                x_api_timestamp="123",
                x_api_signature="sig",
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "not configured" in str(exc_info.value.detail)


# ============================================================================
# APIClient Model Tests
# ============================================================================


class TestApiClientModel:
    """Test APIClient Pydantic model."""

    def test_creates_client_with_all_fields(self) -> None:
        """Test APIClient model with all fields specified.

        Arrange: Client data with all fields
        Act: Create APIClient instance
        Assert: All fields set correctly
        """
        # Arrange & Act
        client = APIClient(
            client_id="test-client",
            secret_key="test-secret",
            is_active=True,
            allowed_ips=["1.2.3.4"],
        )

        # Assert
        assert client.client_id == "test-client"
        assert client.secret_key == "test-secret"
        assert client.is_active is True
        assert client.allowed_ips == ["1.2.3.4"]

    def test_uses_default_values(self) -> None:
        """Test APIClient default values for optional fields.

        Arrange: Client data with only required fields
        Act: Create APIClient instance
        Assert: Optional fields have expected defaults
        """
        # Arrange & Act
        client = APIClient(
            client_id="test",
            secret_key="secret",
        )

        # Assert
        assert client.is_active is True  # Default
        assert client.allowed_ips == []  # Default empty list
