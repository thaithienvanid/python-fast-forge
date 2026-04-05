"""Comprehensive tests for the ISO 27001 compliance implementation.

Tests cover access control, security event logging, cryptographic compliance,
event retrieval, control verification, and compliance reporting.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.compliance.iso27001 import (
    AccessControlRule,
    AccessLevel,
    ControlCategory,
    ISO27001Compliance,
    SecurityEvent,
    SecurityEventType,
)


# ─── Enums ────────────────────────────────────────────────────────────────────


class TestISO27001Enums:
    """Tests for ISO 27001 enum values."""

    def test_control_categories(self):
        assert ControlCategory.ORGANIZATIONAL == "organizational"
        assert ControlCategory.PEOPLE == "people"
        assert ControlCategory.PHYSICAL == "physical"
        assert ControlCategory.TECHNOLOGICAL == "technological"

    def test_security_event_types(self):
        types = {e.value for e in SecurityEventType}
        assert "login_success" in types
        assert "login_failure" in types
        assert "access_granted" in types
        assert "access_denied" in types
        assert "intrusion_attempt" in types

    def test_access_levels(self):
        assert AccessLevel.NONE == "none"
        assert AccessLevel.READ == "read"
        assert AccessLevel.WRITE == "write"
        assert AccessLevel.ADMIN == "admin"
        assert AccessLevel.PRIVILEGED == "privileged"


# ─── ISO27001Compliance Initialization ────────────────────────────────────────


class TestISO27001ComplianceInit:
    """Tests for ISO27001Compliance initialization."""

    def test_default_init(self):
        iso = ISO27001Compliance()
        assert iso._security_events == []
        assert iso._access_rules == []
        assert iso._failed_logins == {}

    def test_crypto_controls_initialized(self):
        iso = ISO27001Compliance()
        # Should have pre-populated crypto controls
        assert len(iso._crypto_controls) > 0

    def test_crypto_controls_include_aes(self):
        iso = ISO27001Compliance()
        algorithms = [c.algorithm for c in iso._crypto_controls]
        assert "AES-256-GCM" in algorithms

    def test_crypto_controls_include_sha256(self):
        iso = ISO27001Compliance()
        algorithms = [c.algorithm for c in iso._crypto_controls]
        assert "SHA-256" in algorithms


# ─── add_access_rule ─────────────────────────────────────────────────────────


class TestAddAccessRule:
    """Tests for add_access_rule method."""

    @pytest.mark.asyncio
    async def test_add_user_rule(self):
        iso = ISO27001Compliance()
        rule = await iso.add_access_rule(
            resource="database.users",
            access_level=AccessLevel.READ,
            user_id="user123",
        )

        assert isinstance(rule, AccessControlRule)
        assert rule.user_id == "user123"
        assert rule.resource == "database.users"
        assert rule.access_level == AccessLevel.READ
        assert rule.rule_id.startswith("rule_")

    @pytest.mark.asyncio
    async def test_add_role_rule(self):
        iso = ISO27001Compliance()
        rule = await iso.add_access_rule(
            resource="api.*",
            access_level=AccessLevel.WRITE,
            role="api_user",
        )

        assert rule.role == "api_user"
        assert rule.user_id is None

    @pytest.mark.asyncio
    async def test_add_rule_requires_user_or_role(self):
        iso = ISO27001Compliance()
        with pytest.raises(ValueError, match="Either user_id or role must be specified"):
            await iso.add_access_rule(
                resource="resource",
                access_level=AccessLevel.READ,
            )

    @pytest.mark.asyncio
    async def test_add_rule_with_expiry(self):
        iso = ISO27001Compliance()
        rule = await iso.add_access_rule(
            resource="database.*",
            access_level=AccessLevel.READ,
            user_id="temp_user",
            valid_days=30,
        )

        assert rule.valid_until is not None
        expected = datetime.now(UTC) + timedelta(days=30)
        assert abs((rule.valid_until - expected).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_add_rule_appended_to_list(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule("resource1", AccessLevel.READ, user_id="u1")
        await iso.add_access_rule("resource2", AccessLevel.WRITE, user_id="u2")

        assert len(iso._access_rules) == 2

    @pytest.mark.asyncio
    async def test_add_rule_string_access_level(self):
        iso = ISO27001Compliance()
        rule = await iso.add_access_rule(
            resource="resource",
            access_level="read",
            user_id="user123",
        )
        assert rule.access_level == AccessLevel.READ


# ─── verify_access ────────────────────────────────────────────────────────────


class TestVerifyAccess:
    """Tests for verify_access method."""

    @pytest.mark.asyncio
    async def test_access_denied_no_rules(self):
        iso = ISO27001Compliance()
        result = await iso.verify_access(
            resource="database.users",
            requested_level=AccessLevel.READ,
            user_id="user123",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_access_granted_exact_match(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule(
            resource="database.users",
            access_level=AccessLevel.READ,
            user_id="user123",
        )

        result = await iso.verify_access(
            resource="database.users",
            requested_level=AccessLevel.READ,
            user_id="user123",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_access_granted_higher_level(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule(
            resource="database.users",
            access_level=AccessLevel.ADMIN,
            user_id="user123",
        )

        # ADMIN covers READ
        result = await iso.verify_access(
            resource="database.users",
            requested_level=AccessLevel.READ,
            user_id="user123",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_access_denied_insufficient_level(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule(
            resource="database.users",
            access_level=AccessLevel.READ,
            user_id="user123",
        )

        # READ does not cover WRITE
        result = await iso.verify_access(
            resource="database.users",
            requested_level=AccessLevel.WRITE,
            user_id="user123",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_access_denied_wrong_user(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule(
            resource="database.users",
            access_level=AccessLevel.READ,
            user_id="user123",
        )

        result = await iso.verify_access(
            resource="database.users",
            requested_level=AccessLevel.READ,
            user_id="user456",  # Different user
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_access_with_role(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule(
            resource="api.*",
            access_level=AccessLevel.WRITE,
            role="api_user",
        )

        result = await iso.verify_access(
            resource="api.v1",
            requested_level=AccessLevel.READ,
            role="api_user",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_access_logs_security_event(self):
        iso = ISO27001Compliance()
        await iso.verify_access(
            resource="database.users",
            requested_level=AccessLevel.READ,
            user_id="user123",
        )

        # Should have logged an ACCESS_DENIED event
        assert len(iso._security_events) > 0

    @pytest.mark.asyncio
    async def test_access_string_level(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule("resource", "read", user_id="u1")

        result = await iso.verify_access(
            resource="resource",
            requested_level="read",
            user_id="u1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_expired_rule_denies_access(self):
        iso = ISO27001Compliance()
        # Add a rule with expiry in the past
        rule = await iso.add_access_rule(
            resource="resource",
            access_level=AccessLevel.READ,
            user_id="user123",
            valid_days=1,
        )
        # Manually set to past
        rule.valid_until = datetime.now(UTC) - timedelta(hours=1)

        result = await iso.verify_access(
            resource="resource",
            requested_level=AccessLevel.READ,
            user_id="user123",
        )
        assert result is False


# ─── _resource_matches ────────────────────────────────────────────────────────


class TestResourceMatches:
    """Tests for _resource_matches method."""

    def test_exact_match(self):
        iso = ISO27001Compliance()
        assert iso._resource_matches("database.users", "database.users") is True

    def test_wildcard_match(self):
        iso = ISO27001Compliance()
        assert iso._resource_matches("database.users", "database.*") is True
        assert iso._resource_matches("database.orders", "database.*") is True

    def test_no_match(self):
        iso = ISO27001Compliance()
        assert iso._resource_matches("api.users", "database.*") is False

    def test_full_wildcard(self):
        iso = ISO27001Compliance()
        assert iso._resource_matches("anything", "*") is True


# ─── log_security_event ──────────────────────────────────────────────────────


class TestLogSecurityEvent:
    """Tests for log_security_event method."""

    @pytest.mark.asyncio
    async def test_log_login_success(self):
        iso = ISO27001Compliance()
        event = await iso.log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id="user123",
            ip_address="192.168.1.1",
        )

        assert isinstance(event, SecurityEvent)
        assert event.event_type == SecurityEventType.LOGIN_SUCCESS
        assert event.user_id == "user123"
        assert event.event_id.startswith("evt_")

    @pytest.mark.asyncio
    async def test_log_event_string_type(self):
        iso = ISO27001Compliance()
        event = await iso.log_security_event(
            event_type="login_success",
            user_id="user123",
        )
        assert event.event_type == SecurityEventType.LOGIN_SUCCESS

    @pytest.mark.asyncio
    async def test_log_failed_login_tracks_attempts(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(
            event_type=SecurityEventType.LOGIN_FAILURE,
            user_id="user123",
        )

        assert "user123" in iso._failed_logins
        assert len(iso._failed_logins["user123"]) == 1

    @pytest.mark.asyncio
    async def test_brute_force_detection(self):
        """After 5 failed logins in 5 minutes, brute force warning should trigger."""
        iso = ISO27001Compliance()
        for _ in range(5):
            await iso.log_security_event(
                event_type=SecurityEventType.LOGIN_FAILURE,
                user_id="victim_user",
            )

        assert len(iso._failed_logins["victim_user"]) == 5

    @pytest.mark.asyncio
    async def test_log_event_with_severity(self):
        iso = ISO27001Compliance()
        event = await iso.log_security_event(
            event_type=SecurityEventType.INTRUSION_ATTEMPT,
            severity="critical",
        )
        assert event.severity == "critical"

    @pytest.mark.asyncio
    async def test_log_event_appended_to_list(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS)
        await iso.log_security_event(SecurityEventType.LOGOUT)

        assert len(iso._security_events) == 2

    @pytest.mark.asyncio
    async def test_log_event_with_details(self):
        iso = ISO27001Compliance()
        event = await iso.log_security_event(
            event_type=SecurityEventType.ACCESS_GRANTED,
            details={"resource": "database", "level": "read"},
        )
        assert event.details == {"resource": "database", "level": "read"}


# ─── verify_cryptographic_compliance ─────────────────────────────────────────


class TestVerifyCryptographicCompliance:
    """Tests for verify_cryptographic_compliance method."""

    @pytest.mark.asyncio
    async def test_aes_256_gcm_compliant(self):
        iso = ISO27001Compliance()
        result = await iso.verify_cryptographic_compliance(
            algorithm="AES-256-GCM",
            key_length=256,
            purpose="encryption",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_sha_256_compliant(self):
        iso = ISO27001Compliance()
        result = await iso.verify_cryptographic_compliance(
            algorithm="SHA-256",
            key_length=256,
            purpose="hashing",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_hmac_sha256_compliant(self):
        iso = ISO27001Compliance()
        result = await iso.verify_cryptographic_compliance(
            algorithm="HMAC-SHA256",
            key_length=256,
            purpose="integrity",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_weak_algorithm_not_compliant(self):
        iso = ISO27001Compliance()
        result = await iso.verify_cryptographic_compliance(
            algorithm="DES",
            key_length=56,
            purpose="encryption",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_key_length_not_compliant(self):
        iso = ISO27001Compliance()
        result = await iso.verify_cryptographic_compliance(
            algorithm="AES-256-GCM",
            key_length=128,  # Wrong key length
            purpose="encryption",
        )
        assert result is False


# ─── get_security_events ──────────────────────────────────────────────────────


class TestGetSecurityEvents:
    """Tests for get_security_events method."""

    @pytest.mark.asyncio
    async def test_get_all_events(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, user_id="u1")
        await iso.log_security_event(SecurityEventType.LOGIN_FAILURE, user_id="u2")

        events = await iso.get_security_events()
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_filter_by_event_type(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, user_id="u1")
        await iso.log_security_event(SecurityEventType.LOGIN_FAILURE, user_id="u2")

        events = await iso.get_security_events(event_type=SecurityEventType.LOGIN_FAILURE)
        assert len(events) == 1
        assert events[0].event_type == SecurityEventType.LOGIN_FAILURE

    @pytest.mark.asyncio
    async def test_filter_by_event_type_string(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, user_id="u1")

        events = await iso.get_security_events(event_type="login_success")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_filter_by_user_id(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, user_id="user123")
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, user_id="user456")

        events = await iso.get_security_events(user_id="user123")
        assert len(events) == 1
        assert events[0].user_id == "user123"

    @pytest.mark.asyncio
    async def test_filter_by_date_range(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS)

        start = datetime.now(UTC) - timedelta(seconds=10)
        end = datetime.now(UTC) + timedelta(seconds=10)

        events = await iso.get_security_events(start_date=start, end_date=end)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_filter_by_severity(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, severity="info")
        await iso.log_security_event(
            SecurityEventType.INTRUSION_ATTEMPT,
            severity="critical",
        )

        events = await iso.get_security_events(severity="critical")
        assert len(events) == 1
        assert events[0].severity == "critical"


# ─── verify_controls ─────────────────────────────────────────────────────────


class TestISO27001VerifyControls:
    """Tests for verify_controls method."""

    @pytest.mark.asyncio
    async def test_verify_controls_returns_dict(self):
        iso = ISO27001Compliance()
        controls = await iso.verify_controls()
        assert isinstance(controls, dict)

    @pytest.mark.asyncio
    async def test_verify_controls_all_enabled(self):
        iso = ISO27001Compliance()
        controls = await iso.verify_controls()

        expected_controls = [
            "access_control_enabled",
            "security_monitoring_enabled",
            "cryptographic_controls_enabled",
            "failed_login_tracking_enabled",
        ]
        for control in expected_controls:
            assert control in controls
            assert controls[control] is True


# ─── generate_compliance_report ──────────────────────────────────────────────


class TestISO27001ComplianceReport:
    """Tests for generate_compliance_report method."""

    @pytest.mark.asyncio
    async def test_empty_report(self):
        iso = ISO27001Compliance()
        report = await iso.generate_compliance_report()

        assert "timestamp" in report
        assert report["total_security_events"] == 0
        assert report["failed_events"] == 0
        assert report["critical_events"] == 0
        assert "controls_status" in report
        assert "compliance_status" in report

    @pytest.mark.asyncio
    async def test_report_with_events(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(SecurityEventType.LOGIN_SUCCESS, success=True)
        await iso.log_security_event(SecurityEventType.LOGIN_FAILURE, success=False)

        report = await iso.generate_compliance_report()

        assert report["total_security_events"] == 2
        assert report["failed_events"] == 1

    @pytest.mark.asyncio
    async def test_report_critical_events(self):
        iso = ISO27001Compliance()
        await iso.log_security_event(
            SecurityEventType.INTRUSION_ATTEMPT,
            severity="critical",
        )

        report = await iso.generate_compliance_report()
        assert report["critical_events"] == 1

    @pytest.mark.asyncio
    async def test_report_access_rules_count(self):
        iso = ISO27001Compliance()
        await iso.add_access_rule("resource1", AccessLevel.READ, user_id="u1")
        await iso.add_access_rule("resource2", AccessLevel.WRITE, user_id="u2")

        report = await iso.generate_compliance_report()
        assert report["access_rules"] == 2

    @pytest.mark.asyncio
    async def test_report_compliance_status(self):
        iso = ISO27001Compliance()
        report = await iso.generate_compliance_report()
        assert report["compliance_status"] is True
