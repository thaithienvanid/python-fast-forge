"""Tests for tenant authentication utilities.

Test Organization:
- TestCreateTenantToken: Token creation functionality
- TestDecodeTenantToken: Token decoding and validation
- TestRefreshTenantToken: Token rotation
- TestTokenExpiration: Expiration checking utilities
- TestVerifyTenantToken: Token verification with tenant_id check
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import JWTError

from src.infrastructure.config import Settings
from src.utils.tenant_auth import (
    create_tenant_token,
    decode_tenant_token,
    get_token_expiration,
    is_token_expired,
    refresh_tenant_token,
)


# ============================================================================
# Create Token Tests
# ============================================================================


class TestCreateTenantToken:
    """Test create_tenant_token function."""

    def test_creates_valid_jwt_token(self) -> None:
        """Test creating a valid JWT token.

        Arrange: Tenant UUID
        Act: Create token
        Assert: Returns non-empty string in JWT format
        """
        # Arrange
        tenant_id = uuid4()

        # Act
        token = create_tenant_token(tenant_id)

        # Assert
        assert isinstance(token, str)
        assert len(token) > 0
        # JWT tokens have 3 parts separated by dots
        assert token.count(".") == 2

    def test_token_contains_tenant_id(self) -> None:
        """Test created token contains tenant_id claim.

        Arrange: Tenant UUID
        Act: Create and decode token
        Assert: Claims contain tenant_id
        """
        # Arrange
        tenant_id = uuid4()

        # Act
        token = create_tenant_token(tenant_id)
        claims = decode_tenant_token(token)

        # Assert
        assert claims.tenant_id == tenant_id

    def test_token_has_expiration(self) -> None:
        """Test created token has expiration claim.

        Arrange: Tenant UUID
        Act: Create and decode token
        Assert: Claims contain exp
        """
        # Arrange
        tenant_id = uuid4()

        # Act
        token = create_tenant_token(tenant_id)
        claims = decode_tenant_token(token)

        # Assert
        assert claims.exp is not None
        assert isinstance(claims.exp, datetime)

    def test_token_has_issued_at(self) -> None:
        """Test created token has issued_at claim.

        Arrange: Tenant UUID
        Act: Create and decode token
        Assert: Claims contain iat
        """
        # Arrange
        tenant_id = uuid4()

        # Act
        token = create_tenant_token(tenant_id)
        claims = decode_tenant_token(token)

        # Assert
        assert claims.iat is not None
        assert isinstance(claims.iat, datetime)

    def test_custom_expiration_delta(self) -> None:
        """Test creating token with custom expiration.

        Arrange: Tenant UUID and 1 hour expiration
        Act: Create token with custom expiration
        Assert: Token expires in approximately 1 hour
        """
        # Arrange
        tenant_id = uuid4()
        expires_delta = timedelta(hours=1)

        # Act
        token = create_tenant_token(tenant_id, expires_delta=expires_delta)
        claims = decode_tenant_token(token)
        now = datetime.now(UTC)

        # Assert
        time_until_expiry = claims.exp - now
        # Should be approximately 1 hour (with some tolerance for test execution time)
        assert 3590 < time_until_expiry.total_seconds() < 3610

    def test_default_expiration_uses_settings(self) -> None:
        """Test default expiration uses access_token_expire_minutes from settings.

        Arrange: Tenant UUID, no custom expiration
        Act: Create token
        Assert: Token expires in settings.access_token_expire_minutes
        """
        # Arrange
        tenant_id = uuid4()
        settings = Settings()

        # Act
        token = create_tenant_token(tenant_id)
        claims = decode_tenant_token(token)
        now = datetime.now(UTC)

        # Assert
        time_until_expiry = claims.exp - now
        expected_minutes = settings.access_token_expire_minutes
        # Should be approximately expected_minutes (with tolerance)
        assert (
            expected_minutes * 60 - 10
            < time_until_expiry.total_seconds()
            < expected_minutes * 60 + 10
        )


# ============================================================================
# Decode Token Tests
# ============================================================================


class TestDecodeTenantToken:
    """Test decode_tenant_token function."""

    def test_decodes_valid_token(self) -> None:
        """Test decoding a valid JWT token.

        Arrange: Valid JWT token
        Act: Decode token
        Assert: Returns TenantTokenClaims object
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act
        claims = decode_tenant_token(token)

        # Assert
        assert claims.tenant_id == tenant_id
        assert claims.type == "tenant_access"

    def test_raises_error_for_expired_token(self) -> None:
        """Test decoding expired token raises error.

        Arrange: Expired JWT token
        Act: Decode token
        Assert: Raises JWTError
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id, expires_delta=timedelta(seconds=-1))

        # Act & Assert
        with pytest.raises(JWTError):
            decode_tenant_token(token)

    def test_raises_error_for_invalid_signature(self) -> None:
        """Test decoding token with invalid signature raises error.

        Arrange: Token with wrong signature
        Act: Decode token
        Assert: Raises JWTError
        """
        # Arrange
        # Create a token with a different settings instance (different key)
        token = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiIwMThjNWU5ZS0xMjM0LTcwMDAtODAwMC0wMDAwMDAwMDAwMDAiLCJleHAiOjk5OTk5OTk5OTksImlhdCI6MTYwMDAwMDAwMCwidHlwZSI6InRlbmFudF9hY2Nlc3MifQ.invalid_signature"

        # Act & Assert
        with pytest.raises(JWTError):
            decode_tenant_token(token)

    def test_raises_error_for_malformed_token(self) -> None:
        """Test decoding malformed token raises error.

        Arrange: Malformed token string
        Act: Decode token
        Assert: Raises JWTError
        """
        # Arrange
        token = "not.a.valid.token"

        # Act & Assert
        with pytest.raises(JWTError):
            decode_tenant_token(token)


# ============================================================================
# Refresh Token Tests
# ============================================================================


class TestRefreshTenantToken:
    """Test refresh_tenant_token function."""

    def test_creates_new_token_with_same_tenant_id(self) -> None:
        """Test refreshing creates token with same tenant_id.

        Arrange: Valid JWT token
        Act: Refresh token
        Assert: New token has same tenant_id and is valid
        """
        # Arrange
        tenant_id = uuid4()
        old_token = create_tenant_token(tenant_id)

        # Act
        new_token = refresh_tenant_token(old_token)
        new_claims = decode_tenant_token(new_token)

        # Assert - New token should have same tenant_id and be valid
        assert new_claims.tenant_id == tenant_id
        assert new_claims.exp is not None
        assert new_claims.iat is not None

    def test_new_token_has_valid_expiration(self) -> None:
        """Test refreshed token has valid expiration time.

        Arrange: Valid JWT token
        Act: Refresh token
        Assert: New token has valid exp claim in the future
        """
        # Arrange
        tenant_id = uuid4()
        old_token = create_tenant_token(tenant_id)

        # Act
        new_token = refresh_tenant_token(old_token)
        new_claims = decode_tenant_token(new_token)
        now = datetime.now(UTC)

        # Assert - Token should not be expired
        assert new_claims.exp > now

    def test_refresh_with_custom_expiration(self) -> None:
        """Test refreshing with custom expiration delta.

        Arrange: Valid JWT token and custom expiration
        Act: Refresh token with custom expiration
        Assert: New token has custom expiration
        """
        # Arrange
        tenant_id = uuid4()
        old_token = create_tenant_token(tenant_id)
        custom_expiration = timedelta(hours=2)

        # Act
        new_token = refresh_tenant_token(old_token, expires_delta=custom_expiration)
        new_claims = decode_tenant_token(new_token)
        now = datetime.now(UTC)

        # Assert
        time_until_expiry = new_claims.exp - now
        # Should be approximately 2 hours
        assert 7190 < time_until_expiry.total_seconds() < 7210

    def test_raises_error_for_expired_token(self) -> None:
        """Test refreshing expired token raises error.

        Arrange: Expired JWT token
        Act: Refresh token
        Assert: Raises jwt.ExpiredSignatureError
        """
        # Arrange
        tenant_id = uuid4()
        old_token = create_tenant_token(tenant_id, expires_delta=timedelta(seconds=-1))

        # Act & Assert
        with pytest.raises(JWTError):
            refresh_tenant_token(old_token)


# ============================================================================
# Token Expiration Tests
# ============================================================================


class TestTokenExpiration:
    """Test token expiration utility functions."""

    def test_get_token_expiration_returns_datetime(self) -> None:
        """Test get_token_expiration returns datetime.

        Arrange: Valid JWT token
        Act: Get expiration
        Assert: Returns datetime in UTC
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act
        exp = get_token_expiration(token)

        # Assert
        assert isinstance(exp, datetime)
        assert exp.tzinfo == UTC

    def test_get_token_expiration_is_in_future(self) -> None:
        """Test token expiration is in the future for new tokens.

        Arrange: Newly created JWT token
        Act: Get expiration
        Assert: Expiration is in the future
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act
        exp = get_token_expiration(token)
        now = datetime.now(UTC)

        # Assert
        assert exp > now

    def test_is_token_expired_returns_false_for_valid_token(self) -> None:
        """Test is_token_expired returns False for valid token.

        Arrange: Valid JWT token
        Act: Check if expired
        Assert: Returns False
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act
        expired = is_token_expired(token)

        # Assert
        assert expired is False

    def test_is_token_expired_returns_true_for_expired_token(self) -> None:
        """Test is_token_expired returns True for expired token.

        Arrange: Expired JWT token
        Act: Check if expired
        Assert: Returns True
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id, expires_delta=timedelta(seconds=-1))

        # Act
        expired = is_token_expired(token)

        # Assert
        assert expired is True

    def test_is_token_expired_returns_true_for_invalid_token(self) -> None:
        """Test is_token_expired returns True for invalid token.

        Arrange: Invalid JWT token
        Act: Check if expired
        Assert: Returns True (treat invalid as expired)
        """
        # Arrange
        token = "invalid.jwt.token"

        # Act
        expired = is_token_expired(token)

        # Assert
        assert expired is True


# ============================================================================
# Integration Tests
# ============================================================================


class TestJWTUtilsIntegration:
    """Integration tests for JWT utilities."""

    def test_create_decode_roundtrip(self) -> None:
        """Test creating and decoding token roundtrip.

        Arrange: Tenant UUID
        Act: Create token, decode it
        Assert: Decoded payload matches original data
        """
        # Arrange
        tenant_id = uuid4()

        # Act
        token = create_tenant_token(tenant_id)
        claims = decode_tenant_token(token)

        # Assert
        assert claims.tenant_id == tenant_id
        assert claims.exp is not None
        assert claims.iat is not None

    def test_refresh_multiple_times(self) -> None:
        """Test refreshing token multiple times.

        Arrange: Valid JWT token
        Act: Refresh token 3 times
        Assert: Each refresh produces valid token with same tenant_id
        """
        # Arrange
        tenant_id = uuid4()
        token = create_tenant_token(tenant_id)

        # Act - Refresh token multiple times
        for _ in range(3):
            token = refresh_tenant_token(token)
            claims = decode_tenant_token(token)

            # Assert - Each refreshed token should be valid and have correct tenant_id
            assert claims.tenant_id == tenant_id
            assert claims.exp is not None
            assert claims.iat is not None
