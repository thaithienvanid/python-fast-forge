"""Tests for HIPAA Technical Safeguards Implementation."""

import pytest
from datetime import UTC, datetime, timedelta

from src.infrastructure.compliance.hipaa import (
    HIPAACompliance,
    PHIAccessType,
    AuditEvent,
)


class TestHIPAACompliance:
    """Test HIPAA compliance controls."""

    @pytest.fixture
    def hipaa(self):
        """Create HIPAA compliance instance."""
        return HIPAACompliance()

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_phi(self, hipaa):
        """Test PHI encryption and decryption."""
        # Test data
        phi_data = {
            "ssn": "123-45-6789",
            "name": "John Doe",
            "diagnosis": "Test diagnosis",
        }

        # Encrypt PHI
        encrypted = await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_smith",
            patient_id="patient_123",
            resource="medical_record_456",
        )

        assert encrypted is not None
        assert isinstance(encrypted, bytes)

        # Decrypt PHI
        decrypted = await hipaa.decrypt_phi(
            encrypted_data=encrypted,
            user_id="dr_smith",
            patient_id="patient_123",
            resource="medical_record_456",
            ip_address="192.168.1.100",
        )

        assert decrypted == phi_data

    @pytest.mark.asyncio
    async def test_audit_trail_creation(self, hipaa):
        """Test that audit trail is created for PHI access."""
        phi_data = {"ssn": "123-45-6789"}

        # Encrypt (creates audit event)
        encrypted = await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_smith",
            patient_id="patient_123",
        )

        # Decrypt (creates audit event)
        await hipaa.decrypt_phi(
            encrypted_data=encrypted,
            user_id="dr_smith",
            patient_id="patient_123",
        )

        # Get audit trail
        audit_trail = await hipaa.get_audit_trail(patient_id="patient_123")

        # Should have 2 events (encrypt + decrypt)
        assert len(audit_trail) >= 2

        # Check event types
        event_types = {event.access_type for event in audit_trail}
        assert PHIAccessType.CREATE in event_types
        assert PHIAccessType.READ in event_types

    @pytest.mark.asyncio
    async def test_audit_trail_filtering(self, hipaa):
        """Test audit trail filtering by user and patient."""
        # Create events for different users and patients
        phi_data = {"data": "test"}

        await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_smith",
            patient_id="patient_123",
        )

        await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_jones",
            patient_id="patient_456",
        )

        # Filter by patient
        patient_123_events = await hipaa.get_audit_trail(patient_id="patient_123")
        assert all(e.patient_id == "patient_123" for e in patient_123_events)

        # Filter by user
        dr_smith_events = await hipaa.get_audit_trail(user_id="dr_smith")
        assert all(e.user_id == "dr_smith" for e in dr_smith_events)

    @pytest.mark.asyncio
    async def test_failed_decryption_logged(self, hipaa):
        """Test that failed decryption attempts are logged."""
        # Try to decrypt invalid data
        with pytest.raises(Exception):
            await hipaa.decrypt_phi(
                encrypted_data=b"invalid_data",
                user_id="dr_smith",
                patient_id="patient_123",
            )

        # Check audit trail for failed attempt
        audit_trail = await hipaa.get_audit_trail(user_id="dr_smith")
        failed_events = [e for e in audit_trail if not e.success]

        assert len(failed_events) > 0
        assert failed_events[0].failure_reason is not None

    @pytest.mark.asyncio
    async def test_data_integrity_verification(self, hipaa):
        """Test HMAC data integrity verification."""
        data = "sensitive PHI data"

        # Sign data
        signature = await hipaa.sign_data(data)

        assert signature is not None
        assert isinstance(signature, str)

        # Verify signature
        is_valid = await hipaa.verify_data_integrity(data, signature)
        assert is_valid is True

        # Verify tampered data fails
        is_valid = await hipaa.verify_data_integrity("tampered data", signature)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_controls(self, hipaa):
        """Test control verification."""
        controls = await hipaa.verify_controls()

        assert controls["encryption_enabled"] is True
        assert controls["audit_logging_enabled"] is True
        assert controls["integrity_protection_enabled"] is True
        assert controls["access_control_enabled"] is True
        assert controls["authentication_enabled"] is True

    @pytest.mark.asyncio
    async def test_compliance_report(self, hipaa):
        """Test compliance report generation."""
        # Create some audit events
        phi_data = {"data": "test"}

        await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_smith",
            patient_id="patient_123",
        )

        # Generate report
        report = await hipaa.generate_compliance_report()

        assert "timestamp" in report
        assert "total_accesses" in report
        assert "failed_accesses" in report
        assert "success_rate" in report
        assert "unique_users" in report
        assert "unique_patients" in report
        assert "controls_status" in report
        assert "compliance_status" in report

        assert report["total_accesses"] >= 1
        assert report["compliance_status"] is True

    @pytest.mark.asyncio
    async def test_audit_event_fields(self, hipaa):
        """Test that audit events contain all required fields."""
        phi_data = {"data": "test"}

        await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_smith",
            patient_id="patient_123",
            resource="medical_record",
        )

        audit_trail = await hipaa.get_audit_trail()
        event = audit_trail[0]

        # Verify all required fields
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.user_id == "dr_smith"
        assert event.patient_id == "patient_123"
        assert event.access_type == PHIAccessType.CREATE
        assert event.resource == "medical_record"
        assert event.success is True
        assert event.data_hash is not None

    @pytest.mark.asyncio
    async def test_date_range_filtering(self, hipaa):
        """Test audit trail date range filtering."""
        phi_data = {"data": "test"}

        # Create event
        await hipaa.encrypt_phi(
            data=phi_data,
            user_id="dr_smith",
            patient_id="patient_123",
        )

        # Filter with date range
        now = datetime.now(UTC)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        events = await hipaa.get_audit_trail(start_date=start, end_date=end)
        assert len(events) > 0

        # Filter with future date (should return nothing)
        future_start = now + timedelta(days=1)
        future_events = await hipaa.get_audit_trail(start_date=future_start)
        assert len(future_events) == 0
