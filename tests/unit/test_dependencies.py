"""Tests for API dependencies.

Test Organization:
- TestGetTenantIdWithNoToken: No token provided scenarios
- TestGetTenantIdWithValidToken: Valid JWT token scenarios
- TestGetTenantIdWithInvalidToken: Invalid/expired/malformed token scenarios
- TestGetTenantIdLogging: Logging behavior verification
- TestGetTenantIdEdgeCases: Edge cases and boundary conditions
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from authlib.jose import JsonWebToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from src.infrastructure.config import Settings
from src.presentation.api.dependencies import get_tenant_id
from src.utils.tenant_auth import create_tenant_token


# ============================================================================
# Test Helpers
# ============================================================================


def _generate_wrong_ec_private_key() -> str:
    """Generate a different EC private key for invalid signature tests."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


# ============================================================================
# No Token Tests
# ============================================================================


class TestGetTenantIdWithNoToken:
    """Test get_tenant_id when no token is provided."""

    @pytest.mark.asyncio
    async def test_returns_none_when_token_is_none(self) -> None:
        """Test get_tenant_id returns None when token is None.

        Arrange: x_tenant_token=None
        Act: Call get_tenant_id
        Assert: Returns None
        """
        # Arrange
        x_tenant_token = None

        # Act
        result = await get_tenant_id(x_tenant_token=x_tenant_token)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_token_not_provided(self) -> None:
        """Test get_tenant_id returns None when token parameter omitted.

        Arrange: No token parameter
        Act: Call get_tenant_id without argument
        Assert: Returns None
        """
        # Arrange & Act
        result = await get_tenant_id()

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_token_is_empty_string(self) -> None:
        """Test get_tenant_id returns None for empty string token.

        Arrange: x_tenant_token="" (empty string is falsy)
        Act: Call get_tenant_id
        Assert: Returns None
        """
        # Arrange
        x_tenant_token = ""

        # Act
        result = await get_tenant_id(x_tenant_token=x_tenant_token)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_explicit_none_and_missing_behave_identically(self) -> None:
        """Test explicit None and missing parameter produce same result.

        Arrange: None
        Act: Call get_tenant_id with and without None parameter
        Assert: Both return None
        """
        # Arrange & Act
        result_explicit_none = await get_tenant_id(x_tenant_token=None)
        result_missing = await get_tenant_id()

        # Assert
        assert result_explicit_none is None
        assert result_missing is None
        assert result_explicit_none == result_missing


# ============================================================================
# Valid Token Tests
# ============================================================================


class TestGetTenantIdWithValidToken:
    """Test get_tenant_id with valid JWT tokens."""

    @pytest.mark.asyncio
    async def test_extracts_tenant_id_from_valid_token(self) -> None:
        """Test get_tenant_id extracts tenant_id from valid JWT token.

        Arrange: Valid JWT token with tenant_id
        Act: Call get_tenant_id with token
        Assert: Returns correct tenant UUID
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act
        result = await get_tenant_id(x_tenant_token=token)

        # Assert
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_accepts_token_with_custom_expiration(self) -> None:
        """Test get_tenant_id accepts token with custom expiration.

        Arrange: Token with 1 hour expiration
        Act: Call get_tenant_id with token
        Assert: Returns correct tenant UUID
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id, expires_delta=timedelta(hours=1))

        # Act
        result = await get_tenant_id(x_tenant_token=token)

        # Assert
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_validates_multiple_different_tokens(self) -> None:
        """Test get_tenant_id validates multiple different tokens.

        Arrange: Multiple tokens with different tenant IDs
        Act: Call get_tenant_id for each token
        Assert: Returns correct tenant UUID for each
        """
        # Arrange
        tenant_ids = [uuid4() for _ in range(3)]
        tokens = [create_tenant_token(tid) for tid in tenant_ids]

        # Act & Assert
        for tenant_id, token in zip(tenant_ids, tokens, strict=False):
            result = await get_tenant_id(x_tenant_token=token)
            assert result == tenant_id


# ============================================================================
# Invalid Token Tests
# ============================================================================


