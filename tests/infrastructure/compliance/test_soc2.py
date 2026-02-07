"""Tests for SOC 2 Trust Service Criteria Implementation."""

import pytest
from datetime import UTC, datetime

from src.infrastructure.compliance.soc2 import (
    SOC2Compliance,
    ChangeType,
    ChangeStatus,
    TrustServiceCriteria,
)


class TestSOC2Compliance:
    """Test SOC 2 compliance controls."""

    @pytest.fixture
    def soc2(self):
        """Create SOC 2 compliance instance."""
        return SOC2Compliance()

    @pytest.mark.asyncio
    async def test_request_change(self, soc2):
        """Test change request creation."""
        change = await soc2.request_change(
            change_type=ChangeType.CONFIGURATION,
            description="Update rate limiting settings",
            requestor="dev_team",
            rollback_plan="Revert to previous settings",
        )

        assert change.change_type == ChangeType.CONFIGURATION
        assert change.description == "Update rate limiting settings"
        assert change.requestor == "dev_team"
        assert change.status == ChangeStatus.REQUESTED
        assert change.rollback_plan == "Revert to previous settings"

    @pytest.mark.asyncio
    async def test_approve_change(self, soc2):
        """Test change approval."""
        # Request change
        change = await soc2.request_change(
            change_type=ChangeType.CODE_DEPLOYMENT,
            description="Deploy v2.0",
            requestor="dev_team",
        )

        # Approve change
        approved = await soc2.approve_change(
            change_id=change.change_id,
            approver="admin",
            testing_notes="Tested in staging environment",
        )

        assert approved.status == ChangeStatus.APPROVED
        assert approved.approver == "admin"
        assert approved.testing_notes == "Tested in staging environment"

    @pytest.mark.asyncio
    async def test_implement_change(self, soc2):
        """Test change implementation."""
        # Request and approve change
        change = await soc2.request_change(
            change_type=ChangeType.CONFIGURATION,
            description="Update settings",
            requestor="dev_team",
        )

        await soc2.approve_change(
            change_id=change.change_id,
            approver="admin",
        )

        # Implement change
        implemented = await soc2.implement_change(change_id=change.change_id)

        assert implemented.status == ChangeStatus.IMPLEMENTED
        assert implemented.implemented_at is not None

    @pytest.mark.asyncio
    async def test_implement_unapproved_change_fails(self, soc2):
        """Test that implementing unapproved change fails."""
        # Request change (but don't approve)
        change = await soc2.request_change(
            change_type=ChangeType.CONFIGURATION,
            description="Update settings",
            requestor="dev_team",
        )

        # Try to implement without approval (should fail)
        with pytest.raises(ValueError):
            await soc2.implement_change(change_id=change.change_id)

    @pytest.mark.asyncio
    async def test_record_monitoring_event(self, soc2):
        """Test system monitoring event recording."""
        event = await soc2.record_monitoring_event(
            metric_name="cpu_usage",
            metric_value=75.5,
            threshold=80.0,
        )

        assert event.metric_name == "cpu_usage"
        assert event.metric_value == 75.5
        assert event.threshold == 80.0
        assert event.alert_triggered is False  # Below threshold

    @pytest.mark.asyncio
    async def test_monitoring_alert_triggered(self, soc2):
        """Test monitoring alert when threshold exceeded."""
        event = await soc2.record_monitoring_event(
            metric_name="cpu_usage",
            metric_value=85.0,
            threshold=80.0,
        )

        assert event.alert_triggered is True  # Above threshold

    @pytest.mark.asyncio
    async def test_record_uptime(self, soc2):
        """Test availability tracking."""
        record = await soc2.record_uptime(
            service="api",
            uptime_seconds=86100,  # 23 hours 55 minutes
            downtime_seconds=300,  # 5 minutes
            incident_count=1,
        )

        assert record.service == "api"
        assert record.uptime_seconds == 86100
        assert record.downtime_seconds == 300
        assert record.incident_count == 1
        assert record.availability_percentage > 99.0

    @pytest.mark.asyncio
    async def test_calculate_availability_sla(self, soc2):
        """Test SLA calculation."""
        # Record uptime for service
        await soc2.record_uptime(
            service="api",
            uptime_seconds=86100,
            downtime_seconds=300,
        )

        await soc2.record_uptime(
            service="api",
            uptime_seconds=86000,
            downtime_seconds=400,
        )

        # Calculate SLA
        sla = await soc2.calculate_availability_sla(
            service="api",
            period_days=30,
        )

        assert sla["service"] == "api"
        assert "availability_percentage" in sla
        assert "total_uptime_seconds" in sla
        assert "total_downtime_seconds" in sla
        assert "meets_sla" in sla

    @pytest.mark.asyncio
    async def test_audit_access(self, soc2):
        """Test access control audit."""
        audit = await soc2.audit_access(
            user_id="user123",
            access_level="admin",
            review_interval_days=90,
        )

        assert audit.user_id == "user123"
        assert audit.access_level == "admin"
        assert audit.next_review > audit.last_review
        assert audit.is_compliant is True

    @pytest.mark.asyncio
    async def test_admin_quarterly_review_required(self, soc2):
        """Test that admin access requires quarterly review."""
        # Try to set admin access with 180-day review (should fail compliance)
        audit = await soc2.audit_access(
            user_id="user123",
            access_level="admin",
            review_interval_days=180,
        )

        # Should not be compliant (admins need quarterly review)
        assert audit.is_compliant is False
        assert audit.violations is not None

    @pytest.mark.asyncio
    async def test_verify_controls(self, soc2):
        """Test control verification."""
        controls = await soc2.verify_controls()

        assert controls["cc4_monitoring_enabled"] is True
        assert controls["cc6_access_audits_enabled"] is True
        assert controls["cc8_change_management_enabled"] is True
        assert controls["availability_tracking_enabled"] is True

    @pytest.mark.asyncio
    async def test_compliance_report(self, soc2):
        """Test compliance report generation."""
        # Create some data
        change = await soc2.request_change(
            change_type=ChangeType.CONFIGURATION,
            description="Update settings",
            requestor="dev_team",
        )

        await soc2.approve_change(change_id=change.change_id, approver="admin")

        await soc2.record_monitoring_event(
            metric_name="cpu_usage",
            metric_value=75.0,
        )

        await soc2.audit_access(
            user_id="user123",
            access_level="user",
        )

        # Generate report
        report = await soc2.generate_compliance_report()

        assert "timestamp" in report
        assert "change_management" in report
        assert "monitoring" in report
        assert "access_control" in report
        assert "compliance_status" in report

        assert report["change_management"]["total_changes"] >= 1
        assert report["monitoring"]["total_events"] >= 1
        assert report["access_control"]["total_audits"] >= 1
        assert report["compliance_status"] is True

    @pytest.mark.asyncio
    async def test_change_workflow(self, soc2):
        """Test complete change management workflow."""
        # Request change
        change = await soc2.request_change(
            change_type=ChangeType.CODE_DEPLOYMENT,
            description="Deploy new feature",
            requestor="developer",
            rollback_plan="Revert commit",
        )

        assert change.status == ChangeStatus.REQUESTED

        # Approve change
        await soc2.approve_change(
            change_id=change.change_id,
            approver="manager",
            testing_notes="All tests passed",
        )

        change = soc2._find_change(change.change_id)
        assert change.status == ChangeStatus.APPROVED

        # Implement change
        await soc2.implement_change(change_id=change.change_id)

        change = soc2._find_change(change.change_id)
        assert change.status == ChangeStatus.IMPLEMENTED
        assert change.implemented_at is not None

    @pytest.mark.asyncio
    async def test_sla_meets_target(self, soc2):
        """Test that 99.9% SLA target is correctly calculated."""
        # Record high availability (99.95%)
        await soc2.record_uptime(
            service="api",
            uptime_seconds=86356,  # 99.95% of 24 hours
            downtime_seconds=44,
        )

        sla = await soc2.calculate_availability_sla(service="api", period_days=1)

        assert sla["meets_sla"] is True
        assert sla["availability_percentage"] >= 99.9
