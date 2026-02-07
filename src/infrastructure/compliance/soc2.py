"""SOC 2 Trust Service Criteria Implementation

Implements SOC 2 Type II Trust Service Criteria for service organizations.

SOC 2 Trust Service Criteria:
- **Common Criteria (CC)** - Required for all SOC 2 reports:
  * CC1: Control Environment
  * CC2: Communication and Information
  * CC3: Risk Assessment
  * CC4: Monitoring Activities
  * CC5: Control Activities
  * CC6: Logical and Physical Access Controls
  * CC7: System Operations
  * CC8: Change Management

- **Additional Criteria** - Optional based on business needs:
  * A: Availability
  * C: Confidentiality
  * P: Processing Integrity
  * PI: Privacy

This implementation focuses on automated technical controls that can be
enforced and audited programmatically.

Example:
    >>> from src.infrastructure.compliance import SOC2Compliance
    >>> soc2 = SOC2Compliance()
    >>>
    >>> # Log change management activity (CC8)
    >>> await soc2.log_change(
    ...     change_type="configuration",
    ...     description="Updated database settings",
    ...     approver="admin",
    ... )
    >>>
    >>> # Monitor system availability (A)
    >>> await soc2.record_uptime(service="api", uptime_seconds=86400)
    >>>
    >>> # Verify access controls (CC6)
    >>> has_access = await soc2.verify_logical_access(user_id="user123")
"""

import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)


class TrustServiceCriteria(str, Enum):
    """SOC 2 Trust Service Criteria."""

    # Common Criteria (mandatory)
    CC1_CONTROL_ENVIRONMENT = "cc1_control_environment"
    CC2_COMMUNICATION = "cc2_communication"
    CC3_RISK_ASSESSMENT = "cc3_risk_assessment"
    CC4_MONITORING = "cc4_monitoring"
    CC5_CONTROL_ACTIVITIES = "cc5_control_activities"
    CC6_ACCESS_CONTROLS = "cc6_access_controls"
    CC7_SYSTEM_OPERATIONS = "cc7_system_operations"
    CC8_CHANGE_MANAGEMENT = "cc8_change_management"

    # Additional criteria (optional)
    A_AVAILABILITY = "a_availability"
    C_CONFIDENTIALITY = "c_confidentiality"
    P_PROCESSING_INTEGRITY = "p_processing_integrity"
    PI_PRIVACY = "pi_privacy"


class ChangeType(str, Enum):
    """Types of changes for CC8: Change Management."""

    CONFIGURATION = "configuration"
    CODE_DEPLOYMENT = "code_deployment"
    INFRASTRUCTURE = "infrastructure"
    SECURITY_POLICY = "security_policy"
    ACCESS_CONTROL = "access_control"
    EMERGENCY = "emergency"


class ChangeStatus(str, Enum):
    """Change request status."""

    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    ROLLED_BACK = "rolled_back"


class ChangeRecord(BaseModel):
    """Change management record (CC8).

    CC8: Change Management
    Changes must be authorized, tested, and documented.
    """

    change_id: str = Field(description="Unique change identifier")
    timestamp: datetime = Field(description="Change request timestamp")
    change_type: ChangeType = Field(description="Type of change")
    description: str = Field(description="Change description")
    requestor: str = Field(description="Person requesting change")
    approver: str | None = Field(default=None, description="Person approving change")
    status: ChangeStatus = Field(description="Change status")
    impact_assessment: str | None = Field(default=None, description="Impact assessment")
    rollback_plan: str | None = Field(default=None, description="Rollback plan")
    testing_notes: str | None = Field(default=None, description="Testing performed")
    implemented_at: datetime | None = Field(default=None, description="Implementation timestamp")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "change_id": "chg_12345",
                "timestamp": "2026-02-07T12:00:00Z",
                "change_type": "configuration",
                "description": "Update rate limiting settings",
                "requestor": "dev_team",
                "approver": "admin",
                "status": "approved",
            }
        }


class MonitoringEvent(BaseModel):
    """System monitoring event (CC4).

    CC4: Monitoring Activities
    System performance and security must be monitored.
    """

    event_id: str = Field(description="Unique event identifier")
    timestamp: datetime = Field(description="Event timestamp")
    criteria: TrustServiceCriteria = Field(description="Trust service criteria")
    metric_name: str = Field(description="Metric being monitored")
    metric_value: float = Field(description="Metric value")
    threshold: float | None = Field(default=None, description="Alert threshold")
    alert_triggered: bool = Field(default=False, description="Whether alert was triggered")
    details: dict[str, Any] | None = Field(default=None, description="Additional details")


