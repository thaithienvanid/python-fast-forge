"""Comprehensive tests for the HIPAA compliance implementation.

Tests cover PHI encryption/decryption, audit trail, integrity verification,
access control, and compliance reporting.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.compliance.hipaa import (
    HIPAACompliance,
    PHIAccessType,
)


# ─── PHIAccessType ────────────────────────────────────────────────────────────


class TestPHIAccessType:
    """Tests for PHIAccessType enum."""

    def test_access_types_defined(self):
        types = {t.value for t in PHIAccessType}
        assert "create" in types
        assert "read" in types
        assert "update" in types
        assert "delete" in types
        assert "export" in types
        assert "print" in types


# ─── HIPAACompliance Initialization ──────────────────────────────────────────


class TestHIPAAComplianceInit:
    """Tests for HIPAACompliance initialization."""

    def test_default_init(self):
        hipaa = HIPAACompliance()
        assert hipaa._cipher is not None
        assert hipaa._audit_trail == []
        assert hipaa._hmac_key is not None

    def test_custom_encryption_key(self):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        hipaa = HIPAACompliance(encryption_key=key)
        assert hipaa._encryption_key == key

    def test_auto_generates_encryption_key(self):
        hipaa = HIPAACompliance()
        assert hipaa._encryption_key is not None
        assert len(hipaa._encryption_key) > 0

    def test_unique_hmac_keys_per_instance(self):
        hipaa1 = HIPAACompliance()
        hipaa2 = HIPAACompliance()
        assert hipaa1._hmac_key != hipaa2._hmac_key


# ─── encrypt_phi ─────────────────────────────────────────────────────────────


class TestEncryptPHI:
    """Tests for encrypt_phi method."""

    @pytest.mark.asyncio
    async def test_encrypt_phi_returns_bytes(self):
        hipaa = HIPAACompliance()
        encrypted = await hipaa.encrypt_phi(
            data={"ssn": "123-45-6789", "name": "John Doe"},
            user_id="dr_smith",
        )
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0

    @pytest.mark.asyncio
    async def test_encrypted_data_not_plaintext(self):
        hipaa = HIPAACompliance()
        data = {"ssn": "123-45-6789"}
        encrypted = await hipaa.encrypt_phi(data=data, user_id="dr_smith")

        # Encrypted data should not contain the plaintext SSN
        assert b"123-45-6789" not in encrypted

    @pytest.mark.asyncio
    async def test_encrypt_phi_creates_audit_event(self):
        hipaa = HIPAACompliance()
        await hipaa.encrypt_phi(
            data={"name": "Patient X"},
            user_id="dr_smith",
            patient_id="patient_123",
        )

        assert len(hipaa._audit_trail) == 1
        event = hipaa._audit_trail[0]
        assert event.user_id == "dr_smith"
        assert event.patient_id == "patient_123"
        assert event.access_type == PHIAccessType.CREATE
        assert event.success is True

    @pytest.mark.asyncio
    async def test_encrypt_phi_with_resource(self):
        hipaa = HIPAACompliance()
        await hipaa.encrypt_phi(
            data={"name": "Patient X"},
            user_id="dr_smith",
            resource="medical_record_456",
        )

        event = hipaa._audit_trail[0]
        assert event.resource == "medical_record_456"

    @pytest.mark.asyncio
    async def test_encrypt_phi_different_results_per_call(self):
        """Fernet produces different ciphertext each time (nonce-based)."""
        hipaa = HIPAACompliance()
        data = {"ssn": "123-45-6789"}
        encrypted1 = await hipaa.encrypt_phi(data=data, user_id="dr1")
        encrypted2 = await hipaa.encrypt_phi(data=data, user_id="dr2")
        assert encrypted1 != encrypted2

    @pytest.mark.asyncio
    async def test_encrypt_phi_complex_data(self):
        hipaa = HIPAACompliance()
        complex_data = {
            "ssn": "123-45-6789",
            "medications": ["aspirin", "metformin"],
            "diagnoses": [{"code": "E11", "description": "Type 2 diabetes"}],
            "age": 45,
        }
        encrypted = await hipaa.encrypt_phi(data=complex_data, user_id="nurse_jones")
        assert isinstance(encrypted, bytes)


# ─── decrypt_phi ─────────────────────────────────────────────────────────────


class TestDecryptPHI:
    """Tests for decrypt_phi method."""

    @pytest.mark.asyncio
    async def test_decrypt_phi_roundtrip(self):
        hipaa = HIPAACompliance()
        original_data = {"ssn": "123-45-6789", "name": "John Doe"}

        encrypted = await hipaa.encrypt_phi(data=original_data, user_id="dr_smith")
        decrypted = await hipaa.decrypt_phi(encrypted_data=encrypted, user_id="dr_smith")

        assert decrypted == original_data

    @pytest.mark.asyncio
    async def test_decrypt_phi_creates_audit_event(self):
        hipaa = HIPAACompliance()
        data = {"name": "Patient X"}
        encrypted = await hipaa.encrypt_phi(data=data, user_id="dr_smith")

        # Clear audit trail
        hipaa._audit_trail.clear()

        await hipaa.decrypt_phi(
            encrypted_data=encrypted,
            user_id="nurse_jones",
            patient_id="patient_123",
            ip_address="192.168.1.1",
        )

        assert len(hipaa._audit_trail) == 1
        event = hipaa._audit_trail[0]
        assert event.user_id == "nurse_jones"
        assert event.access_type == PHIAccessType.READ
        assert event.success is True

    @pytest.mark.asyncio
    async def test_decrypt_phi_invalid_data_raises(self):
        hipaa = HIPAACompliance()
        with pytest.raises(Exception):
            await hipaa.decrypt_phi(
                encrypted_data=b"invalid_encrypted_data",
                user_id="dr_smith",
            )

    @pytest.mark.asyncio
    async def test_decrypt_phi_audit_event_on_failure(self):
        hipaa = HIPAACompliance()
        try:
            await hipaa.decrypt_phi(
                encrypted_data=b"invalid_data",
                user_id="dr_smith",
            )
        except Exception:  # noqa: S110
            pass

        assert len(hipaa._audit_trail) == 1
        event = hipaa._audit_trail[0]
        assert event.success is False
        assert event.failure_reason is not None

    @pytest.mark.asyncio
    async def test_decrypt_phi_with_ip_address(self):
        hipaa = HIPAACompliance()
        data = {"name": "Patient Y"}
        encrypted = await hipaa.encrypt_phi(data=data, user_id="dr_smith")
        hipaa._audit_trail.clear()

        await hipaa.decrypt_phi(
            encrypted_data=encrypted,
            user_id="dr_smith",
            ip_address="10.0.0.1",
        )

        event = hipaa._audit_trail[0]
        assert event.ip_address == "10.0.0.1"


# ─── sign_data / verify_data_integrity ───────────────────────────────────────


class TestDataIntegrity:
    """Tests for sign_data and verify_data_integrity methods."""

    @pytest.mark.asyncio
    async def test_sign_data_returns_hex_string(self):
        hipaa = HIPAACompliance()
        signature = await hipaa.sign_data("test data")
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA-256 hex digest

    @pytest.mark.asyncio
    async def test_verify_data_integrity_valid(self):
        hipaa = HIPAACompliance()
        data = "sensitive phi data"
        signature = await hipaa.sign_data(data)

        is_valid = await hipaa.verify_data_integrity(data, signature)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_data_integrity_tampered_data(self):
        hipaa = HIPAACompliance()
        original_data = "original phi data"
        signature = await hipaa.sign_data(original_data)

        is_valid = await hipaa.verify_data_integrity("tampered phi data", signature)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_data_integrity_invalid_signature(self):
        hipaa = HIPAACompliance()
        data = "test data"
        is_valid = await hipaa.verify_data_integrity(data, "a" * 64)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_sign_data_bytes_input(self):
        hipaa = HIPAACompliance()
        data = b"binary phi data"
        signature = await hipaa.sign_data(data)
        assert isinstance(signature, str)

    @pytest.mark.asyncio
    async def test_verify_data_integrity_bytes_input(self):
        hipaa = HIPAACompliance()
        data = "test data"
        signature = await hipaa.sign_data(data)

        # Verify with bytes input
        is_valid = await hipaa.verify_data_integrity(data.encode("utf-8"), signature)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_sign_verify_roundtrip_with_complex_data(self):
        hipaa = HIPAACompliance()
        data = json.dumps({"ssn": "123-45-6789", "diagnosis": "E11"})
        signature = await hipaa.sign_data(data)
        is_valid = await hipaa.verify_data_integrity(data, signature)
        assert is_valid is True


# ─── get_audit_trail ──────────────────────────────────────────────────────────


class TestGetAuditTrail:
    """Tests for get_audit_trail method."""

    @pytest.mark.asyncio
    async def test_get_all_events(self):
        hipaa = HIPAACompliance()
        data = {"name": "Patient A"}
        encrypted = await hipaa.encrypt_phi(data=data, user_id="dr1", patient_id="p1")
        await hipaa.decrypt_phi(encrypted_data=encrypted, user_id="dr2", patient_id="p1")

        events = await hipaa.get_audit_trail()
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_filter_by_patient_id(self):
        hipaa = HIPAACompliance()
        await hipaa.encrypt_phi({"name": "Patient A"}, user_id="dr1", patient_id="patient_a")
        await hipaa.encrypt_phi({"name": "Patient B"}, user_id="dr1", patient_id="patient_b")

        events = await hipaa.get_audit_trail(patient_id="patient_a")
        assert all(e.patient_id == "patient_a" for e in events)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_filter_by_user_id(self):
        hipaa = HIPAACompliance()
        await hipaa.encrypt_phi({"name": "Patient A"}, user_id="dr_smith", patient_id="p1")
        await hipaa.encrypt_phi({"name": "Patient B"}, user_id="dr_jones", patient_id="p2")

        events = await hipaa.get_audit_trail(user_id="dr_smith")
        assert all(e.user_id == "dr_smith" for e in events)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self):
        hipaa = HIPAACompliance()
        await hipaa.encrypt_phi({"name": "Patient A"}, user_id="dr1", patient_id="p1")

        start_date = datetime.now(UTC) - timedelta(seconds=10)
        end_date = datetime.now(UTC) + timedelta(seconds=10)

        events = await hipaa.get_audit_trail(start_date=start_date, end_date=end_date)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_filter_excludes_old_events(self):
        hipaa = HIPAACompliance()
        await hipaa.encrypt_phi({"name": "Patient A"}, user_id="dr1", patient_id="p1")

        # Filter with a future start date
        future_start = datetime.now(UTC) + timedelta(hours=1)
        events = await hipaa.get_audit_trail(start_date=future_start)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_empty_audit_trail(self):
        hipaa = HIPAACompliance()
        events = await hipaa.get_audit_trail()
        assert events == []


# ─── verify_controls ─────────────────────────────────────────────────────────


class TestVerifyControls:
    """Tests for verify_controls method."""

    @pytest.mark.asyncio
    async def test_verify_controls_returns_dict(self):
        hipaa = HIPAACompliance()
        controls = await hipaa.verify_controls()
        assert isinstance(controls, dict)

    @pytest.mark.asyncio
    async def test_verify_controls_all_true(self):
        hipaa = HIPAACompliance()
        controls = await hipaa.verify_controls()

        expected_controls = [
            "encryption_enabled",
            "audit_logging_enabled",
            "integrity_protection_enabled",
            "access_control_enabled",
            "authentication_enabled",
        ]
        for control in expected_controls:
            assert control in controls
            assert controls[control] is True


# ─── generate_compliance_report ──────────────────────────────────────────────


class TestHIPAAComplianceReport:
    """Tests for generate_compliance_report method."""

    @pytest.mark.asyncio
    async def test_empty_report(self):
        hipaa = HIPAACompliance()
        report = await hipaa.generate_compliance_report()

        assert "timestamp" in report
        assert report["total_accesses"] == 0
        assert report["failed_accesses"] == 0
        assert report["success_rate"] == 1.0
        assert "controls_status" in report
        assert "compliance_status" in report

    @pytest.mark.asyncio
    async def test_report_with_events(self):
        hipaa = HIPAACompliance()
        data = {"ssn": "123-45-6789"}
        encrypted = await hipaa.encrypt_phi(data=data, user_id="dr_smith")
        await hipaa.decrypt_phi(encrypted_data=encrypted, user_id="dr_smith")

        report = await hipaa.generate_compliance_report()

        assert report["total_accesses"] == 2
        assert report["failed_accesses"] == 0
        assert report["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_report_counts_failures(self):
        hipaa = HIPAACompliance()
        # Encrypt some data
        data = {"name": "Patient X"}
        await hipaa.encrypt_phi(data=data, user_id="dr1")

        # Try invalid decrypt
        try:
            await hipaa.decrypt_phi(b"invalid", user_id="dr1")
        except Exception:  # noqa: S110
            pass

        report = await hipaa.generate_compliance_report()
        assert report["failed_accesses"] >= 1

    @pytest.mark.asyncio
    async def test_report_success_rate(self):
        hipaa = HIPAACompliance()
        data = {"name": "Patient X"}
        encrypted = await hipaa.encrypt_phi(data=data, user_id="dr1")
        await hipaa.decrypt_phi(encrypted_data=encrypted, user_id="dr1")

        report = await hipaa.generate_compliance_report()
        assert report["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_report_unique_users(self):
        hipaa = HIPAACompliance()
        data = {"name": "Patient X"}
        await hipaa.encrypt_phi(data=data, user_id="dr_smith")
        await hipaa.encrypt_phi(data=data, user_id="nurse_jones")

        report = await hipaa.generate_compliance_report()
        assert report["unique_users"] == 2

    @pytest.mark.asyncio
    async def test_report_compliance_status(self):
        hipaa = HIPAACompliance()
        report = await hipaa.generate_compliance_report()
        assert report["compliance_status"] is True