class TestGetTenantIdWithInvalidToken:
    """Test get_tenant_id with invalid JWT tokens."""

    @pytest.mark.asyncio
    async def test_raises_401_for_expired_token(self) -> None:
        """Test get_tenant_id raises 401 for expired token.

        Arrange: Expired JWT token
        Act: Call get_tenant_id with expired token
        Assert: Raises HTTPException with status 401
        """
        # Arrange - Create expired token
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id, expires_delta=timedelta(seconds=-1))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "TENANT_TOKEN_EXPIRED"
        assert "expired" in exc_info.value.detail["message"].lower()

    @pytest.mark.asyncio
    async def test_raises_401_for_invalid_signature(self) -> None:
        """Test get_tenant_id raises 401 for invalid signature.

        Arrange: Token with tampered signature
        Act: Call get_tenant_id with invalid token
        Assert: Raises HTTPException with status 401
        """
        # Arrange - Create token with different EC private key
        tenant_id = uuid4()
        settings = Settings()
        payload = {
            "tenant_id": str(tenant_id),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "iat": datetime.now(UTC),
        }
        # Create token with wrong EC private key
        wrong_key = _generate_wrong_ec_private_key()
        jwt_instance = JsonWebToken([settings.jwt_algorithm])
        header = {"alg": settings.jwt_algorithm}
        token_bytes = jwt_instance.encode(header, payload, wrong_key)
        token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "TENANT_TOKEN_INVALID_SIGNATURE"
        assert "signature" in exc_info.value.detail["message"].lower()

    @pytest.mark.asyncio
    async def test_raises_401_for_malformed_token(self) -> None:
        """Test get_tenant_id raises 401 for malformed token.

        Arrange: Malformed JWT string
        Act: Call get_tenant_id with malformed token
        Assert: Raises HTTPException with status 401
        """
        # Arrange
        token = "not.a.valid.jwt.token"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "TENANT_TOKEN_MALFORMED"
        assert "malformed" in exc_info.value.detail["message"].lower()

    @pytest.mark.asyncio
    async def test_raises_401_for_token_without_tenant_id(self) -> None:
        """Test get_tenant_id raises 401 for token without tenant_id claim.

        Arrange: Valid JWT token but missing tenant_id claim
        Act: Call get_tenant_id with token
        Assert: Raises HTTPException with status 401
        """
        # Arrange - Create token without tenant_id using same settings instance
        settings = Settings()
        payload = {
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "iat": datetime.now(UTC),
        }
        private_key = settings.get_jwt_private_key()
        jwt_instance = JsonWebToken([settings.jwt_algorithm])
        header = {"alg": settings.jwt_algorithm}
        token_bytes = jwt_instance.encode(header, payload, private_key)
        token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes

        # Act & Assert - Pass same settings instance
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token, settings=settings)

        assert exc_info.value.status_code == 401
        # Missing tenant_id is a claims validation error
        assert exc_info.value.detail["code"] == "TENANT_TOKEN_INVALID_CLAIMS"

    @pytest.mark.asyncio
    async def test_raises_401_for_invalid_uuid_in_tenant_id(self) -> None:
        """Test get_tenant_id raises 401 for invalid UUID in tenant_id claim.

        Arrange: JWT token with invalid UUID string in tenant_id
        Act: Call get_tenant_id with token
        Assert: Raises HTTPException with status 401
        """
        # Arrange - Create token with invalid UUID using same settings instance
        settings = Settings()
        payload = {
            "tenant_id": "not-a-valid-uuid",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "iat": datetime.now(UTC),
        }
        private_key = settings.get_jwt_private_key()
        jwt_instance = JsonWebToken([settings.jwt_algorithm])
        header = {"alg": settings.jwt_algorithm}
        token_bytes = jwt_instance.encode(header, payload, private_key)
        token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes

        # Act & Assert - Pass same settings instance
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token, settings=settings)

        assert exc_info.value.status_code == 401
        # Invalid UUID format is a claims validation error
        assert exc_info.value.detail["code"] == "TENANT_TOKEN_INVALID_CLAIMS"

    @pytest.mark.asyncio
    async def test_raises_401_for_simple_string_token(self) -> None:
        """Test get_tenant_id raises 401 for simple string token.

        Arrange: Simple string (not JWT format)
        Act: Call get_tenant_id with token
        Assert: Raises HTTPException with status 401
        """
        # Arrange
        token = "simple-token-string"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401


# ============================================================================
# Logging Tests
# ============================================================================


