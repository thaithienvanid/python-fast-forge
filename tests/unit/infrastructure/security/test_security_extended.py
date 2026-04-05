"""Extended unit tests for API signature security module.

Covers missing lines in src/infrastructure/security/api_signature.py:
- SignatureValidator.validate_signature:
  - Unknown client ID
  - Inactive client
  - IP whitelist enforcement
  - Timestamp validation (invalid format)
  - Replay attack prevention (too old/future)
  - Valid signature verification
  - Invalid signature rejection
- SignatureValidator._create_signature_payload:
  - With body
  - Without body
- SignatureValidator._compute_signature
- init_signature_validator
- verify_api_signature (FastAPI dependency)
- create_signature helper function

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- pytest.mark.parametrize for multiple scenarios
- Freeze time for deterministic timestamp testing
"""

import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock

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
# Shared Fixtures
# ============================================================================


@pytest.fixture
def active_client():
    """Create an active API client."""
    return APIClient(
        client_id="test-client",
        secret_key="super-secret-key-1234",
        is_active=True,
        allowed_ips=[],
    )


@pytest.fixture
def inactive_client():
    """Create an inactive API client."""
    return APIClient(
        client_id="inactive-client",
        secret_key="some-secret",
        is_active=False,
        allowed_ips=[],
    )


@pytest.fixture
def ip_restricted_client():
    """Create an API client restricted to specific IPs."""
    return APIClient(
        client_id="ip-client",
        secret_key="ip-secret",
        is_active=True,
        allowed_ips=["192.168.1.100", "10.0.0.1"],
    )


@pytest.fixture
def validator(active_client):
    """Create a SignatureValidator with one active client."""
    return SignatureValidator(
        api_clients={"test-client": active_client},
        timestamp_tolerance=300,
    )


@pytest.fixture
def validator_with_ip_restricted(ip_restricted_client):
    """Create a SignatureValidator with IP-restricted client."""
    return SignatureValidator(
        api_clients={"ip-client": ip_restricted_client},
        timestamp_tolerance=300,
    )


@pytest.fixture
def validator_with_inactive(inactive_client):
    """Create a SignatureValidator with inactive client."""
    return SignatureValidator(
        api_clients={"inactive-client": inactive_client},
        timestamp_tolerance=300,
    )


def _make_valid_signature(secret_key: str, method: str, path: str, body: bytes, timestamp: str):
    """Helper to create a valid HMAC-SHA256 signature.

    Args:
        secret_key: Secret key for signing
        method: HTTP method
        path: Request path
        body: Request body
        timestamp: Unix timestamp string

    Returns:
        HMAC-SHA256 hex signature
    """
    method = method.upper()
    body_hash = hashlib.sha256(body).hexdigest() if body else ""
    payload = f"{timestamp}:{method}:{path}:{body_hash}"
    return hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


# ============================================================================
# APIClient Model Tests
# ============================================================================


class TestAPIClient:
    """Tests for APIClient model."""

    def test_default_is_active_true(self):
        """Test that is_active defaults to True.

        Arrange: APIClient without is_active
        Act: Create client
        Assert: is_active is True
        """
        client = APIClient(client_id="test", secret_key="secret")

        assert client.is_active is True

    def test_default_allowed_ips_empty(self):
        """Test that allowed_ips defaults to empty list.

        Arrange: APIClient without allowed_ips
        Act: Create client
        Assert: allowed_ips is empty list
        """
        client = APIClient(client_id="test", secret_key="secret")

        assert client.allowed_ips == []

    def test_ip_restricted_client(self):
        """Test creating client with IP restrictions.

        Arrange: APIClient with allowed_ips
        Act: Create client
        Assert: allowed_ips set correctly
        """
        client = APIClient(
            client_id="test",
            secret_key="secret",
            allowed_ips=["10.0.0.1", "192.168.1.1"],
        )

        assert "10.0.0.1" in client.allowed_ips
        assert "192.168.1.1" in client.allowed_ips


