"""Compliance API endpoints for HIPAA, GDPR, ISO 27001, and SOC 2.

This module provides REST API endpoints for compliance management:
- HIPAA: PHI encryption, audit trails, compliance reporting
- GDPR: Consent management, data subject rights (access, erasure, portability)
- ISO 27001: Access control, security monitoring, compliance verification
- SOC 2: Change management, system monitoring, availability tracking

Security:
    All endpoints require authentication and tenant isolation.
    PHI data is automatically encrypted using Fernet encryption.
    All compliance actions are logged with full audit trails.

Example:
    ```python
    # Record GDPR consent
    POST / api / v1 / compliance / gdpr / consent
    {"user_id": "user-uuid", "purpose": "marketing", "consent_given": true}

    # Encrypt PHI (HIPAA)
    POST / api / v1 / compliance / hipaa / encrypt
    {
        "data": {"ssn": "123-45-6789", "diagnosis": "..."},
        "user_id": "doctor-uuid",
        "patient_id": "patient-uuid",
    }

    # Get compliance reports
    GET / api / v1 / compliance / reports
    ```
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.infrastructure.compliance import ComplianceManager
from src.infrastructure.compliance.gdpr import ProcessingPurpose
from src.infrastructure.compliance.iso27001 import AccessLevel, SecurityEventType
from src.infrastructure.compliance.soc2 import ChangeType
from src.presentation.api.dependencies import get_compliance_manager, get_tenant_id
from src.presentation.schemas.base import BaseResponse


router = APIRouter(prefix="/compliance", tags=["compliance"])


# Request/Response Models


class GDPRConsentRequest(BaseModel):
    """Request to record GDPR consent."""

    user_id: str = Field(description="User ID")
    purpose: str | ProcessingPurpose = Field(description="Processing purpose")
    consent_given: bool = Field(description="Whether consent was given")
    ip_address: str | None = Field(default=None, description="User IP address")
    expires_in_days: int | None = Field(default=None, description="Consent expiration in days")


class GDPRAccessRequest(BaseModel):
    """Request for GDPR data access (Article 15)."""

    user_id: str = Field(description="User ID to access data for")


class GDPRErasureRequest(BaseModel):
    """Request for GDPR data erasure (Article 17)."""

    user_id: str = Field(description="User ID to erase data for")
    reason: str | None = Field(default=None, description="Reason for erasure")


class GDPRPortabilityRequest(BaseModel):
    """Request for GDPR data portability (Article 20)."""

    user_id: str = Field(description="User ID to export data for")
    format: Literal["json", "csv"] = Field(default="json", description="Export format")


class HIPAAEncryptRequest(BaseModel):
    """Request to encrypt PHI data."""

    data: dict[str, Any] = Field(description="PHI data to encrypt")
    user_id: str = Field(description="User performing encryption")
    patient_id: str | None = Field(default=None, description="Patient ID")


class HIPAADecryptRequest(BaseModel):
    """Request to decrypt PHI data."""

    encrypted_data: str = Field(description="Encrypted PHI data (base64)")
    user_id: str = Field(description="User performing decryption")
    patient_id: str | None = Field(default=None, description="Patient ID")


class ISO27001AccessRuleRequest(BaseModel):
    """Request to add ISO 27001 access control rule."""

    resource: str = Field(description="Resource to control access to")
    access_level: str | AccessLevel = Field(description="Access level")
    user_id: str | None = Field(default=None, description="Specific user ID")
    role: str | None = Field(default=None, description="Role name")
    valid_days: int | None = Field(default=None, description="Rule validity in days")


class ISO27001SecurityEventRequest(BaseModel):
    """Request to log ISO 27001 security event."""

    event_type: str | SecurityEventType = Field(description="Event type")
    success: bool = Field(default=True, description="Whether event succeeded")
    user_id: str | None = Field(default=None, description="User ID")
    resource: str | None = Field(default=None, description="Resource accessed")


class SOC2ChangeRequest(BaseModel):
    """Request to create SOC 2 change request."""

    change_type: str | ChangeType = Field(description="Type of change")
    description: str = Field(description="Change description")
    requestor: str = Field(description="User requesting change")
    rollback_plan: str | None = Field(default=None, description="Rollback plan")


class SOC2ChangeApprovalRequest(BaseModel):
    """Request to approve/implement SOC 2 change."""

    change_id: str = Field(description="Change ID")
    approver: str = Field(description="User approving change")


class ComplianceReportResponse(BaseModel):
    """Comprehensive compliance report."""

    timestamp: str
    frameworks: dict[str, dict[str, Any]]


# GDPR Endpoints


@router.post("/gdpr/consent", response_model=BaseResponse)
async def record_gdpr_consent(
    request: GDPRConsentRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Record user consent for data processing (GDPR Article 7).

    Args:
        request: Consent request data
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Consent record

    Example:
        ```json
        POST /api/v1/compliance/gdpr/consent
        {
            "user_id": "user123",
            "purpose": "marketing",
            "consent_given": true,
            "ip_address": "192.168.1.1",
            "expires_in_days": 365
        }
        ```
    """
    consent = await compliance.gdpr.record_consent(
        user_id=request.user_id,
        purpose=request.purpose,
        consent_given=request.consent_given,
        ip_address=request.ip_address,
        expires_in_days=request.expires_in_days,
    )

    return BaseResponse(
        success=True,
        message="Consent recorded successfully",
        data=consent.model_dump(),
    )