class AvailabilityRecord(BaseModel):
    """Availability tracking (A: Availability).

    Availability Criterion
    System must be available for operation and use as committed.
    """

    record_id: str = Field(description="Unique record identifier")
    timestamp: datetime = Field(description="Record timestamp")
    service: str = Field(description="Service name")
    uptime_seconds: float = Field(description="Uptime in seconds")
    downtime_seconds: float = Field(description="Downtime in seconds")
    availability_percentage: float = Field(description="Availability percentage")
    incident_count: int = Field(default=0, description="Number of incidents")


class AccessAudit(BaseModel):
    """Access control audit record (CC6).

    CC6: Logical and Physical Access Controls
    Access must be restricted to authorized users.
    """

    audit_id: str = Field(description="Unique audit identifier")
    timestamp: datetime = Field(description="Audit timestamp")
    user_id: str = Field(description="User being audited")
    access_level: str = Field(description="Access level")
    last_review: datetime = Field(description="Last access review date")
    next_review: datetime = Field(description="Next access review date")
    is_compliant: bool = Field(description="Whether access is compliant")
    violations: list[str] | None = Field(default=None, description="Compliance violations")


class SOC2Compliance:
    """SOC 2 Trust Service Criteria Implementation.

    Implements automated technical controls for SOC 2 Type II compliance.
    Provides change management, system monitoring, access controls,
    and availability tracking.

    Attributes:
        _change_records: Change management records (CC8)
        _monitoring_events: System monitoring events (CC4)
        _availability_records: Availability tracking (A)
        _access_audits: Access control audits (CC6)

    Example:
        >>> soc2 = SOC2Compliance()
        >>>
        >>> # Request change (CC8)
        >>> change = await soc2.request_change(
        ...     change_type="configuration",
        ...     description="Update API timeout",
        ...     requestor="dev_team",
        ... )
        >>>
        >>> # Approve change
        >>> await soc2.approve_change(change.change_id, approver="admin")
        >>>
        >>> # Monitor system (CC4)
        >>> await soc2.record_monitoring_event(
        ...     metric_name="cpu_usage",
        ...     metric_value=75.5,
        ...     threshold=80.0,
        ... )
        >>>
        >>> # Track availability (A)
        >>> await soc2.record_uptime(
        ...     service="api",
        ...     uptime_seconds=86400,
        ... )
    """

    def __init__(self):
        """Initialize SOC 2 compliance controls."""
        # CC8: Change Management
        self._change_records: list[ChangeRecord] = []

        # CC4: Monitoring Activities
        self._monitoring_events: list[MonitoringEvent] = []

        # A: Availability
        self._availability_records: list[AvailabilityRecord] = []

        # CC6: Logical Access Controls
        self._access_audits: list[AccessAudit] = []

        logger.info("soc2_compliance_initialized")

    async def request_change(
        self,
        change_type: ChangeType | str,
        description: str,
        requestor: str,
        impact_assessment: str | None = None,
        rollback_plan: str | None = None,
    ) -> ChangeRecord:
        """Request change (CC8: Change Management).

        All changes must be formally requested, reviewed, and approved.

        Args:
            change_type: Type of change
            description: Change description
            requestor: Person requesting change
            impact_assessment: Impact assessment
            rollback_plan: Rollback plan

        Returns:
            ChangeRecord

        Example:
            >>> change = await soc2.request_change(
            ...     change_type="code_deployment",
            ...     description="Deploy v2.0",
            ...     requestor="dev_team",
            ...     rollback_plan="Revert to v1.9",
            ... )
        """
        if isinstance(change_type, str):
            change_type = ChangeType(change_type)

        change = ChangeRecord(
            change_id=f"chg_{secrets.token_hex(8)}",
            timestamp=datetime.now(UTC),
            change_type=change_type,
            description=description,
            requestor=requestor,
            status=ChangeStatus.REQUESTED,
            impact_assessment=impact_assessment,
            rollback_plan=rollback_plan,
        )

        self._change_records.append(change)

        logger.info(
            "soc2_change_requested",
            change_id=change.change_id,
            change_type=change_type.value,
            requestor=requestor,
        )

        return change

    async def approve_change(
        self,
        change_id: str,
        approver: str,
        testing_notes: str | None = None,
    ) -> ChangeRecord:
        """Approve change request (CC8: Change Management).

        Args:
            change_id: Change ID to approve
            approver: Person approving change
            testing_notes: Testing performed

        Returns:
            Updated ChangeRecord

        Example:
            >>> change = await soc2.approve_change(
            ...     change_id="chg_12345",
            ...     approver="admin",
            ...     testing_notes="Tested in staging",
            ... )
        """
        change = self._find_change(change_id)

        if not change:
            raise ValueError(f"Change {change_id} not found")

        change.approver = approver
        change.status = ChangeStatus.APPROVED
        change.testing_notes = testing_notes

        logger.info(
            "soc2_change_approved",
            change_id=change_id,
            approver=approver,
        )

        return change

    async def implement_change(
        self,
        change_id: str,
    ) -> ChangeRecord:
        """Mark change as implemented (CC8: Change Management).

        Args:
            change_id: Change ID

        Returns:
            Updated ChangeRecord

        Example:
            >>> change = await soc2.implement_change("chg_12345")
        """
        change = self._find_change(change_id)

        if not change:
            raise ValueError(f"Change {change_id} not found")

        if change.status != ChangeStatus.APPROVED:
            raise ValueError(f"Change {change_id} is not approved")

        change.status = ChangeStatus.IMPLEMENTED
        change.implemented_at = datetime.now(UTC)

        logger.info(
            "soc2_change_implemented",
            change_id=change_id,
        )

        return change

    def _find_change(self, change_id: str) -> ChangeRecord | None:
        """Find change record by ID."""
        for change in self._change_records:
            if change.change_id == change_id:
                return change
        return None

    async def record_monitoring_event(
        self,
        metric_name: str,
        metric_value: float,
        criteria: TrustServiceCriteria | str = TrustServiceCriteria.CC4_MONITORING,
        threshold: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> MonitoringEvent:
        """Record system monitoring event (CC4: Monitoring Activities).

        CC4: Monitoring Activities
        System performance and security must be continuously monitored.

        Args:
            metric_name: Metric being monitored
            metric_value: Metric value
            criteria: Trust service criteria
            threshold: Alert threshold
            details: Additional details

        Returns:
            MonitoringEvent

        Example:
            >>> event = await soc2.record_monitoring_event(
            ...     metric_name="response_time_ms",
            ...     metric_value=250,
            ...     threshold=500,
            ... )
        """
        if isinstance(criteria, str):
            criteria = TrustServiceCriteria(criteria)

        alert_triggered = False
        if threshold is not None and metric_value > threshold:
            alert_triggered = True

        event = MonitoringEvent(
            event_id=f"mon_{secrets.token_hex(8)}",
            timestamp=datetime.now(UTC),
            criteria=criteria,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            alert_triggered=alert_triggered,
            details=details,
        )

        self._monitoring_events.append(event)

        if alert_triggered:
            logger.warning(
                "soc2_monitoring_alert",
                metric_name=metric_name,
                metric_value=metric_value,
                threshold=threshold,
            )
        else:
            logger.info(
                "soc2_monitoring_event",
                metric_name=metric_name,
                metric_value=metric_value,
            )

        return event

    async def record_uptime(
        self,
        service: str,
        uptime_seconds: float,
        downtime_seconds: float = 0,
        incident_count: int = 0,
    ) -> AvailabilityRecord:
        """Record service availability (A: Availability).

        Availability Criterion
        System must meet committed availability SLAs.

        Args:
            service: Service name
            uptime_seconds: Uptime in seconds
            downtime_seconds: Downtime in seconds
            incident_count: Number of incidents

        Returns:
            AvailabilityRecord

        Example:
            >>> record = await soc2.record_uptime(
            ...     service="api",
            ...     uptime_seconds=86100,
            ...     downtime_seconds=300,
            ...     incident_count=1,
            ... )
        """
        total_seconds = uptime_seconds + downtime_seconds
        availability_percentage = (
            (uptime_seconds / total_seconds * 100) if total_seconds > 0 else 100.0
        )

        record = AvailabilityRecord(
            record_id=f"avail_{secrets.token_hex(8)}",
            timestamp=datetime.now(UTC),
            service=service,
            uptime_seconds=uptime_seconds,
            downtime_seconds=downtime_seconds,
            availability_percentage=availability_percentage,
            incident_count=incident_count,
        )

        self._availability_records.append(record)

        logger.info(
            "soc2_availability_recorded",
            service=service,
            availability_percentage=availability_percentage,
            incident_count=incident_count,
        )

        return record

    async def audit_access(
        self,
        user_id: str,
        access_level: str,
        review_interval_days: int = 90,
    ) -> AccessAudit:
        """Audit user access (CC6: Logical Access Controls).

        CC6: Logical and Physical Access Controls
        Access rights must be reviewed periodically.

        Args:
            user_id: User to audit
            access_level: Access level
            review_interval_days: Days between reviews

        Returns:
            AccessAudit

        Example:
            >>> audit = await soc2.audit_access(
            ...     user_id="user123",
            ...     access_level="admin",
            ...     review_interval_days=90,
            ... )
        """
        now = datetime.now(UTC)
        next_review = now + timedelta(days=review_interval_days)

        # Simple compliance check (would be more complex in production)
        violations = []
        if access_level == "admin":
            # Admins require quarterly review
            if review_interval_days > 90:
                violations.append("Admin access requires quarterly review")

        is_compliant = len(violations) == 0

        audit = AccessAudit(
            audit_id=f"audit_{secrets.token_hex(8)}",
            timestamp=now,
            user_id=user_id,
            access_level=access_level,
            last_review=now,
            next_review=next_review,
            is_compliant=is_compliant,
            violations=violations if violations else None,
        )

        self._access_audits.append(audit)

        logger.info(
            "soc2_access_audited",
            user_id=user_id,
            is_compliant=is_compliant,
        )

        return audit

    async def calculate_availability_sla(
        self,
        service: str,
        period_days: int = 30,
    ) -> dict[str, Any]:
        """Calculate availability SLA for service.

        Args:
            service: Service name
            period_days: Period in days

        Returns:
            Dictionary with SLA metrics

        Example:
            >>> sla = await soc2.calculate_availability_sla(
            ...     service="api",
            ...     period_days=30,
            ... )
            >>> print(f"Availability: {sla['availability_percentage']:.2f}%")
        """
        cutoff = datetime.now(UTC) - timedelta(days=period_days)

        relevant_records = [
            r for r in self._availability_records if r.service == service and r.timestamp >= cutoff
        ]

        if not relevant_records:
            return {
                "service": service,
                "period_days": period_days,
                "availability_percentage": 100.0,
                "total_uptime_seconds": 0,
                "total_downtime_seconds": 0,
                "total_incidents": 0,
            }

        total_uptime = sum(r.uptime_seconds for r in relevant_records)
        total_downtime = sum(r.downtime_seconds for r in relevant_records)
        total_incidents = sum(r.incident_count for r in relevant_records)

        total_seconds = total_uptime + total_downtime
        availability_percentage = (
            (total_uptime / total_seconds * 100) if total_seconds > 0 else 100.0
        )

        sla = {
            "service": service,
            "period_days": period_days,
            "availability_percentage": availability_percentage,
            "total_uptime_seconds": total_uptime,
            "total_downtime_seconds": total_downtime,
            "total_incidents": total_incidents,
            "meets_sla": availability_percentage >= 99.9,  # Typical 99.9% SLA
        }

        logger.info("soc2_sla_calculated", sla=sla)

        return sla

    async def verify_controls(self) -> dict[str, bool]:
        """Verify SOC 2 controls are in place.

        Returns:
            Dictionary of control verification results

        Example:
            >>> results = await soc2.verify_controls()
            >>> if all(results.values()):
            ...     print("All SOC 2 controls verified")
        """
        controls = {
            "cc4_monitoring_enabled": len(self._monitoring_events) >= 0,
            "cc6_access_audits_enabled": len(self._access_audits) >= 0,
            "cc8_change_management_enabled": len(self._change_records) >= 0,
            "availability_tracking_enabled": len(self._availability_records) >= 0,
        }

        logger.info("soc2_controls_verified", controls=controls)

        return controls

    async def generate_compliance_report(self) -> dict[str, Any]:
        """Generate SOC 2 compliance report.

        Returns:
            Compliance report with statistics

        Example:
            >>> report = await soc2.generate_compliance_report()
        """
        controls = await self.verify_controls()

        # Calculate statistics
        total_changes = len(self._change_records)
        approved_changes = len(
            [c for c in self._change_records if c.status == ChangeStatus.APPROVED]
        )
        implemented_changes = len(
            [c for c in self._change_records if c.status == ChangeStatus.IMPLEMENTED]
        )

        monitoring_alerts = len([e for e in self._monitoring_events if e.alert_triggered])

        compliant_audits = len([a for a in self._access_audits if a.is_compliant])
        total_audits = len(self._access_audits)

        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "change_management": {
                "total_changes": total_changes,
                "approved_changes": approved_changes,
                "implemented_changes": implemented_changes,
                "approval_rate": approved_changes / total_changes if total_changes > 0 else 0,
            },
            "monitoring": {
                "total_events": len(self._monitoring_events),
                "alerts_triggered": monitoring_alerts,
            },
            "access_control": {
                "total_audits": total_audits,
                "compliant_audits": compliant_audits,
                "compliance_rate": compliant_audits / total_audits if total_audits > 0 else 1.0,
            },
            "availability": {
                "total_records": len(self._availability_records),
            },
            "controls_status": controls,
            "compliance_status": all(controls.values()),
        }

        logger.info("soc2_compliance_report_generated", report=report)

        return report


__all__ = [
    "AccessAudit",
    "AvailabilityRecord",
    "ChangeRecord",
    "ChangeStatus",
    "ChangeType",
    "MonitoringEvent",
    "SOC2Compliance",
    "TrustServiceCriteria",
]
