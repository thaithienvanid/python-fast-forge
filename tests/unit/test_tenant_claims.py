"""Unit tests for tenant token claims."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.domain.tenant_claims import TenantTokenClaims


class TestTenantTokenClaims:
    """Tests for TenantTokenClaims model."""

    def test_creates_claims_with_all_fields(self):
        """Can create claims with all fields."""
        tenant_id = uuid4()
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=30)
        nbf = now - timedelta(seconds=5)

        claims = TenantTokenClaims(
            tenant_id=tenant_id,
            exp=exp,
            iat=now,
            nbf=nbf,
            type="tenant_access",
            jti="unique-jwt-id",
        )

        assert claims.tenant_id == tenant_id
        assert claims.exp == exp
        assert claims.iat == now
        assert claims.nbf == nbf
        assert claims.type == "tenant_access"
        assert claims.jti == "unique-jwt-id"

    def test_creates_claims_with_minimal_fields(self):
        """Can create claims with minimal required fields."""
        tenant_id = uuid4()
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=30)

        claims = TenantTokenClaims(
            tenant_id=tenant_id,
            exp=exp,
            iat=now,
        )

        assert claims.tenant_id == tenant_id
        assert claims.exp == exp
        assert claims.iat == now
        assert claims.nbf is None
        assert claims.type == "tenant_access"  # default
        assert claims.jti is None

    def test_validates_tenant_id_from_string(self):
        """Validator converts string to UUID."""
        tenant_id_str = str(uuid4())
        now = datetime.now(UTC)

        claims = TenantTokenClaims(
            tenant_id=tenant_id_str,  # type: ignore[arg-type]
            exp=now + timedelta(minutes=30),
            iat=now,
        )

        assert isinstance(claims.tenant_id, UUID)
        assert str(claims.tenant_id) == tenant_id_str

    def test_rejects_invalid_tenant_id_string(self):
        """Validator rejects invalid UUID string."""
        now = datetime.now(UTC)

        with pytest.raises(ValidationError) as exc_info:
            TenantTokenClaims(
                tenant_id="not-a-uuid",  # type: ignore[arg-type]
                exp=now + timedelta(minutes=30),
                iat=now,
            )

        assert "tenant_id" in str(exc_info.value)

    def test_to_jwt_payload_with_all_fields(self):
        """to_jwt_payload converts all fields correctly."""
        tenant_id = uuid4()
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=30)
        nbf = now - timedelta(seconds=5)

        claims = TenantTokenClaims(
            tenant_id=tenant_id,
            exp=exp,
            iat=now,
            nbf=nbf,
            type="tenant_access",
            jti="jwt-id-123",
        )

        payload = claims.to_jwt_payload()

        assert payload["tenant_id"] == str(tenant_id)
        assert payload["exp"] == int(exp.timestamp())
        assert payload["iat"] == int(now.timestamp())
        assert payload["nbf"] == int(nbf.timestamp())
        assert payload["type"] == "tenant_access"
        assert payload["jti"] == "jwt-id-123"

    def test_to_jwt_payload_without_optional_fields(self):
        """to_jwt_payload excludes None optional fields."""
        tenant_id = uuid4()
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=30)

        claims = TenantTokenClaims(
            tenant_id=tenant_id,
            exp=exp,
            iat=now,
        )

        payload = claims.to_jwt_payload()

        assert payload["tenant_id"] == str(tenant_id)
        assert payload["exp"] == int(exp.timestamp())
        assert payload["iat"] == int(now.timestamp())
        assert payload["type"] == "tenant_access"
        assert "nbf" not in payload
        assert "jti" not in payload

    def test_from_jwt_payload_with_all_fields(self):
        """from_jwt_payload reconstructs claims from payload."""
        tenant_id = uuid4()
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=30)
        nbf = now - timedelta(seconds=5)

        payload = {
            "tenant_id": str(tenant_id),
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "nbf": int(nbf.timestamp()),
            "type": "tenant_access",
            "jti": "jwt-id-456",
        }

        claims = TenantTokenClaims.from_jwt_payload(payload)

        assert claims.tenant_id == tenant_id
        assert claims.exp.timestamp() == pytest.approx(exp.timestamp(), abs=1)
        assert claims.iat.timestamp() == pytest.approx(now.timestamp(), abs=1)
        assert claims.nbf is not None
        assert claims.nbf.timestamp() == pytest.approx(nbf.timestamp(), abs=1)
        assert claims.type == "tenant_access"
        assert claims.jti == "jwt-id-456"

    def test_from_jwt_payload_without_optional_fields(self):
        """from_jwt_payload handles missing optional fields."""
        tenant_id = uuid4()
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=30)

        payload = {
            "tenant_id": str(tenant_id),
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
        }

        claims = TenantTokenClaims.from_jwt_payload(payload)

        assert claims.tenant_id == tenant_id
        assert claims.exp.timestamp() == pytest.approx(exp.timestamp(), abs=1)
        assert claims.iat.timestamp() == pytest.approx(now.timestamp(), abs=1)
        assert claims.nbf is None
        assert claims.type == "tenant_access"  # default
        assert claims.jti is None

    def test_roundtrip_to_and_from_jwt_payload(self):
        """Claims can be converted to payload and back."""
        original_claims = TenantTokenClaims(
            tenant_id=uuid4(),
            exp=datetime.now(UTC) + timedelta(minutes=30),
            iat=datetime.now(UTC),
            nbf=datetime.now(UTC) - timedelta(seconds=5),
            jti="roundtrip-test",
        )

        payload = original_claims.to_jwt_payload()
        reconstructed_claims = TenantTokenClaims.from_jwt_payload(payload)

        assert reconstructed_claims.tenant_id == original_claims.tenant_id
        assert reconstructed_claims.exp.timestamp() == pytest.approx(
            original_claims.exp.timestamp(), abs=1
        )
        assert reconstructed_claims.iat.timestamp() == pytest.approx(
            original_claims.iat.timestamp(), abs=1
        )
        assert reconstructed_claims.nbf is not None
        assert original_claims.nbf is not None
        assert reconstructed_claims.nbf.timestamp() == pytest.approx(
            original_claims.nbf.timestamp(), abs=1
        )
        assert reconstructed_claims.jti == original_claims.jti

    def test_type_field_is_literal(self):
        """Type field must be exactly 'tenant_access'."""
        tenant_id = uuid4()
        now = datetime.now(UTC)

        # Valid type
        claims = TenantTokenClaims(
            tenant_id=tenant_id,
            exp=now + timedelta(minutes=30),
            iat=now,
            type="tenant_access",
        )
        assert claims.type == "tenant_access"

    def test_jwt_timestamps_are_integers(self):
        """JWT payload uses integer timestamps."""
        claims = TenantTokenClaims(
            tenant_id=uuid4(),
            exp=datetime.now(UTC) + timedelta(minutes=30),
            iat=datetime.now(UTC),
        )

        payload = claims.to_jwt_payload()

        assert isinstance(payload["exp"], int)
        assert isinstance(payload["iat"], int)

    def test_from_jwt_payload_handles_float_timestamps(self):
        """from_jwt_payload accepts float timestamps."""
        tenant_id = uuid4()
        now_timestamp = datetime.now(UTC).timestamp()

        payload = {
            "tenant_id": str(tenant_id),
            "exp": now_timestamp + 1800.5,  # float timestamp
            "iat": now_timestamp,
        }

        claims = TenantTokenClaims.from_jwt_payload(payload)

        assert claims.tenant_id == tenant_id
        assert isinstance(claims.exp, datetime)
        assert isinstance(claims.iat, datetime)