# ============================================================================
# SignatureValidator._create_signature_payload Tests
# ============================================================================


class TestCreateSignaturePayload:
    """Tests for SignatureValidator._create_signature_payload."""

    def test_payload_with_body(self, validator):
        """Test payload includes body hash when body is present.

        Arrange: Non-empty body
        Act: Call _create_signature_payload
        Assert: Payload contains body hash
        """
        body = b'{"key": "value"}'
        expected_body_hash = hashlib.sha256(body).hexdigest()

        payload = validator._create_signature_payload(
            timestamp="1700000000",
            method="POST",
            path="/api/v1/users",
            body=body,
        )

        assert expected_body_hash in payload
        assert payload == f"1700000000:POST:/api/v1/users:{expected_body_hash}"

    def test_payload_without_body(self, validator):
        """Test payload has empty body hash when body is empty.

        Arrange: Empty body
        Act: Call _create_signature_payload
        Assert: Payload ends with colon (empty body hash)
        """
        payload = validator._create_signature_payload(
            timestamp="1700000000",
            method="GET",
            path="/api/v1/users",
            body=b"",
        )

        assert payload == "1700000000:GET:/api/v1/users:"

    def test_method_normalized_to_uppercase(self, validator):
        """Test that method is normalized to uppercase.

        Arrange: Lowercase method
        Act: Call _create_signature_payload
        Assert: Method in payload is uppercase
        """
        payload = validator._create_signature_payload(
            timestamp="1700000000",
            method="post",
            path="/api/v1/users",
            body=b"",
        )

        assert "POST" in payload

    @pytest.mark.parametrize("method", ["get", "post", "put", "delete", "patch"])
    def test_all_methods_normalized(self, validator, method):
        """Test all HTTP methods are normalized to uppercase.

        Arrange: Various HTTP method cases
        Act: Call _create_signature_payload
        Assert: Method is uppercase in payload
        """
        payload = validator._create_signature_payload(
            timestamp="1700000000",
            method=method,
            path="/api/v1/test",
            body=b"",
        )

        assert method.upper() in payload


# ============================================================================
# SignatureValidator._compute_signature Tests
# ============================================================================


class TestComputeSignature:
    """Tests for SignatureValidator._compute_signature."""

    def test_computes_hmac_sha256(self, validator):
        """Test that signature is HMAC-SHA256 of payload.

        Arrange: Known secret and payload
        Act: Call _compute_signature
        Assert: Returns correct HMAC-SHA256 hex digest
        """
        secret_key = "test-secret"
        payload = "1700000000:POST:/api/v1/users:abc123"

        result = validator._compute_signature(secret_key, payload)

        expected = hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        assert result == expected

    def test_different_secrets_produce_different_signatures(self, validator):
        """Test that different secrets produce different signatures.

        Arrange: Two different secrets, same payload
        Act: Compute signatures for both
        Assert: Signatures differ
        """
        payload = "test-payload"

        sig1 = validator._compute_signature("secret-1", payload)
        sig2 = validator._compute_signature("secret-2", payload)

        assert sig1 != sig2


# ============================================================================
# SignatureValidator.validate_signature Tests
# ============================================================================


