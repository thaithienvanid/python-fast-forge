"""Tests for GDPR Data Protection Implementation."""

import pytest
from datetime import UTC, datetime, timedelta

from src.infrastructure.compliance.gdpr import (
    GDPRCompliance,
    ProcessingPurpose,
    DataCategory,
    BreachSeverity,
)


class TestGDPRCompliance:
    """Test GDPR compliance controls."""

    @pytest.fixture
    def gdpr(self):
        """Create GDPR compliance instance."""
        return GDPRCompliance()

    @pytest.mark.asyncio
    async def test_record_consent(self, gdpr):
        """Test consent recording."""
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
            ip_address="192.168.1.100",
            expires_in_days=365,
        )

        assert consent.user_id == "user123"
        assert consent.purpose == "marketing"
        assert consent.consent_given is True
        assert consent.ip_address == "192.168.1.100"
        assert consent.expires_at is not None

    @pytest.mark.asyncio
    async def test_has_consent(self, gdpr):
        """Test consent verification."""
        # Grant consent
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        # Check consent
        has_consent = await gdpr.has_consent("user123", "marketing")
        assert has_consent is True

        # Check different purpose (should be False)
        has_consent = await gdpr.has_consent("user123", "analytics")
        assert has_consent is False

    @pytest.mark.asyncio
    async def test_consent_withdrawal(self, gdpr):
        """Test consent withdrawal."""
        # Grant consent
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        # Withdraw consent
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=False,
        )

        # Check consent (should be False)
        has_consent = await gdpr.has_consent("user123", "marketing")
        assert has_consent is False

    @pytest.mark.asyncio
    async def test_consent_expiration(self, gdpr):
        """Test consent expiration."""
        # Grant consent that expires in the past
        consent = await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
            expires_in_days=-1,  # Already expired
        )

        # Manually set expiration to past
        consent.expires_at = datetime.now(UTC) - timedelta(days=1)

        # Check consent (should be False due to expiration)
        has_consent = await gdpr.has_consent("user123", "marketing")
        assert has_consent is False

    @pytest.mark.asyncio
    async def test_access_request(self, gdpr):
        """Test data subject access request (Article 15)."""
        # Record consent
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        # Handle access request
        data = await gdpr.handle_access_request("user123")

        assert data["user_id"] == "user123"
        assert "data_collected_at" in data
        assert "consent_records" in data
        assert len(data["consent_records"]) > 0

    @pytest.mark.asyncio
    async def test_rectification_request(self, gdpr):
        """Test right to rectification (Article 16)."""
        # Update user data
        result = await gdpr.handle_rectification_request(
            user_id="user123",
            data_updates={"email": "new@example.com", "name": "John Doe"},
        )

        assert result is True

        # Verify data was updated
        data = await gdpr.handle_access_request("user123")
        assert data["stored_data"]["email"] == "new@example.com"
        assert data["stored_data"]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_erasure_request(self, gdpr):
        """Test right to erasure (Article 17)."""
        # Create user data
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        # Handle erasure request
        result = await gdpr.handle_erasure_request(
            user_id="user123",
            reason="User requested account deletion",
        )

        assert result is True

        # Verify data was erased
        data = await gdpr.handle_access_request("user123")
        assert data["stored_data"] == {}

    @pytest.mark.asyncio
    async def test_portability_request(self, gdpr):
        """Test right to data portability (Article 20)."""
        # Create user data
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        # Handle portability request (JSON)
        data_json = await gdpr.handle_portability_request(
            user_id="user123",
            format="json",
        )

        assert isinstance(data_json, str)
        assert "user123" in data_json

    @pytest.mark.asyncio
    async def test_processing_activity_record(self, gdpr):
        """Test recording processing activities (Article 30)."""
        record = await gdpr.record_processing_activity(
            controller="Acme Corp",
            purpose=ProcessingPurpose.CONTRACT,
            data_categories=[DataCategory.BASIC_IDENTITY, DataCategory.FINANCIAL],
            data_subjects=["customers"],
            retention_period="7 years",
            security_measures=["encryption", "access_control"],
        )

        assert record.controller == "Acme Corp"
        assert record.purpose == ProcessingPurpose.CONTRACT
        assert DataCategory.BASIC_IDENTITY in record.data_categories
        assert "encryption" in record.security_measures

    @pytest.mark.asyncio
    async def test_data_breach_reporting(self, gdpr):
        """Test data breach reporting (Article 33-34)."""
        breach = await gdpr.report_data_breach(
            severity=BreachSeverity.HIGH,
            affected_users=1000,
            data_categories=[DataCategory.BASIC_IDENTITY],
            description="Unauthorized database access",
            consequences="Potential identity theft",
            measures_taken=["Passwords reset", "Security audit"],
        )

        assert breach.severity == BreachSeverity.HIGH
        assert breach.affected_users == 1000
        assert "Passwords reset" in breach.measures_taken

    @pytest.mark.asyncio
    async def test_compliance_report(self, gdpr):
        """Test compliance report generation."""
        # Create some consents
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        await gdpr.record_consent(
            user_id="user456",
            purpose="analytics",
            consent_given=True,
        )

        # Generate report
        report = await gdpr.generate_compliance_report()

        assert "timestamp" in report
        assert "total_consents" in report
        assert "active_consents" in report
        assert "consent_rate" in report
        assert report["total_consents"] >= 2

    @pytest.mark.asyncio
    async def test_multiple_purposes(self, gdpr):
        """Test consent for multiple purposes."""
        # Grant consent for multiple purposes
        await gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )

        await gdpr.record_consent(
            user_id="user123",
            purpose="analytics",
            consent_given=True,
        )

        # Check both consents
        has_marketing = await gdpr.has_consent("user123", "marketing")
        has_analytics = await gdpr.has_consent("user123", "analytics")

        assert has_marketing is True
        assert has_analytics is True