class TestGetTenantIdLogging:
    """Test logging behavior of get_tenant_id."""

    @pytest.mark.asyncio
    async def test_logs_debug_when_no_token_provided(self) -> None:
        """Test debug log when no token provided.

        Arrange: No token
        Act: Call get_tenant_id
        Assert: Logs debug message about no tenant isolation
        """
        # Arrange & Act
        with patch("src.presentation.api.dependencies.logger") as mock_logger:
            result = await get_tenant_id(x_tenant_token=None)

        # Assert
        assert result is None
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args
        assert "no_tenant_isolation" in call_args[0]

    @pytest.mark.asyncio
    async def test_logs_debug_when_valid_token_provided(self) -> None:
        """Test debug log when valid token provided.

        Arrange: Valid JWT token
        Act: Call get_tenant_id
        Assert: Logs debug message about successful extraction
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act
        with patch("src.presentation.api.dependencies.logger") as mock_logger:
            result = await get_tenant_id(x_tenant_token=token)

        # Assert
        assert result == tenant_id
        mock_logger.debug.assert_called()
        # Check that debug was called with tenant_id_extracted
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        assert "tenant_id_extracted" in debug_calls

    @pytest.mark.asyncio
    async def test_logs_warning_when_token_expired(self) -> None:
        """Test warning log when token expired.

        Arrange: Expired JWT token
        Act: Call get_tenant_id
        Assert: Logs warning about expired token
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id, expires_delta=timedelta(seconds=-1))

        # Act & Assert
        with (
            patch("src.presentation.api.dependencies.logger") as mock_logger,
            pytest.raises(HTTPException),
        ):
            await get_tenant_id(x_tenant_token=token)

        mock_logger.warning.assert_called()
        call_args = mock_logger.warning.call_args[0]
        assert "tenant_token_expired" in call_args

    @pytest.mark.asyncio
    async def test_logs_error_for_unexpected_exceptions(self) -> None:
        """Test error log for unexpected exceptions.

        Arrange: Mock jwt.decode to raise unexpected exception
        Act: Call get_tenant_id
        Assert: Logs error with exception details
        """
        # Arrange
        token = "test-token"

        # Act & Assert
        with (
            patch("src.presentation.api.dependencies.logger") as mock_logger,
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=RuntimeError("Unexpected error"),
            ),
            pytest.raises(HTTPException),
        ):
            await get_tenant_id(x_tenant_token=token)

        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args
        assert "tenant_token_validation_failed" in call_args[0]


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestGetTenantIdEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_handles_very_long_token(self) -> None:
        """Test handling of very long JWT token.

        Arrange: Valid but very long token (with large payload)
        Act: Call get_tenant_id
        Assert: Returns correct tenant UUID or raises appropriate error
        """
        # Arrange - Create token with large payload using same settings instance
        tenant_id = uuid4()
        settings = Settings()
        payload = {
            "tenant_id": str(tenant_id),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "iat": datetime.now(UTC),
            "extra_data": "x" * 10000,  # Large extra claim
        }
        private_key = settings.get_jwt_private_key()
        jwt_instance = JsonWebToken([settings.jwt_algorithm])
        header = {"alg": settings.jwt_algorithm}
        token_bytes = jwt_instance.encode(header, payload, private_key)
        token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes

        # Act - Pass same settings instance
        result = await get_tenant_id(x_tenant_token=token, settings=settings)

        # Assert
        assert result == tenant_id

    @pytest.mark.asyncio
    async def test_handles_whitespace_token(self) -> None:
        """Test whitespace-only token raises appropriate error.

        Arrange: Whitespace-only token
        Act: Call get_tenant_id
        Assert: Raises 401 (whitespace is truthy but invalid JWT)
        """
        # Arrange
        token = "   "  # Whitespace is truthy

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_handles_unicode_in_token(self) -> None:
        """Test token with unicode characters.

        Arrange: Token string with unicode characters
        Act: Call get_tenant_id
        Assert: Raises 401 for malformed token
        """
        # Arrange
        token = "eyJhbGc.🔒🔑.signature"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_handles_token_with_special_characters(self) -> None:
        """Test token with special characters.

        Arrange: Token with special/control characters
        Act: Call get_tenant_id
        Assert: Raises 401 for malformed token
        """
        # Arrange
        token = "token\x00with\nnull\rand\tspecial\bchars"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401


# ============================================================================
# HTTP Exception Details Tests
# ============================================================================


class TestGetTenantIdHTTPExceptionDetails:
    """Test HTTP exception status codes and details."""

    @pytest.mark.asyncio
    async def test_expired_token_returns_401_not_403(self) -> None:
        """Test expired token returns 401, not 403.

        Arrange: Expired token
        Act: Call get_tenant_id
        Assert: Returns 401 Unauthorized (not 403 Forbidden)
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id, expires_delta=timedelta(seconds=-1))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401  # Not 403

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self) -> None:
        """Test invalid signature returns 401.

        Arrange: Token with invalid signature
        Act: Call get_tenant_id
        Assert: Returns 401 Unauthorized
        """
        # Arrange
        tenant_id = uuid4()
        settings = Settings()
        payload = {
            "tenant_id": str(tenant_id),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        }
        # Create token with wrong EC private key
        wrong_key = _generate_wrong_ec_private_key()
        jwt_instance = JsonWebToken([settings.jwt_algorithm])
        header = {"alg": settings.jwt_algorithm}
        token_bytes = jwt_instance.encode(header, payload, wrong_key)
        token = token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_id(x_tenant_token=token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_error_detail_is_user_friendly(self) -> None:
        """Test error details are user-friendly.

        Arrange: Various invalid tokens
        Act: Call get_tenant_id
        Assert: Error details don't expose sensitive information
        """
        # Arrange
        test_cases = [
            ("malformed", "not.a.valid.jwt"),
            ("expired", create_tenant_token(uuid4(), expires_delta=timedelta(seconds=-1))),
        ]

        # Act & Assert
        for _case_name, token in test_cases:
            with pytest.raises(HTTPException) as exc_info:
                await get_tenant_id(x_tenant_token=token)

            # Check error response structure
            error_detail = exc_info.value.detail
            assert "code" in error_detail
            assert "message" in error_detail

            # Check message content - should not expose internal details
            message = error_detail["message"].lower()
            assert "secret" not in message
            assert "traceback" not in message
            # Should have helpful error message
            assert len(message) > 0
            assert len(message) < 200  # Reasonable length