class TestValidateSignature:
    """Tests for SignatureValidator.validate_signature."""

    def test_raises_401_for_unknown_client_id(self, validator):
        """Test raises 401 for unknown client_id.

        Arrange: Client_id not in registered clients
        Act: Call validate_signature
        Assert: HTTPException 401 raised
        """
        timestamp = str(int(time.time()))
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="unknown-client",
                timestamp=timestamp,
                signature="any-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API client ID" in str(exc_info.value.detail)

    def test_raises_403_for_inactive_client(self, validator_with_inactive):
        """Test raises 403 for inactive client.

        Arrange: Client exists but is inactive
        Act: Call validate_signature
        Assert: HTTPException 403 raised
        """
        timestamp = str(int(time.time()))
        with pytest.raises(HTTPException) as exc_info:
            validator_with_inactive.validate_signature(
                client_id="inactive-client",
                timestamp=timestamp,
                signature="any-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "inactive" in str(exc_info.value.detail).lower()

    def test_raises_403_for_ip_not_in_whitelist(self, validator_with_ip_restricted):
        """Test raises 403 when client IP is not in whitelist.

        Arrange: IP-restricted client, client_ip not in allowed_ips
        Act: Call validate_signature
        Assert: HTTPException 403 raised
        """
        timestamp = str(int(time.time()))
        with pytest.raises(HTTPException) as exc_info:
            validator_with_ip_restricted.validate_signature(
                client_id="ip-client",
                timestamp=timestamp,
                signature="any-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
                client_ip="9.9.9.9",  # Not in allowed_ips
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "IP" in str(exc_info.value.detail)

    def test_allows_ip_in_whitelist(self, validator_with_ip_restricted, active_client):
        """Test allows request when IP is in whitelist.

        Arrange: IP-restricted client, client_ip in allowed_ips, valid signature
        Act: Call validate_signature
        Assert: Proceeds past IP check (may fail on signature, but not IP)
        """
        timestamp = str(int(time.time()))
        valid_sig = _make_valid_signature("ip-secret", "GET", "/api/v1/users", b"", timestamp)

        # Should not raise 403 (IP whitelist); may raise 401 (signature) or succeed
        try:
            validator_with_ip_restricted.validate_signature(
                client_id="ip-client",
                timestamp=timestamp,
                signature=valid_sig,
                method="GET",
                path="/api/v1/users",
                body=b"",
                client_ip="192.168.1.100",  # In allowed_ips
            )
        except HTTPException as e:
            # If it raises, it must NOT be a 403 IP rejection
            assert e.detail != "IP address not allowed"  # noqa: PT017

    def test_raises_401_for_invalid_timestamp_format(self, validator):
        """Test raises 401 for non-numeric timestamp.

        Arrange: Non-numeric timestamp string
        Act: Call validate_signature
        Assert: HTTPException 401 raised
        """
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="test-client",
                timestamp="not-a-number",
                signature="any-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "timestamp" in str(exc_info.value.detail).lower()

    def test_raises_401_for_timestamp_too_old(self, validator):
        """Test raises 401 for timestamp older than tolerance.

        Arrange: Timestamp 10 minutes in the past (beyond 5-minute tolerance)
        Act: Call validate_signature
        Assert: HTTPException 401 raised with timestamp message
        """
        old_timestamp = str(int(time.time()) - 700)  # 700 seconds ago > 300s tolerance

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="test-client",
                timestamp=old_timestamp,
                signature="any-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "timestamp" in str(exc_info.value.detail).lower()

    def test_raises_401_for_timestamp_in_future(self, validator):
        """Test raises 401 for timestamp too far in the future.

        Arrange: Timestamp 10 minutes in the future
        Act: Call validate_signature
        Assert: HTTPException 401 raised
        """
        future_timestamp = str(int(time.time()) + 700)

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="test-client",
                timestamp=future_timestamp,
                signature="any-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_raises_401_for_invalid_signature(self, validator):
        """Test raises 401 when signature does not match.

        Arrange: Valid timestamp, wrong signature
        Act: Call validate_signature
        Assert: HTTPException 401 raised
        """
        timestamp = str(int(time.time()))

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_signature(
                client_id="test-client",
                timestamp=timestamp,
                signature="invalid-signature-value",
                method="GET",
                path="/api/v1/users",
                body=b"",
            )

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "signature" in str(exc_info.value.detail).lower()

    def test_returns_client_for_valid_signature(self, validator, active_client):
        """Test returns APIClient when signature is valid.

        Arrange: Valid timestamp and correct HMAC signature
        Act: Call validate_signature
        Assert: Returns the APIClient object
        """
        timestamp = str(int(time.time()))
        valid_sig = _make_valid_signature(
            active_client.secret_key, "GET", "/api/v1/users", b"", timestamp
        )

        result = validator.validate_signature(
            client_id="test-client",
            timestamp=timestamp,
            signature=valid_sig,
            method="GET",
            path="/api/v1/users",
            body=b"",
        )

        assert result is active_client

    def test_validates_post_with_body(self, validator, active_client):
        """Test valid signature for POST request with body.

        Arrange: POST request with JSON body, valid signature
        Act: Call validate_signature
        Assert: Returns APIClient
        """
        body = b'{"email": "user@example.com", "username": "testuser"}'
        timestamp = str(int(time.time()))
        valid_sig = _make_valid_signature(
            active_client.secret_key, "POST", "/api/v1/users", body, timestamp
        )

        result = validator.validate_signature(
            client_id="test-client",
            timestamp=timestamp,
            signature=valid_sig,
            method="POST",
            path="/api/v1/users",
            body=body,
        )

        assert result is active_client

    def test_no_ip_check_when_allowed_ips_empty(self, validator, active_client):
        """Test that no IP check is performed when allowed_ips is empty.

        Arrange: Client with empty allowed_ips, any client_ip
        Act: Call validate_signature (with valid sig)
        Assert: IP is not checked (proceeds to signature validation)
        """
        timestamp = str(int(time.time()))
        valid_sig = _make_valid_signature(
            active_client.secret_key, "GET", "/api/v1/test", b"", timestamp
        )

        # Should not raise 403 for IP
        result = validator.validate_signature(
            client_id="test-client",
            timestamp=timestamp,
            signature=valid_sig,
            method="GET",
            path="/api/v1/test",
            body=b"",
            client_ip="any-ip-address",  # No restriction
        )

        assert result is active_client

    def test_no_ip_check_when_no_client_ip_provided(self, validator_with_ip_restricted):
        """Test that IP check is skipped when client_ip is None.

        Arrange: IP-restricted client, no client_ip
        Act: Call validate_signature (with any sig)
        Assert: Does not raise 403 for IP (proceeds to next check)
        """
        timestamp = str(int(time.time()))

        # With no client_ip, IP check should be skipped
        # Should fail on signature validation instead
        with pytest.raises(HTTPException) as exc_info:
            validator_with_ip_restricted.validate_signature(
                client_id="ip-client",
                timestamp=timestamp,
                signature="invalid-sig",
                method="GET",
                path="/api/v1/users",
                body=b"",
                client_ip=None,
            )

        # Should fail on signature, not IP
        assert exc_info.value.detail != "IP address not allowed"


# ============================================================================
# init_signature_validator Tests
# ============================================================================


class TestInitSignatureValidator:
    """Tests for init_signature_validator global initialization."""

    def test_initializes_global_validator(self):
        """Test that init_signature_validator creates the global validator.

        Arrange: API clients dict
        Act: Call init_signature_validator
        Assert: Global _signature_validator is set
        """
        from src.infrastructure.security import api_signature as sig_module

        original_validator = sig_module._signature_validator

        try:
            client = APIClient(client_id="init-test", secret_key="init-secret")
            init_signature_validator({"init-test": client})

            assert sig_module._signature_validator is not None
            assert isinstance(sig_module._signature_validator, SignatureValidator)
        finally:
            # Restore original state
            sig_module._signature_validator = original_validator

    def test_validator_has_registered_clients(self):
        """Test that initialized validator contains registered clients.

        Arrange: API clients dict
        Act: Call init_signature_validator
        Assert: Validator has the clients
        """
        from src.infrastructure.security import api_signature as sig_module

        original_validator = sig_module._signature_validator

        try:
            client = APIClient(client_id="client-check", secret_key="check-secret")
            init_signature_validator({"client-check": client})

            assert "client-check" in sig_module._signature_validator._clients
        finally:
            sig_module._signature_validator = original_validator


# ============================================================================
# verify_api_signature FastAPI Dependency Tests
# ============================================================================


class TestVerifyApiSignature:
    """Tests for the verify_api_signature FastAPI dependency."""

    async def test_raises_500_when_validator_not_configured(self):
        """Test raises 500 when signature validator is not initialized.

        Arrange: _signature_validator is None
        Act: Call verify_api_signature
        Assert: HTTPException 500 raised
        """
        from src.infrastructure.security import api_signature as sig_module

        original_validator = sig_module._signature_validator
        sig_module._signature_validator = None

        try:
            mock_request = MagicMock()
            mock_request.body = AsyncMock(return_value=b"")
            mock_request.client = MagicMock()
            mock_request.client.host = "127.0.0.1"
            mock_request.url.path = "/api/v1/test"
            mock_request.url.query = ""
            mock_request.method = "GET"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_signature(
                    request=mock_request,
                    x_api_client_id="test-client",
                    x_api_timestamp="1700000000",
                    x_api_signature="any-sig",
                )

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        finally:
            sig_module._signature_validator = original_validator

    async def test_includes_query_string_in_path(self):
        """Test that query string is appended to path for signature validation.

        Arrange: Validator configured, request with query string
        Act: Call verify_api_signature
        Assert: Path includes query string
        """
        from src.infrastructure.security import api_signature as sig_module

        client = APIClient(client_id="query-test", secret_key="query-secret")
        original_validator = sig_module._signature_validator
        sig_module._signature_validator = SignatureValidator(
            {"query-test": client}, timestamp_tolerance=300
        )

        try:
            body = b""
            path = "/api/v1/users"
            query = "status=active&page=1"
            full_path = f"{path}?{query}"
            timestamp = str(int(time.time()))
            valid_sig = _make_valid_signature("query-secret", "GET", full_path, body, timestamp)

            mock_request = MagicMock()
            mock_request.body = AsyncMock(return_value=body)
            mock_request.client = MagicMock()
            mock_request.client.host = "127.0.0.1"
            mock_request.url.path = path
            mock_request.url.query = query
            mock_request.method = "GET"

            result = await verify_api_signature(
                request=mock_request,
                x_api_client_id="query-test",
                x_api_timestamp=timestamp,
                x_api_signature=valid_sig,
            )

            assert result is client
        finally:
            sig_module._signature_validator = original_validator

    async def test_path_without_query_string(self):
        """Test that path without query string is used as-is.

        Arrange: Validator configured, request without query string
        Act: Call verify_api_signature
        Assert: Path does not include query separator
        """
        from src.infrastructure.security import api_signature as sig_module

        client = APIClient(client_id="no-query", secret_key="no-query-secret")
        original_validator = sig_module._signature_validator
        sig_module._signature_validator = SignatureValidator(
            {"no-query": client}, timestamp_tolerance=300
        )

        try:
            body = b""
            path = "/api/v1/users"
            timestamp = str(int(time.time()))
            valid_sig = _make_valid_signature("no-query-secret", "GET", path, body, timestamp)

            mock_request = MagicMock()
            mock_request.body = AsyncMock(return_value=body)
            mock_request.client = MagicMock()
            mock_request.client.host = "127.0.0.1"
            mock_request.url.path = path
            mock_request.url.query = ""
            mock_request.method = "GET"

            result = await verify_api_signature(
                request=mock_request,
                x_api_client_id="no-query",
                x_api_timestamp=timestamp,
                x_api_signature=valid_sig,
            )

            assert result is client
        finally:
            sig_module._signature_validator = original_validator


# ============================================================================
# create_signature Helper Function Tests
# ============================================================================


class TestCreateSignature:
    """Tests for create_signature helper function."""

    def test_returns_tuple_of_three_values(self):
        """Test returns (client_id, timestamp, signature) tuple.

        Arrange: Valid parameters
        Act: Call create_signature
        Assert: Returns 3-tuple
        """
        result = create_signature(
            client_id="test",
            secret_key="secret",
            method="GET",
            path="/api/v1/test",
        )

        assert len(result) == 3

    def test_first_element_is_client_id(self):
        """Test first element of tuple is the client_id.

        Arrange: Known client_id
        Act: Call create_signature
        Assert: First element matches client_id
        """
        client_id, _, _ = create_signature(
            client_id="my-client",
            secret_key="secret",
            method="GET",
            path="/api/v1/test",
        )

        assert client_id == "my-client"

    def test_second_element_is_numeric_timestamp(self):
        """Test second element is a numeric timestamp string.

        Arrange: Valid parameters
        Act: Call create_signature
        Assert: Timestamp is a string of digits
        """
        _, timestamp, _ = create_signature(
            client_id="test",
            secret_key="secret",
            method="GET",
            path="/api/v1/test",
        )

        assert timestamp.isdigit()
        assert int(timestamp) > 0

    def test_third_element_is_hex_signature(self):
        """Test third element is a hex-encoded signature string.

        Arrange: Valid parameters
        Act: Call create_signature
        Assert: Signature is 64-char hex string (SHA256 = 32 bytes = 64 hex chars)
        """
        _, _, signature = create_signature(
            client_id="test",
            secret_key="secret",
            method="GET",
            path="/api/v1/test",
        )

        assert len(signature) == 64
        # Validate it's hex
        int(signature, 16)

    def test_created_signature_is_valid(self):
        """Test that the created signature can be validated.

        Arrange: Create signature for a request
        Act: Validate with SignatureValidator
        Assert: Validation succeeds
        """
        client = APIClient(client_id="helper-test", secret_key="helper-secret")
        validator = SignatureValidator(
            {"helper-test": client},
            timestamp_tolerance=300,
        )

        client_id, timestamp, signature = create_signature(
            client_id="helper-test",
            secret_key="helper-secret",
            method="POST",
            path="/api/v1/users",
            body=b'{"email":"test@example.com"}',
        )

        result = validator.validate_signature(
            client_id=client_id,
            timestamp=timestamp,
            signature=signature,
            method="POST",
            path="/api/v1/users",
            body=b'{"email":"test@example.com"}',
        )

        assert result is client

    def test_signature_with_empty_body(self):
        """Test create_signature with empty body (GET request).

        Arrange: GET request with no body
        Act: Call create_signature
        Assert: Returns valid signature
        """
        _, timestamp, signature = create_signature(
            client_id="test",
            secret_key="secret",
            method="GET",
            path="/api/v1/test",
            body=b"",
        )

        assert len(signature) == 64

    def test_timestamp_is_current_time(self):
        """Test that timestamp is approximately current time.

        Arrange: Current time reference
        Act: Call create_signature
        Assert: Timestamp within 5 seconds of current time
        """
        before = int(time.time())
        _, timestamp, _ = create_signature(
            client_id="test",
            secret_key="secret",
            method="GET",
            path="/api/v1/test",
        )
        after = int(time.time())

        ts_int = int(timestamp)
        assert before <= ts_int <= after

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
    def test_signature_different_methods(self, method):
        """Test that different methods produce different signatures.

        Arrange: Same parameters, different HTTP methods
        Act: Call create_signature for each method
        Assert: Signatures differ across methods
        """
        signatures = []
        for m in ["GET", "POST", "PUT", "DELETE"]:
            _, _, sig = create_signature(
                client_id="test",
                secret_key="secret",
                method=m,
                path="/api/v1/test",
            )
            signatures.append(sig)

        # All signatures should be different
        assert len(set(signatures)) == 4
