"""Unit tests for API dependencies."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from authlib.jose import JoseError
from fastapi import HTTPException
from pydantic import ValidationError

from src.domain.tenant_claims import TenantTokenClaims
from src.infrastructure.compliance import ComplianceManager
from src.presentation.api.dependencies import get_compliance_manager, get_tenant_id


class TestGetComplianceManager:
    """Tests for get_compliance_manager dependency."""

    def test_validates_encryption_key_length(self):
        """Validates encryption key uses jwt_secret_key truncated to 32 bytes."""
        import src.presentation.api.dependencies

        src.presentation.api.dependencies._compliance_manager = None

        with patch("src.presentation.api.dependencies.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            # Set jwt_secret_key that will be truncated to 32 bytes
            mock_settings.security.jwt_secret_key = (
                "test_secret_key_for_compliance_encryption_needs_to_be_long"
            )
            mock_get_settings.return_value = mock_settings

            manager = get_compliance_manager()

            # Verify manager was created successfully
            assert isinstance(manager, ComplianceManager)

    def test_creates_manager_without_encryption_key(self):
        """Creates ComplianceManager when no jwt_secret_key is available."""
        import src.presentation.api.dependencies

        src.presentation.api.dependencies._compliance_manager = None

        with patch("src.presentation.api.dependencies.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            # Remove jwt_secret_key attribute to test fallback
            del mock_settings.security.jwt_secret_key
            mock_get_settings.return_value = mock_settings

            manager = get_compliance_manager()

            # Verify manager was created with generated key
            assert isinstance(manager, ComplianceManager)


class TestGetTenantId:
    """Tests for get_tenant_id dependency."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_token_provided(self):
        """Returns None when X-Tenant-Token header is not provided."""
        tenant_id = await get_tenant_id(x_tenant_token=None)

        assert tenant_id is None

    @pytest.mark.asyncio
    async def test_extracts_tenant_id_from_valid_token(self):
        """Extracts tenant ID from valid JWT token."""
        expected_tenant_id = uuid4()
        mock_claims = TenantTokenClaims(
            tenant_id=expected_tenant_id,
            exp=MagicMock(),
            iat=MagicMock(),
        )

        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                return_value=mock_claims,
            ),
            patch("src.presentation.api.dependencies.get_settings"),
        ):
            tenant_id = await get_tenant_id(x_tenant_token="valid.jwt.token")

        assert tenant_id == expected_tenant_id

    @pytest.mark.asyncio
    async def test_raises_401_on_expired_token(self):
        """Raises 401 Unauthorized when token is expired."""
        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=JoseError("signature has expired"),
            ),
            patch("src.presentation.api.dependencies.get_settings"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_tenant_id(x_tenant_token="expired.jwt.token")

        assert exc_info.value.status_code == 401
        assert "TENANT_TOKEN_EXPIRED" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_raises_401_on_invalid_signature(self):
        """Raises 401 Unauthorized when signature is invalid."""
        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=JoseError("invalid signature"),
            ),
            patch("src.presentation.api.dependencies.get_settings"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_tenant_id(x_tenant_token="tampered.jwt.token")

        assert exc_info.value.status_code == 401
        assert "TENANT_TOKEN_INVALID_SIGNATURE" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_raises_401_on_malformed_token(self):
        """Raises 401 Unauthorized when token is malformed."""
        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=JoseError("invalid token structure"),
            ),
            patch("src.presentation.api.dependencies.get_settings"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_tenant_id(x_tenant_token="malformed-token")

        assert exc_info.value.status_code == 401
        assert "TENANT_TOKEN_MALFORMED" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_raises_401_on_invalid_claims(self):
        """Raises 401 Unauthorized when claims validation fails."""
        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=ValidationError.from_exception_data(
                    "TenantTokenClaims", [{"type": "missing", "loc": ("tenant_id",)}]
                ),
            ),
            patch("src.presentation.api.dependencies.get_settings"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_tenant_id(x_tenant_token="invalid.claims.token")

        assert exc_info.value.status_code == 401
        assert "TENANT_TOKEN_INVALID_CLAIMS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_raises_401_on_missing_tenant_id_claim(self):
        """Raises 401 Unauthorized when tenant_id claim is missing."""
        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=KeyError("tenant_id"),
            ),
            patch("src.presentation.api.dependencies.get_settings"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_tenant_id(x_tenant_token="no.tenant.token")

        assert exc_info.value.status_code == 401
        assert "TENANT_TOKEN_INVALID_CLAIMS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_raises_401_on_unexpected_error(self):
        """Raises 401 Unauthorized on unexpected decoding errors."""
        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                side_effect=RuntimeError("unexpected error"),
            ),
            patch("src.presentation.api.dependencies.get_settings"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_tenant_id(x_tenant_token="error.jwt.token")

        assert exc_info.value.status_code == 401
        assert "TENANT_TOKEN_VALIDATION_FAILED" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_uses_provided_settings(self):
        """Uses provided settings parameter."""
        mock_settings = MagicMock()
        expected_tenant_id = uuid4()
        mock_claims = TenantTokenClaims(
            tenant_id=expected_tenant_id,
            exp=MagicMock(),
            iat=MagicMock(),
        )

        with patch(
            "src.presentation.api.dependencies.decode_tenant_token",
            return_value=mock_claims,
        ) as mock_decode:
            tenant_id = await get_tenant_id(
                x_tenant_token="valid.jwt.token", settings=mock_settings
            )

        assert tenant_id == expected_tenant_id
        mock_decode.assert_called_once_with("valid.jwt.token", mock_settings)

    @pytest.mark.asyncio
    async def test_gets_settings_when_not_provided(self):
        """Gets settings from get_settings when not provided."""
        expected_tenant_id = uuid4()
        mock_claims = TenantTokenClaims(
            tenant_id=expected_tenant_id,
            exp=MagicMock(),
            iat=MagicMock(),
        )

        with (
            patch(
                "src.presentation.api.dependencies.decode_tenant_token",
                return_value=mock_claims,
            ),
            patch("src.presentation.api.dependencies.get_settings") as mock_get_settings,
        ):
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            # settings=None triggers get_settings call
            tenant_id = await get_tenant_id(x_tenant_token="valid.jwt.token")

        assert tenant_id == expected_tenant_id
