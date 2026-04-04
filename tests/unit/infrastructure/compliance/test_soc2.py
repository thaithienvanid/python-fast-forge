"""Comprehensive tests for the SOC 2 compliance implementation.

Tests cover change management, monitoring, availability tracking, access audits,
SLA calculation, control verification, and compliance reporting.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.compliance.soc2 import (
    ChangeRecord,
    ChangeStatus,
    ChangeType,
    SOC2Compliance,
    TrustServiceCriteria,
)


# ─── Enums ────────────────────────────────────────────────────────────────────


class TestSOC2Enums:
    """Tests for SOC 2 enum values."""

    def test_trust_service_criteria(self):
        criteria = {c.value for c in TrustServiceCriteria}
        # Should contain monitoring criteria
        assert any("cc4" in c or "monitoring" in c for c in criteria)

    def test_change_types(self):
        types = {t.value for t in ChangeType}
        assert len(types) > 0

    def test_change_statuses(self):
        statuses = {s.value for s in ChangeStatus}
        assert "requested" in statuses
        assert "approved" in statuses
        assert "implemented" in statuses


# ─── SOC2Compliance Initialization ────────────────────────────────────────────


class TestSOC2ComplianceInit:
    """Tests for SOC2Compliance initialization."""

    def test_default_init(self):
        soc2 = SOC2Compliance()
        assert soc2._change_records == []
        assert soc2._monitoring_events == []
        assert soc2._availability_records == []
        assert soc2._access_audits == []


# ─── request_change ────────────────────────────────────────────────────────────


class TestRequestChange:
    """Tests for request_change method."""

    @pytest.mark.asyncio
    async def test_request_code_deployment(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(
            change_type=ChangeType.CODE_DEPLOYMENT,
            description="Deploy v2.0",
            requestor="dev_team",
        )

        assert isinstance(change, ChangeRecord)
        assert change.change_type == ChangeType.CODE_DEPLOYMENT
        assert change.description == "Deploy v2.0"
        assert change.requestor == "dev_team"
        assert change.status == ChangeStatus.REQUESTED
        assert change.change_id.startswith("chg_")

    @pytest.mark.asyncio
    async def test_request_change_string_type(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(
            change_type="code_deployment",
            description="Test deploy",
            requestor="dev",
        )
        assert change.change_type == ChangeType.CODE_DEPLOYMENT

    @pytest.mark.asyncio
    async def test_request_change_with_impact_and_rollback(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(
            change_type=ChangeType.CONFIGURATION,
            description="Update timeout",
            requestor="ops_team",
            impact_assessment="Low risk change",
            rollback_plan="Revert config",
        )

        assert change.impact_assessment == "Low risk change"
        assert change.rollback_plan == "Revert config"

    @pytest.mark.asyncio
    async def test_request_change_appended_to_records(self):
        soc2 = SOC2Compliance()
        await soc2.request_change(ChangeType.CODE_DEPLOYMENT, "Deploy A", "dev1")
        await soc2.request_change(ChangeType.CONFIGURATION, "Config B", "ops1")

        assert len(soc2._change_records) == 2


# ─── approve_change ────────────────────────────────────────────────────────────


class TestApproveChange:
    """Tests for approve_change method."""

    @pytest.mark.asyncio
    async def test_approve_change(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(ChangeType.CODE_DEPLOYMENT, "Deploy", "dev")

        approved = await soc2.approve_change(
            change_id=change.change_id,
            approver="manager",
            testing_notes="Tested in staging",
        )

        assert approved.status == ChangeStatus.APPROVED
        assert approved.approver == "manager"
        assert approved.testing_notes == "Tested in staging"

    @pytest.mark.asyncio
    async def test_approve_nonexistent_change_raises(self):
        soc2 = SOC2Compliance()
        with pytest.raises(ValueError, match="not found"):
            await soc2.approve_change("nonexistent_id", "manager")


# ─── implement_change ──────────────────────────────────────────────────────────


class TestImplementChange:
    """Tests for implement_change method."""

    @pytest.mark.asyncio
    async def test_implement_approved_change(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(ChangeType.CODE_DEPLOYMENT, "Deploy", "dev")
        await soc2.approve_change(change.change_id, "manager")

        implemented = await soc2.implement_change(change.change_id)

        assert implemented.status == ChangeStatus.IMPLEMENTED
        assert implemented.implemented_at is not None

    @pytest.mark.asyncio
    async def test_implement_unapproved_change_raises(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(ChangeType.CODE_DEPLOYMENT, "Deploy", "dev")

        with pytest.raises(ValueError, match="not approved"):
            await soc2.implement_change(change.change_id)

    @pytest.mark.asyncio
    async def test_implement_nonexistent_change_raises(self):
        soc2 = SOC2Compliance()
        with pytest.raises(ValueError, match="not found"):
            await soc2.implement_change("nonexistent_id")


# ─── record_monitoring_event ──────────────────────────────────────────────────


class TestRecordMonitoringEvent:
    """Tests for record_monitoring_event method."""

    @pytest.mark.asyncio
    async def test_record_normal_event(self):
        soc2 = SOC2Compliance()
        event = await soc2.record_monitoring_event(
            metric_name="cpu_usage",
            metric_value=50.0,
            threshold=80.0,
        )

        assert event.metric_name == "cpu_usage"
        assert event.metric_value == 50.0
        assert event.threshold == 80.0
        assert event.alert_triggered is False
        assert event.event_id.startswith("mon_")

    @pytest.mark.asyncio
    async def test_record_event_triggers_alert(self):
        soc2 = SOC2Compliance()
        event = await soc2.record_monitoring_event(
            metric_name="response_time",
            metric_value=600,
            threshold=500,
        )

        assert event.alert_triggered is True

    @pytest.mark.asyncio
    async def test_record_event_no_threshold(self):
        soc2 = SOC2Compliance()
        event = await soc2.record_monitoring_event(
            metric_name="request_count",
            metric_value=1000,
        )

        assert event.alert_triggered is False

    @pytest.mark.asyncio
    async def test_record_event_with_details(self):
        soc2 = SOC2Compliance()
        event = await soc2.record_monitoring_event(
            metric_name="error_rate",
            metric_value=0.05,
            details={"error_type": "500", "endpoint": "/api/users"},
        )

        assert event.details is not None

    @pytest.mark.asyncio
    async def test_record_event_string_criteria(self):
        soc2 = SOC2Compliance()
        # Should work with string criteria
        first_criteria = next(iter(TrustServiceCriteria))
        event = await soc2.record_monitoring_event(
            metric_name="test",
            metric_value=1.0,
            criteria=first_criteria.value,
        )
        assert event is not None

    @pytest.mark.asyncio
    async def test_record_event_appended(self):
        soc2 = SOC2Compliance()
        await soc2.record_monitoring_event("cpu", 50.0)
        await soc2.record_monitoring_event("memory", 60.0)

        assert len(soc2._monitoring_events) == 2


# ─── record_uptime ────────────────────────────────────────────────────────────


class TestRecordUptime:
    """Tests for record_uptime method."""

    @pytest.mark.asyncio
    async def test_record_full_uptime(self):
        soc2 = SOC2Compliance()
        record = await soc2.record_uptime(
            service="api",
            uptime_seconds=86400,
            downtime_seconds=0,
        )

        assert record.service == "api"
        assert record.uptime_seconds == 86400
        assert record.availability_percentage == 100.0
        assert record.record_id.startswith("avail_")

    @pytest.mark.asyncio
    async def test_record_partial_uptime(self):
        soc2 = SOC2Compliance()
        record = await soc2.record_uptime(
            service="api",
            uptime_seconds=86100,
            downtime_seconds=300,
        )

        # 86100 / 86400 * 100 = 99.65%
        expected = 86100 / 86400 * 100
        assert abs(record.availability_percentage - expected) < 0.01

    @pytest.mark.asyncio
    async def test_record_uptime_with_incidents(self):
        soc2 = SOC2Compliance()
        record = await soc2.record_uptime(
            service="api",
            uptime_seconds=86100,
            downtime_seconds=300,
            incident_count=2,
        )

        assert record.incident_count == 2

    @pytest.mark.asyncio
    async def test_record_uptime_zero_total(self):
        soc2 = SOC2Compliance()
        record = await soc2.record_uptime(
            service="api",
            uptime_seconds=0,
            downtime_seconds=0,
        )
        assert record.availability_percentage == 100.0


# ─── audit_access ─────────────────────────────────────────────────────────────


class TestAuditAccess:
    """Tests for audit_access method."""

    @pytest.mark.asyncio
    async def test_audit_regular_user(self):
        soc2 = SOC2Compliance()
        audit = await soc2.audit_access(
            user_id="user123",
            access_level="read",
        )

        assert audit.user_id == "user123"
        assert audit.access_level == "read"
        assert audit.is_compliant is True
        assert audit.audit_id.startswith("audit_")

    @pytest.mark.asyncio
    async def test_audit_admin_within_90_days(self):
        soc2 = SOC2Compliance()
        audit = await soc2.audit_access(
            user_id="admin123",
            access_level="admin",
            review_interval_days=90,
        )

        assert audit.is_compliant is True
        assert audit.violations is None

    @pytest.mark.asyncio
    async def test_audit_admin_over_90_days_violation(self):
        soc2 = SOC2Compliance()
        audit = await soc2.audit_access(
            user_id="admin123",
            access_level="admin",
            review_interval_days=120,  # More than 90 days
        )

        assert audit.is_compliant is False
        assert audit.violations is not None
        assert len(audit.violations) > 0

    @pytest.mark.asyncio
    async def test_audit_sets_next_review(self):
        soc2 = SOC2Compliance()
        before = datetime.now(UTC)
        audit = await soc2.audit_access("user123", "read", review_interval_days=90)
        after = datetime.now(UTC)

        expected = before + timedelta(days=90)
        # Allow slight timing differences
        assert abs((audit.next_review - expected).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_audit_appended_to_records(self):
        soc2 = SOC2Compliance()
        await soc2.audit_access("u1", "read")
        await soc2.audit_access("u2", "admin")

        assert len(soc2._access_audits) == 2


# ─── calculate_availability_sla ──────────────────────────────────────────────


class TestCalculateAvailabilitySLA:
    """Tests for calculate_availability_sla method."""

    @pytest.mark.asyncio
    async def test_sla_no_records(self):
        soc2 = SOC2Compliance()
        sla = await soc2.calculate_availability_sla("api", period_days=30)

        assert sla["service"] == "api"
        assert sla["availability_percentage"] == 100.0
        assert sla["total_uptime_seconds"] == 0
        assert sla["total_downtime_seconds"] == 0
        assert sla["total_incidents"] == 0

    @pytest.mark.asyncio
    async def test_sla_with_records(self):
        soc2 = SOC2Compliance()
        await soc2.record_uptime("api", 86100, 300, 1)  # 99.65%

        sla = await soc2.calculate_availability_sla("api", period_days=30)

        assert sla["total_uptime_seconds"] == 86100
        assert sla["total_downtime_seconds"] == 300
        assert sla["total_incidents"] == 1

    @pytest.mark.asyncio
    async def test_sla_meets_999(self):
        soc2 = SOC2Compliance()
        # Add full uptime
        await soc2.record_uptime("api", 86400, 0)

        sla = await soc2.calculate_availability_sla("api")
        assert sla["meets_sla"] is True

    @pytest.mark.asyncio
    async def test_sla_fails_999(self):
        soc2 = SOC2Compliance()
        # Add significant downtime
        await soc2.record_uptime("api", 80000, 6400)  # ~92.6%

        sla = await soc2.calculate_availability_sla("api")
        assert sla["meets_sla"] is False

    @pytest.mark.asyncio
    async def test_sla_filters_by_service(self):
        soc2 = SOC2Compliance()
        await soc2.record_uptime("api", 86400, 0)
        await soc2.record_uptime("database", 86400, 0)

        sla = await soc2.calculate_availability_sla("api")
        # Should only count "api" records
        assert sla["total_uptime_seconds"] == 86400


# ─── verify_controls ─────────────────────────────────────────────────────────


class TestSOC2VerifyControls:
    """Tests for verify_controls method."""

    @pytest.mark.asyncio
    async def test_verify_controls_structure(self):
        soc2 = SOC2Compliance()
        controls = await soc2.verify_controls()

        expected_keys = [
            "cc4_monitoring_enabled",
            "cc6_access_audits_enabled",
            "cc8_change_management_enabled",
            "availability_tracking_enabled",
        ]
        for key in expected_keys:
            assert key in controls

    @pytest.mark.asyncio
    async def test_verify_controls_all_true(self):
        soc2 = SOC2Compliance()
        controls = await soc2.verify_controls()
        assert all(controls.values())


# ─── generate_compliance_report ──────────────────────────────────────────────


class TestSOC2ComplianceReport:
    """Tests for generate_compliance_report method."""

    @pytest.mark.asyncio
    async def test_empty_report(self):
        soc2 = SOC2Compliance()
        report = await soc2.generate_compliance_report()

        assert "timestamp" in report
        assert "change_management" in report
        assert "monitoring" in report
        assert "access_control" in report
        assert "availability" in report
        assert "controls_status" in report
        assert "compliance_status" in report

    @pytest.mark.asyncio
    async def test_report_change_management(self):
        soc2 = SOC2Compliance()
        change = await soc2.request_change(ChangeType.CODE_DEPLOYMENT, "Deploy", "dev")
        await soc2.approve_change(change.change_id, "manager")
        await soc2.implement_change(change.change_id)

        report = await soc2.generate_compliance_report()

        cm = report["change_management"]
        assert cm["total_changes"] == 1
        assert cm["implemented_changes"] == 1

    @pytest.mark.asyncio
    async def test_report_monitoring_alerts(self):
        soc2 = SOC2Compliance()
        await soc2.record_monitoring_event("cpu", 95.0, threshold=80.0)
        await soc2.record_monitoring_event("memory", 60.0, threshold=80.0)

        report = await soc2.generate_compliance_report()
        assert report["monitoring"]["alerts_triggered"] == 1

    @pytest.mark.asyncio
    async def test_report_access_control(self):
        soc2 = SOC2Compliance()
        await soc2.audit_access("u1", "read")
        await soc2.audit_access("u2", "admin", review_interval_days=90)

        report = await soc2.generate_compliance_report()
        ac = report["access_control"]
        assert ac["total_audits"] == 2
        assert ac["compliant_audits"] == 2

    @pytest.mark.asyncio
    async def test_report_compliance_status(self):
        soc2 = SOC2Compliance()
        report = await soc2.generate_compliance_report()
        assert report["compliance_status"] is True

    @pytest.mark.asyncio
    async def test_report_approval_rate(self):
        soc2 = SOC2Compliance()
        change1 = await soc2.request_change(ChangeType.CODE_DEPLOYMENT, "Deploy 1", "dev")
        await soc2.request_change(ChangeType.CONFIGURATION, "Config", "ops")
        await soc2.approve_change(change1.change_id, "manager")

        report = await soc2.generate_compliance_report()
        cm = report["change_management"]
        assert cm["total_changes"] == 2
        assert cm["approved_changes"] == 1
        assert abs(cm["approval_rate"] - 0.5) < 0.01
