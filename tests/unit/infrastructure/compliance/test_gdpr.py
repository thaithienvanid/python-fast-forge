"""Comprehensive tests for the GDPR compliance implementation.

Tests cover consent management, data subject rights (access, rectification,
erasure, portability), processing records, breach reporting, and compliance reports.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.compliance.gdpr import (
    BreachSeverity,
    ConsentRecord,
    DataBreachRecord,
    DataCategory,
    DataProcessingRecord,
    GDPRCompliance,
    ProcessingPurpose,
)


# ─── Enums ────────────────────────────────────────────────────────────────────


class TestGDPREnums:
    """Tests for GDPR enum values."""

    def test_processing_purposes(self):
        assert ProcessingPurpose.CONSENT == "consent"
        assert ProcessingPurpose.CONTRACT == "contract"
        assert ProcessingPurpose.LEGAL_OBLIGATION == "legal_obligation"
        assert ProcessingPurpose.LEGITIMATE_INTERESTS == "legitimate_interests"

    def test_data_categories(self):
        assert DataCategory.BASIC_IDENTITY == "basic_identity"
        assert DataCategory.FINANCIAL == "financial"
        assert DataCategory.HEALTH == "health"
        assert DataCategory.BIOMETRIC == "biometric"

    def test_breach_severities(self):
        assert BreachSeverity.LOW == "low"
        assert BreachSeverity.MEDIUM == "medium"
        assert BreachSeverity.HIGH == "high"
        assert BreachSeverity.CRITICAL == "critical"


# ─── GDPRCompliance Initialization ────────────────────────────────────────────


class TestGDPRComplianceInit:
    """Tests for GDPRCompliance initialization."""

    def test_default_init(self):
        gdpr = GDPRCompliance()
        assert gdpr._consent_records == []
        assert gdpr._processing_records == []
        assert gdpr._breach_records == []
        assert gdpr._data_store == {}

    def test_multiple_instances_independent(self):
        gdpr1 = GDPRCompliance()
        gdpr2 = GDPRCompliance()
        gdpr1._consent_records.append(MagicMock())
        assert len(gdpr2._consent_records) == 0


# ─── record_consent ────────────────────────────────────────────────────────────


class TestRecordConsent:
    """Tests for record_consent method."""

    @pytest.mark.asyncio
    async def test_record_consent_basic(self):
        gdpr = GDPRCompliance()
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose=ProcessingPurpose.CONSENT,
            consent_given=True,
        )

        assert isinstance(consent, ConsentRecord)
        assert consent.user_id == "user123"
        assert consent.purpose == ProcessingPurpose.CONSENT
        assert consent.consent_given is True
        assert consent.consent_id.startswith("consent_")

    @pytest.mark.asyncio
    async def test_record_consent_with_expiry(self):
        gdpr = GDPRCompliance()
        before = datetime.now(UTC)
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose=ProcessingPurpose.CONSENT,
            consent_given=True,
            expires_in_days=365,
        )

        assert consent.expires_at is not None
        expected = before + timedelta(days=365)
        # Allow for slight timing differences
        assert abs((consent.expires_at - expected).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_record_consent_without_expiry(self):
        gdpr = GDPRCompliance()
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose=ProcessingPurpose.CONTRACT,
            consent_given=True,
        )
        assert consent.expires_at is None

    @pytest.mark.asyncio
    async def test_record_consent_with_metadata(self):
        gdpr = GDPRCompliance()
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose=ProcessingPurpose.CONSENT,
            consent_given=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            consent_text="I agree to the terms",
        )

        assert consent.ip_address == "192.168.1.1"
        assert consent.user_agent == "Mozilla/5.0"
        assert consent.consent_text == "I agree to the terms"

    @pytest.mark.asyncio
    async def test_record_consent_appended_to_records(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("u1", ProcessingPurpose.CONTRACT, True)
        await gdpr.record_consent("u2", ProcessingPurpose.CONSENT, False)

        assert len(gdpr._consent_records) == 2

    @pytest.mark.asyncio
    async def test_record_consent_withdrawal(self):
        gdpr = GDPRCompliance()
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose=ProcessingPurpose.CONSENT,
            consent_given=False,
        )
        assert consent.consent_given is False

    @pytest.mark.asyncio
    async def test_record_consent_string_purpose(self):
        gdpr = GDPRCompliance()
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )
        assert consent.purpose == "marketing"


# ─── has_consent ─────────────────────────────────────────────────────────────


class TestHasConsent:
    """Tests for has_consent method."""

    @pytest.mark.asyncio
    async def test_no_consent_returns_false(self):
        gdpr = GDPRCompliance()
        result = await gdpr.has_consent("user123", ProcessingPurpose.CONSENT)
        assert result is False

    @pytest.mark.asyncio
    async def test_given_consent_returns_true(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("user123", ProcessingPurpose.CONSENT, True)

        result = await gdpr.has_consent("user123", ProcessingPurpose.CONSENT)
        assert result is True

    @pytest.mark.asyncio
    async def test_withdrawn_consent_returns_false(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("user123", ProcessingPurpose.CONSENT, True)
        await gdpr.record_consent("user123", ProcessingPurpose.CONSENT, False)

        result = await gdpr.has_consent("user123", ProcessingPurpose.CONSENT)
        assert result is False

    @pytest.mark.asyncio
    async def test_expired_consent_returns_false(self):
        gdpr = GDPRCompliance()
        # Record consent that expires immediately
        consent = await gdpr.record_consent(
            "user123",
            ProcessingPurpose.CONSENT,
            True,
            expires_in_days=1,
        )
        # Manually set to past
        consent.expires_at = datetime.now(UTC) - timedelta(hours=1)

        result = await gdpr.has_consent("user123", ProcessingPurpose.CONSENT)
        assert result is False

    @pytest.mark.asyncio
    async def test_consent_for_different_purpose_not_checked(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("user123", ProcessingPurpose.CONSENT, True)

        result = await gdpr.has_consent("user123", ProcessingPurpose.CONTRACT)
        assert result is False

    @pytest.mark.asyncio
    async def test_consent_for_different_user_not_checked(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("user456", ProcessingPurpose.CONSENT, True)

        result = await gdpr.has_consent("user123", ProcessingPurpose.CONSENT)
        assert result is False


# ─── handle_access_request ────────────────────────────────────────────────────


class TestHandleAccessRequest:
    """Tests for handle_access_request method."""

    @pytest.mark.asyncio
    async def test_access_request_returns_user_data(self):
        gdpr = GDPRCompliance()
        data = await gdpr.handle_access_request("user123")

        assert "user_id" in data
        assert data["user_id"] == "user123"
        assert "data_collected_at" in data
        assert "stored_data" in data
        assert "consent_records" in data
        assert "processing_purposes" in data

    @pytest.mark.asyncio
    async def test_access_request_includes_consent_records(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("user123", ProcessingPurpose.CONSENT, True)
        await gdpr.record_consent("user456", ProcessingPurpose.CONTRACT, True)  # Different user

        data = await gdpr.handle_access_request("user123")

        assert len(data["consent_records"]) == 1
        assert data["consent_records"][0]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_access_request_includes_stored_data(self):
        gdpr = GDPRCompliance()
        gdpr._data_store["user123"] = {"name": "John Doe", "email": "john@example.com"}

        data = await gdpr.handle_access_request("user123")
        assert data["stored_data"] == {"name": "John Doe", "email": "john@example.com"}

    @pytest.mark.asyncio
    async def test_access_request_empty_user(self):
        gdpr = GDPRCompliance()
        data = await gdpr.handle_access_request("nonexistent_user")

        assert data["user_id"] == "nonexistent_user"
        assert data["stored_data"] == {}
        assert data["consent_records"] == []


# ─── handle_rectification_request ────────────────────────────────────────────


class TestHandleRectificationRequest:
    """Tests for handle_rectification_request method."""

    @pytest.mark.asyncio
    async def test_rectification_creates_data_for_new_user(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_rectification_request(
            "user123",
            {"email": "new@example.com"},
        )

        assert result is True
        assert gdpr._data_store["user123"]["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_rectification_updates_existing_data(self):
        gdpr = GDPRCompliance()
        gdpr._data_store["user123"] = {"email": "old@example.com", "name": "Old Name"}

        await gdpr.handle_rectification_request("user123", {"email": "new@example.com"})

        assert gdpr._data_store["user123"]["email"] == "new@example.com"
        assert gdpr._data_store["user123"]["name"] == "Old Name"  # Unchanged

    @pytest.mark.asyncio
    async def test_rectification_sets_last_updated(self):
        gdpr = GDPRCompliance()
        before = datetime.now(UTC)

        await gdpr.handle_rectification_request("user123", {"email": "new@example.com"})

        last_updated = gdpr._data_store["user123"]["last_updated"]
        updated_dt = datetime.fromisoformat(last_updated)
        assert updated_dt >= before

    @pytest.mark.asyncio
    async def test_rectification_returns_true(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_rectification_request("user123", {"key": "value"})
        assert result is True


# ─── handle_erasure_request ───────────────────────────────────────────────────


class TestHandleErasureRequest:
    """Tests for handle_erasure_request method."""

    @pytest.mark.asyncio
    async def test_erasure_removes_stored_data(self):
        gdpr = GDPRCompliance()
        gdpr._data_store["user123"] = {"name": "John", "email": "john@example.com"}

        result = await gdpr.handle_erasure_request("user123")

        assert result is True
        assert "user123" not in gdpr._data_store

    @pytest.mark.asyncio
    async def test_erasure_nonexistent_user_no_error(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_erasure_request("nonexistent_user")
        assert result is True

    @pytest.mark.asyncio
    async def test_erasure_anonymizes_consent_records(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("user123", ProcessingPurpose.CONSENT, True)

        await gdpr.handle_erasure_request("user123")

        # Consent records should be anonymized
        for consent in gdpr._consent_records:
            assert consent.user_id != "user123"
            assert "anonymized_" in consent.user_id

    @pytest.mark.asyncio
    async def test_erasure_with_reason(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_erasure_request(
            "user123",
            reason="User requested account deletion",
        )
        assert result is True


# ─── handle_portability_request ──────────────────────────────────────────────


class TestHandlePortabilityRequest:
    """Tests for handle_portability_request method."""

    @pytest.mark.asyncio
    async def test_portability_json_format(self):
        gdpr = GDPRCompliance()
        gdpr._data_store["user123"] = {"name": "John"}

        result = await gdpr.handle_portability_request("user123", format="json")

        import json

        assert isinstance(result, str)
        data = json.loads(result)
        assert data["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_portability_csv_format(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_portability_request("user123", format="csv")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_portability_xml_format(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_portability_request("user123", format="xml")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_portability_default_format(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_portability_request("user123")
        # Default is json
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_portability_unknown_format_returns_dict(self):
        gdpr = GDPRCompliance()
        result = await gdpr.handle_portability_request("user123", format="unknown")
        assert isinstance(result, dict)


# ─── record_processing_activity ──────────────────────────────────────────────


class TestRecordProcessingActivity:
    """Tests for record_processing_activity method."""

    @pytest.mark.asyncio
    async def test_record_processing_activity(self):
        gdpr = GDPRCompliance()
        record = await gdpr.record_processing_activity(
            controller="Acme Corp",
            purpose=ProcessingPurpose.CONTRACT,
            data_categories=[DataCategory.BASIC_IDENTITY],
            data_subjects=["customers"],
            retention_period="7 years",
            security_measures=["encryption", "access_control"],
        )

        assert isinstance(record, DataProcessingRecord)
        assert record.controller == "Acme Corp"
        assert record.purpose == ProcessingPurpose.CONTRACT
        assert record.record_id.startswith("rec_")

    @pytest.mark.asyncio
    async def test_record_processing_activity_appended(self):
        gdpr = GDPRCompliance()
        await gdpr.record_processing_activity(
            controller="Acme",
            purpose=ProcessingPurpose.CONTRACT,
            data_categories=[DataCategory.BASIC_IDENTITY],
            data_subjects=["customers"],
            retention_period="1 year",
            security_measures=["encryption"],
        )

        assert len(gdpr._processing_records) == 1

    @pytest.mark.asyncio
    async def test_record_processing_with_recipients(self):
        gdpr = GDPRCompliance()
        record = await gdpr.record_processing_activity(
            controller="Acme",
            purpose=ProcessingPurpose.LEGITIMATE_INTERESTS,
            data_categories=[DataCategory.BEHAVIORAL],
            data_subjects=["website_visitors"],
            retention_period="2 years",
            security_measures=["pseudonymization"],
            recipients=["Analytics Provider"],
            third_country_transfers=True,
        )

        assert record.recipients == ["Analytics Provider"]
        assert record.third_country_transfers is True


# ─── report_data_breach ───────────────────────────────────────────────────────


class TestReportDataBreach:
    """Tests for report_data_breach method."""

    @pytest.mark.asyncio
    async def test_report_low_severity_breach(self):
        gdpr = GDPRCompliance()
        breach = await gdpr.report_data_breach(
            severity=BreachSeverity.LOW,
            affected_users=10,
            data_categories=[DataCategory.BASIC_IDENTITY],
            description="Minor incident",
            consequences="Minimal risk",
            measures_taken=["Password reset"],
        )

        assert isinstance(breach, DataBreachRecord)
        assert breach.severity == BreachSeverity.LOW
        assert breach.affected_users == 10
        assert breach.breach_id.startswith("breach_")

    @pytest.mark.asyncio
    async def test_report_critical_breach(self):
        gdpr = GDPRCompliance()
        breach = await gdpr.report_data_breach(
            severity=BreachSeverity.CRITICAL,
            affected_users=100000,
            data_categories=[DataCategory.FINANCIAL, DataCategory.HEALTH],
            description="Major data breach",
            consequences="High risk of identity theft",
            measures_taken=["System shutdown", "Law enforcement notified"],
        )

        assert breach.severity == BreachSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_report_high_severity_breach(self):
        gdpr = GDPRCompliance()
        breach = await gdpr.report_data_breach(
            severity=BreachSeverity.HIGH,
            affected_users=1000,
            data_categories=[DataCategory.BASIC_IDENTITY],
            description="Significant breach",
            consequences="Risk to rights and freedoms",
            measures_taken=["Patches applied"],
        )

        assert breach.severity == BreachSeverity.HIGH

    @pytest.mark.asyncio
    async def test_breach_appended_to_records(self):
        gdpr = GDPRCompliance()
        await gdpr.report_data_breach(
            severity=BreachSeverity.LOW,
            affected_users=5,
            data_categories=[DataCategory.COMMUNICATION],
            description="Test breach",
            consequences="Minimal",
            measures_taken=["Notification sent"],
        )

        assert len(gdpr._breach_records) == 1


# ─── generate_compliance_report ──────────────────────────────────────────────


class TestGenerateComplianceReport:
    """Tests for generate_compliance_report method."""

    @pytest.mark.asyncio
    async def test_empty_report(self):
        gdpr = GDPRCompliance()
        report = await gdpr.generate_compliance_report()

        assert "timestamp" in report
        assert report["total_consents"] == 0
        assert report["active_consents"] == 0
        assert report["consent_rate"] == 0
        assert report["processing_activities"] == 0
        assert report["data_breaches"] == 0
        assert report["high_severity_breaches"] == 0

    @pytest.mark.asyncio
    async def test_report_with_active_consents(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("u1", ProcessingPurpose.CONSENT, True)
        await gdpr.record_consent("u2", ProcessingPurpose.CONTRACT, True)
        await gdpr.record_consent("u3", ProcessingPurpose.CONSENT, False)  # Withdrawn

        report = await gdpr.generate_compliance_report()

        assert report["total_consents"] == 3
        assert report["active_consents"] == 2

    @pytest.mark.asyncio
    async def test_report_with_breaches(self):
        gdpr = GDPRCompliance()
        await gdpr.report_data_breach(
            severity=BreachSeverity.LOW,
            affected_users=5,
            data_categories=[DataCategory.BASIC_IDENTITY],
            description="Test",
            consequences="Minimal",
            measures_taken=["Notification"],
        )
        await gdpr.report_data_breach(
            severity=BreachSeverity.HIGH,
            affected_users=1000,
            data_categories=[DataCategory.FINANCIAL],
            description="Test high",
            consequences="Risk",
            measures_taken=["Containment"],
        )

        report = await gdpr.generate_compliance_report()

        assert report["data_breaches"] == 2
        assert report["high_severity_breaches"] == 1

    @pytest.mark.asyncio
    async def test_consent_rate_calculation(self):
        gdpr = GDPRCompliance()
        await gdpr.record_consent("u1", ProcessingPurpose.CONSENT, True)
        await gdpr.record_consent("u2", ProcessingPurpose.CONSENT, True)
        await gdpr.record_consent("u3", ProcessingPurpose.CONSENT, False)

        report = await gdpr.generate_compliance_report()

        # 2 out of 3 active
        assert abs(report["consent_rate"] - 2 / 3) < 0.01

    @pytest.mark.asyncio
    async def test_report_with_processing_activities(self):
        gdpr = GDPRCompliance()
        await gdpr.record_processing_activity(
            controller="Acme",
            purpose=ProcessingPurpose.CONTRACT,
            data_categories=[DataCategory.BASIC_IDENTITY],
            data_subjects=["customers"],
            retention_period="7 years",
            security_measures=["encryption"],
        )

        report = await gdpr.generate_compliance_report()
        assert report["processing_activities"] == 1


# Need to import MagicMock for the multiple instances test
from unittest.mock import MagicMock  # noqa: E402