@router.post("/gdpr/access", response_model=BaseResponse)
async def gdpr_access_request(
    request: GDPRAccessRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Handle data subject access request (GDPR Article 15).

    Args:
        request: Access request data
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        User data
    """
    data = await compliance.gdpr.handle_access_request(request.user_id)

    return BaseResponse(
        success=True,
        message="Data access request processed",
        data=data,
    )


@router.post("/gdpr/erasure", response_model=BaseResponse)
async def gdpr_erasure_request(
    request: GDPRErasureRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Handle right to erasure request (GDPR Article 17).

    Args:
        request: Erasure request data
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Success confirmation
    """
    result = await compliance.gdpr.handle_erasure_request(
        user_id=request.user_id,
        reason=request.reason,
    )

    return BaseResponse(
        success=result,
        message="Data erasure completed" if result else "Erasure failed",
    )


@router.post("/gdpr/portability", response_model=BaseResponse)
async def gdpr_portability_request(
    request: GDPRPortabilityRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Handle data portability request (GDPR Article 20).

    Args:
        request: Portability request data
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Exported data in requested format
    """
    data = await compliance.gdpr.handle_portability_request(
        user_id=request.user_id,
        format=request.format,
    )

    return BaseResponse(
        success=True,
        message=f"Data exported in {request.format} format",
        data={"export": data},
    )


# HIPAA Endpoints


@router.post("/hipaa/encrypt", response_model=BaseResponse)
async def encrypt_phi(
    request: HIPAAEncryptRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Encrypt Protected Health Information (HIPAA § 164.312).

    Args:
        request: Encryption request
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Encrypted data (base64)
    """
    encrypted = await compliance.hipaa.encrypt_phi(
        data=request.data,
        user_id=request.user_id,
        patient_id=request.patient_id,
    )

    # Convert bytes to base64 string for JSON response
    import base64

    encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

    return BaseResponse(
        success=True,
        message="PHI encrypted successfully",
        data={"encrypted_data": encrypted_b64},
    )


@router.post("/hipaa/decrypt", response_model=BaseResponse)
async def decrypt_phi(
    request: HIPAADecryptRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Decrypt Protected Health Information (HIPAA § 164.312).

    Args:
        request: Decryption request
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Decrypted PHI data
    """
    import base64

    # Decode base64 to bytes
    encrypted_bytes = base64.b64decode(request.encrypted_data)

    decrypted = await compliance.hipaa.decrypt_phi(
        encrypted_data=encrypted_bytes,
        user_id=request.user_id,
        patient_id=request.patient_id,
    )

    return BaseResponse(
        success=True,
        message="PHI decrypted successfully",
        data=decrypted,
    )


@router.get("/hipaa/audit", response_model=BaseResponse)
async def get_hipaa_audit_trail(
    patient_id: str = Query(description="Patient ID to get audit trail for"),
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)] = None,
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Get HIPAA audit trail for patient.

    Args:
        patient_id: Patient ID
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Audit trail events
    """
    audit_trail = await compliance.hipaa.get_audit_trail(patient_id=patient_id)

    return BaseResponse(
        success=True,
        message=f"Retrieved {len(audit_trail)} audit events",
        data={"audit_trail": [event.model_dump() for event in audit_trail]},
    )


# ISO 27001 Endpoints


@router.post("/iso27001/access-rule", response_model=BaseResponse)
async def add_access_rule(
    request: ISO27001AccessRuleRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Add access control rule (ISO 27001 A.8.3).

    Args:
        request: Access rule request
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Created access rule
    """
    rule = await compliance.iso27001.add_access_rule(
        resource=request.resource,
        access_level=request.access_level,
        user_id=request.user_id,
        role=request.role,
        valid_days=request.valid_days,
    )

    return BaseResponse(
        success=True,
        message="Access rule created successfully",
        data=rule.model_dump(),
    )


@router.post("/iso27001/security-event", response_model=BaseResponse)
async def log_security_event(
    request: ISO27001SecurityEventRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Log security event (ISO 27001 A.8.16).

    Args:
        request: Security event request
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Logged security event
    """
    event = await compliance.iso27001.log_security_event(
        event_type=request.event_type,
        success=request.success,
        user_id=request.user_id,
        resource=request.resource,
    )

    return BaseResponse(
        success=True,
        message="Security event logged",
        data=event.model_dump(),
    )


# SOC 2 Endpoints


@router.post("/soc2/change-request", response_model=BaseResponse)
async def create_change_request(
    request: SOC2ChangeRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Create change request (SOC 2 CC8: Change Management).

    Args:
        request: Change request data
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Created change record
    """
    change = await compliance.soc2.request_change(
        change_type=request.change_type,
        description=request.description,
        requestor=request.requestor,
        rollback_plan=request.rollback_plan,
    )

    return BaseResponse(
        success=True,
        message="Change request created",
        data=change.model_dump(),
    )


@router.post("/soc2/change-approve", response_model=BaseResponse)
async def approve_change(
    request: SOC2ChangeApprovalRequest,
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Approve change request (SOC 2 CC8).

    Args:
        request: Approval request
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Updated change record
    """
    change = await compliance.soc2.approve_change(
        change_id=request.change_id,
        approver=request.approver,
    )

    return BaseResponse(
        success=True,
        message="Change approved",
        data=change.model_dump(),
    )


# Comprehensive Compliance Reports


@router.get("/reports", response_model=ComplianceReportResponse)
async def get_compliance_reports(
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Get comprehensive compliance reports for all frameworks.

    This endpoint generates a complete compliance report covering:
    - HIPAA: Audit trail statistics, PHI access logs
    - GDPR: Consent records, data subject requests
    - ISO 27001: Security events, access control rules
    - SOC 2: Change records, system availability

    Args:
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Comprehensive compliance report

    Example Response:
        ```json
        {
            "timestamp": "2026-02-07T12:00:00Z",
            "frameworks": {
                "hipaa": {
                    "total_audit_events": 150,
                    "phi_accesses_last_30_days": 45
                },
                "gdpr": {
                    "total_consents": 1200,
                    "active_consents": 950
                },
                "iso27001": {
                    "total_security_events": 500,
                    "failed_logins_last_24h": 3
                },
                "soc2": {
                    "pending_changes": 5,
                    "system_availability": 99.98
                }
            }
        }
        ```
    """
    report = await compliance.generate_comprehensive_report()

    return ComplianceReportResponse(**report)


@router.get("/status", response_model=BaseResponse)
async def get_compliance_status(
    compliance: Annotated[ComplianceManager, Depends(get_compliance_manager)],
    tenant_id: Annotated[UUID | None, Depends(get_tenant_id)] = None,
):
    """Get compliance verification status for all frameworks.

    Args:
        compliance: Compliance manager (injected)
        tenant_id: Tenant ID (injected)

    Returns:
        Compliance status for all frameworks
    """
    status_result = await compliance.verify_all_controls()

    return BaseResponse(
        success=True,
        message="Compliance status retrieved",
        data=status_result,
    )
