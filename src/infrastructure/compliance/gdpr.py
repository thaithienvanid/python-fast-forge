"""GDPR (General Data Protection Regulation) Compliance Implementation

Implements EU GDPR (Regulation 2016/679) data protection controls and data subject rights.

GDPR Requirements:
- Article 6: Lawful basis for processing
- Article 7: Conditions for consent
- Article 15: Right of access by the data subject
- Article 16: Right to rectification
- Article 17: Right to erasure ("right to be forgotten")
- Article 18: Right to restriction of processing
- Article 20: Right to data portability
- Article 21: Right to object
- Article 30: Records of processing activities
- Article 33: Notification of personal data breach
- Article 34: Communication of personal data breach to data subject

This implementation provides:
1. Consent management
2. Data subject rights (access, rectification, erasure, portability, etc.)
3. Data processing records
4. Breach notification procedures
5. Privacy by design controls

Example:
    >>> from src.infrastructure.compliance import GDPRCompliance
    >>> gdpr = GDPRCompliance()
    >>>
    >>> # Record consent
    >>> await gdpr.record_consent(
    ...     user_id="user123",
    ...     purpose="marketing",
    ...     consent_given=True,
    ... )
    >>>
    >>> # Handle data subject access request
    >>> personal_data = await gdpr.handle_access_request(user_id="user123")
    >>>
    >>> # Handle right to erasure
    >>> await gdpr.handle_erasure_request(user_id="user123")
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class ProcessingPurpose(str, Enum):
    """Lawful purposes for data processing (Article 6)."""

    CONTRACT = "contract"  # Performance of a contract
    LEGAL_OBLIGATION = "legal_obligation"  # Compliance with legal obligation
    VITAL_INTERESTS = "vital_interests"  # Protection of vital interests
    PUBLIC_TASK = "public_task"  # Performance of a task in the public interest
    LEGITIMATE_INTERESTS = "legitimate_interests"  # Legitimate interests
    CONSENT = "consent"  # Explicit consent


class DataCategory(str, Enum):
    """Categories of personal data."""

    BASIC_IDENTITY = "basic_identity"  # Name, email, phone
    FINANCIAL = "financial"  # Payment information
    HEALTH = "health"  # Health data (special category)
    BIOMETRIC = "biometric"  # Biometric data (special category)
    LOCATION = "location"  # Location data
    BEHAVIORAL = "behavioral"  # Browsing history, preferences
    COMMUNICATION = "communication"  # Emails, messages


class DataSubjectRight(str, Enum):
    """Data subject rights under GDPR."""

    ACCESS = "access"  # Article 15
    RECTIFICATION = "rectification"  # Article 16
    ERASURE = "erasure"  # Article 17 (right to be forgotten)
    RESTRICTION = "restriction"  # Article 18
    PORTABILITY = "portability"  # Article 20
    OBJECT = "object"  # Article 21


class BreachSeverity(str, Enum):
    """Data breach severity levels."""

    LOW = "low"  # Minimal risk to rights and freedoms
    MEDIUM = "medium"  # Moderate risk
    HIGH = "high"  # High risk - notification required
    CRITICAL = "critical"  # Severe risk - immediate notification


class ConsentRecord(BaseModel):
    """GDPR consent record (Article 7).

    Must be freely given, specific, informed, and unambiguous.
    """

    consent_id: str = Field(description="Unique consent identifier")
    user_id: str = Field(description="User who gave/withdrew consent")
    purpose: ProcessingPurpose | str = Field(description="Purpose of processing")
    consent_given: bool = Field(description="Whether consent was given")
    timestamp: datetime = Field(description="When consent was recorded (UTC)")
    ip_address: str | None = Field(default=None, description="IP address")
    user_agent: str | None = Field(default=None, description="User agent")
    consent_text: str | None = Field(default=None, description="Consent text shown to user")
    expires_at: datetime | None = Field(default=None, description="Consent expiration")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "consent_id": "consent_123",
                "user_id": "user_456",
                "purpose": "marketing",
                "consent_given": True,
                "timestamp": "2026-02-07T12:00:00Z",
            }
        }


class DataProcessingRecord(BaseModel):
    """Record of processing activities (Article 30)."""

    record_id: str = Field(description="Unique record identifier")
    controller: str = Field(description="Data controller")
    purpose: ProcessingPurpose | str = Field(description="Purpose of processing")
    data_categories: list[DataCategory | str] = Field(description="Categories of data")
    data_subjects: list[str] = Field(description="Categories of data subjects")
    recipients: list[str] | None = Field(default=None, description="Recipients of data")
    third_country_transfers: bool = Field(default=False, description="Transfer to third countries")
    retention_period: str = Field(description="Retention period (e.g., '30 days')")
    security_measures: list[str] = Field(description="Technical and organizational measures")
    timestamp: datetime = Field(description="Record creation timestamp")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "record_id": "rec_789",
                "controller": "Acme Corp",
                "purpose": "contract",
                "data_categories": ["basic_identity", "financial"],
                "data_subjects": ["customers"],
                "retention_period": "7 years",
                "security_measures": ["encryption", "access_control"],
                "timestamp": "2026-02-07T12:00:00Z",
            }
        }


class DataBreachRecord(BaseModel):
    """Personal data breach record (Article 33-34)."""

    breach_id: str = Field(description="Unique breach identifier")
    discovered_at: datetime = Field(description="When breach was discovered")
    reported_at: datetime | None = Field(default=None, description="When breach was reported")
    severity: BreachSeverity = Field(description="Breach severity")
    affected_users: int = Field(description="Number of affected data subjects")
    data_categories: list[DataCategory | str] = Field(description="Categories of breached data")
    description: str = Field(description="Nature of the breach")
    consequences: str = Field(description="Likely consequences")
    measures_taken: list[str] = Field(description="Measures taken to address breach")
    dpa_notified: bool = Field(default=False, description="Data Protection Authority notified")
    users_notified: bool = Field(default=False, description="Users notified")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "breach_id": "breach_001",
                "discovered_at": "2026-02-07T12:00:00Z",
                "severity": "high",
                "affected_users": 1000,
                "data_categories": ["basic_identity"],
                "description": "Unauthorized access to user database",
                "consequences": "Potential identity theft",
                "measures_taken": ["Passwords reset", "Users notified"],
                "dpa_notified": True,
                "users_notified": True,
            }
        }


class GDPRCompliance:
    """GDPR Compliance Implementation.

    Implements data protection controls and data subject rights required
    by EU General Data Protection Regulation (GDPR).

    Attributes:
        _consent_records: Consent records
        _processing_records: Data processing records
        _breach_records: Data breach records
        _data_store: Mock data store (replace with real database)

    Example:
        >>> gdpr = GDPRCompliance()
        >>>
        >>> # Record consent
        >>> await gdpr.record_consent(
        ...     user_id="user123",
        ...     purpose="marketing",
        ...     consent_given=True,
        ... )
        >>>
        >>> # Check consent
        >>> has_consent = await gdpr.has_consent(user_id="user123", purpose="marketing")
        >>>
        >>> # Handle data subject access request (Article 15)
        >>> data = await gdpr.handle_access_request(user_id="user123")
        >>>
        >>> # Handle right to erasure (Article 17)
        >>> await gdpr.handle_erasure_request(user_id="user123")
    """

    def __init__(self):
        """Initialize GDPR compliance controls."""
        # Article 7: Consent records
        self._consent_records: list[ConsentRecord] = []

        # Article 30: Records of processing activities
        self._processing_records: list[DataProcessingRecord] = []

        # Article 33-34: Breach records
        self._breach_records: list[DataBreachRecord] = []

        # Mock data store (replace with real database in production)
        self._data_store: dict[str, dict[str, Any]] = {}

        logger.info("gdpr_compliance_initialized")

    async def record_consent(
        self,
        user_id: str,
        purpose: ProcessingPurpose | str,
        consent_given: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        consent_text: str | None = None,
        expires_in_days: int | None = None,
    ) -> ConsentRecord:
        """Record user consent for data processing.

        Article 7: Conditions for consent.
        Consent must be freely given, specific, informed, and unambiguous.

        Args:
            user_id: User ID
            purpose: Purpose of data processing
            consent_given: Whether consent was given or withdrawn
            ip_address: IP address for audit trail
            user_agent: User agent for audit trail
            consent_text: Text of consent shown to user
            expires_in_days: Consent expiration in days

        Returns:
            ConsentRecord

        Example:
            >>> consent = await gdpr.record_consent(
            ...     user_id="user123",
            ...     purpose="marketing",
            ...     consent_given=True,
            ...     expires_in_days=365,
            ... )
        """
        timestamp = datetime.now(UTC)
        expires_at = None

        if expires_in_days:
            expires_at = timestamp + timedelta(days=expires_in_days)

        consent = ConsentRecord(
            consent_id=f"consent_{secrets.token_hex(8)}",
            user_id=user_id,
            purpose=purpose,
            consent_given=consent_given,
            timestamp=timestamp,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text=consent_text,
            expires_at=expires_at,
        )

        self._consent_records.append(consent)

        logger.info(
            "gdpr_consent_recorded",
            user_id=user_id,
            purpose=purpose,
            consent_given=consent_given,
        )

        return consent

    async def has_consent(
        self,
        user_id: str,
        purpose: ProcessingPurpose | str,
    ) -> bool:
        """Check if user has given valid consent for purpose.

        Article 7: Conditions for consent.

        Args:
            user_id: User ID
            purpose: Purpose to check

        Returns:
            True if valid consent exists, False otherwise

        Example:
            >>> has_consent = await gdpr.has_consent("user123", "marketing")
        """
        now = datetime.now(UTC)

        # Find most recent consent for this purpose
        relevant_consents = [
            c
            for c in self._consent_records
            if c.user_id == user_id and c.purpose == purpose
        ]

        if not relevant_consents:
            return False

        # Get most recent
        latest_consent = max(relevant_consents, key=lambda c: c.timestamp)

        # Check if consent is given and not expired
        is_valid = (
            latest_consent.consent_given
            and (latest_consent.expires_at is None or latest_consent.expires_at > now)
        )

        return is_valid

    async def handle_access_request(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """Handle data subject access request (Article 15).

        User has the right to obtain:
        - Confirmation of processing
        - Access to personal data
        - Copy of personal data

        Args:
            user_id: User ID requesting access

        Returns:
            Dictionary containing all personal data

        Example:
            >>> data = await gdpr.handle_access_request("user123")
            >>> # Returns: {"user_id": "user123", "email": "user@example.com", ...}
        """
        logger.info("gdpr_access_request", user_id=user_id)

        # Collect all personal data for this user
        personal_data = {
            "user_id": user_id,
            "data_collected_at": datetime.now(UTC).isoformat(),
            "stored_data": self._data_store.get(user_id, {}),
            "consent_records": [
                c.model_dump()
                for c in self._consent_records
                if c.user_id == user_id
            ],
            "processing_purposes": list(
                {c.purpose for c in self._consent_records if c.user_id == user_id}
            ),
        }

        logger.info("gdpr_access_request_fulfilled", user_id=user_id)

        return personal_data

    async def handle_rectification_request(
        self,
        user_id: str,
        data_updates: dict[str, Any],
    ) -> bool:
        """Handle right to rectification (Article 16).

        User has the right to rectify inaccurate personal data.

        Args:
            user_id: User ID
            data_updates: Dictionary of fields to update

        Returns:
            True if successful

        Example:
            >>> await gdpr.handle_rectification_request(
            ...     user_id="user123",
            ...     data_updates={"email": "new@example.com"},
            ... )
        """
        logger.info(
            "gdpr_rectification_request",
            user_id=user_id,
            fields_updated=list(data_updates.keys()),
        )

        # Update user data
        if user_id not in self._data_store:
            self._data_store[user_id] = {}

        self._data_store[user_id].update(data_updates)
        self._data_store[user_id]["last_updated"] = datetime.now(UTC).isoformat()

        logger.info("gdpr_rectification_completed", user_id=user_id)

        return True

    async def handle_erasure_request(
        self,
        user_id: str,
        reason: str | None = None,
    ) -> bool:
        """Handle right to erasure - "right to be forgotten" (Article 17).

        User has the right to erasure when:
        - Data no longer necessary
        - Consent withdrawn
        - Data processed unlawfully
        - Legal obligation to erase

        Args:
            user_id: User ID
            reason: Reason for erasure

        Returns:
            True if successful

        Example:
            >>> await gdpr.handle_erasure_request(
            ...     user_id="user123",
            ...     reason="User requested account deletion",
            ... )
        """
        logger.info(
            "gdpr_erasure_request",
            user_id=user_id,
            reason=reason,
        )

        # Erase personal data
        if user_id in self._data_store:
            del self._data_store[user_id]

        # Anonymize audit records (keep for legal compliance)
        # Note: In production, some records must be retained for legal reasons
        user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]

        for consent in self._consent_records:
            if consent.user_id == user_id:
                consent.user_id = f"anonymized_{user_hash}"

        logger.info("gdpr_erasure_completed", user_id=user_id)

        return True

    async def handle_portability_request(
        self,
        user_id: str,
        format: str = "json",
    ) -> dict[str, Any] | str:
        """Handle right to data portability (Article 20).

        User has the right to receive personal data in a structured,
        commonly used, and machine-readable format.

        Args:
            user_id: User ID
            format: Output format (json, csv, xml)

        Returns:
            Personal data in requested format

        Example:
            >>> data = await gdpr.handle_portability_request("user123", format="json")
        """
        logger.info("gdpr_portability_request", user_id=user_id, format=format)

        # Get user data
        data = await self.handle_access_request(user_id)

        # Format data (simplified - would need proper CSV/XML serialization)
        if format == "json":
            import json
            from datetime import datetime

            def default_serializer(obj):
                """Handle datetime serialization."""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            return json.dumps(data, indent=2, default=default_serializer)
        elif format == "csv":
            # Simplified CSV export
            return "CSV export not fully implemented"
        elif format == "xml":
            # Simplified XML export
            return "XML export not fully implemented"
        else:
            return data

    async def record_processing_activity(
        self,
        controller: str,
        purpose: ProcessingPurpose | str,
        data_categories: list[DataCategory | str],
        data_subjects: list[str],
        retention_period: str,
        security_measures: list[str],
        recipients: list[str] | None = None,
        third_country_transfers: bool = False,
    ) -> DataProcessingRecord:
        """Record processing activity (Article 30).

        Required for GDPR compliance - controllers must maintain records
        of all processing activities.

        Args:
            controller: Data controller name
            purpose: Purpose of processing
            data_categories: Categories of personal data
            data_subjects: Categories of data subjects
            retention_period: How long data is retained
            security_measures: Technical and organizational measures
            recipients: Recipients of data
            third_country_transfers: Whether data is transferred outside EU

        Returns:
            DataProcessingRecord

        Example:
            >>> record = await gdpr.record_processing_activity(
            ...     controller="Acme Corp",
            ...     purpose="contract",
            ...     data_categories=["basic_identity"],
            ...     data_subjects=["customers"],
            ...     retention_period="7 years",
            ...     security_measures=["encryption", "access_control"],
            ... )
        """
        record = DataProcessingRecord(
            record_id=f"rec_{secrets.token_hex(8)}",
            controller=controller,
            purpose=purpose,
            data_categories=data_categories,
            data_subjects=data_subjects,
            recipients=recipients,
            third_country_transfers=third_country_transfers,
            retention_period=retention_period,
            security_measures=security_measures,
            timestamp=datetime.now(UTC),
        )

        self._processing_records.append(record)

        logger.info(
            "gdpr_processing_activity_recorded",
            controller=controller,
            purpose=purpose,
        )

        return record

    async def report_data_breach(
        self,
        severity: BreachSeverity,
        affected_users: int,
        data_categories: list[DataCategory | str],
        description: str,
        consequences: str,
        measures_taken: list[str],
    ) -> DataBreachRecord:
        """Report personal data breach (Article 33-34).

        Controllers must notify supervisory authority within 72 hours
        if breach poses a risk to rights and freedoms.

        Args:
            severity: Breach severity
            affected_users: Number of affected users
            data_categories: Categories of breached data
            description: Description of breach
            consequences: Likely consequences
            measures_taken: Measures taken to address breach

        Returns:
            DataBreachRecord

        Example:
            >>> breach = await gdpr.report_data_breach(
            ...     severity="high",
            ...     affected_users=1000,
            ...     data_categories=["basic_identity"],
            ...     description="Database access breach",
            ...     consequences="Potential identity theft",
            ...     measures_taken=["Passwords reset", "Security audit"],
            ... )
        """
        breach = DataBreachRecord(
            breach_id=f"breach_{secrets.token_hex(8)}",
            discovered_at=datetime.now(UTC),
            severity=severity,
            affected_users=affected_users,
            data_categories=data_categories,
            description=description,
            consequences=consequences,
            measures_taken=measures_taken,
        )

        self._breach_records.append(breach)

        logger.error(
            "gdpr_data_breach_reported",
            breach_id=breach.breach_id,
            severity=severity.value,
            affected_users=affected_users,
        )

        # If HIGH or CRITICAL, automatic notification required
        if severity in [BreachSeverity.HIGH, BreachSeverity.CRITICAL]:
            logger.critical(
                "gdpr_breach_notification_required",
                breach_id=breach.breach_id,
                deadline="72 hours from discovery",
            )

        return breach

    async def generate_compliance_report(self) -> dict[str, Any]:
        """Generate GDPR compliance report.

        Returns:
            Compliance report with statistics

        Example:
            >>> report = await gdpr.generate_compliance_report()
        """
        total_consents = len(self._consent_records)
        active_consents = len([
            c for c in self._consent_records
            if c.consent_given and (c.expires_at is None or c.expires_at > datetime.now(UTC))
        ])

        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_consents": total_consents,
            "active_consents": active_consents,
            "consent_rate": active_consents / total_consents if total_consents > 0 else 0,
            "processing_activities": len(self._processing_records),
            "data_breaches": len(self._breach_records),
            "high_severity_breaches": len([
                b for b in self._breach_records
                if b.severity in [BreachSeverity.HIGH, BreachSeverity.CRITICAL]
            ]),
        }

        logger.info("gdpr_compliance_report_generated", report=report)

        return report


__all__ = [
    "GDPRCompliance",
    "ConsentRecord",
    "DataProcessingRecord",
    "DataBreachRecord",
    "ProcessingPurpose",
    "DataCategory",
    "DataSubjectRight",
    "BreachSeverity",
]
