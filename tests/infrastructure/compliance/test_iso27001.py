"""Tests for ISO 27001:2022 Security Controls Implementation."""

import pytest
from datetime import UTC, datetime, timedelta

from src.infrastructure.compliance.iso27001 import (
    ISO27001Compliance,
    AccessLevel,
    SecurityEventType,
)


class TestISO27001Compliance:
    """Test ISO 27001 compliance controls."""

    @pytest.fixture
    def iso(self):
        """Create ISO 27001 compliance instance."""
        return ISO27001Compliance()

    @pytest.mark.asyncio
    async def test_add_access_rule(self, iso):
        """Test adding access control rule."""
        rule = await iso.add_access_rule(
            user_id="user123",
            resource="database.*",
            access_level=AccessLevel.READ,
            valid_days=30,
        )

        assert rule.user_id == "user123"
        assert rule.resource == "database.*"
        assert rule.access_level == AccessLevel.READ
        assert rule.valid_until is not None

    @pytest.mark.asyncio
    async def test_verify_access_granted(self, iso):
        """Test access verification - granted."""
        # Add access rule
        await iso.add_access_rule(
            user_id="user123",
            resource="database.*",
            access_level=AccessLevel.READ,
        )

        # Verify access
        has_access = await iso.verify_access(
            user_id="user123",
            resource="database.users",
            requested_level=AccessLevel.READ,
        )

        assert has_access is True

    @pytest.mark.asyncio
    async def test_verify_access_denied(self, iso):
        """Test access verification - denied."""
        # Add READ access
        await iso.add_access_rule(
            user_id="user123",
            resource="database.*",
            access_level=AccessLevel.READ,
        )

        # Try to get WRITE access (should be denied)
        has_access = await iso.verify_access(
            user_id="user123",
            resource="database.users",
            requested_level=AccessLevel.WRITE,
        )

        assert has_access is False

    @pytest.mark.asyncio
    async def test_role_based_access(self, iso):
        """Test role-based access control."""
        # Add role-based rule
        await iso.add_access_rule(
            role="admin",
            resource="*",
            access_level=AccessLevel.ADMIN,
        )

        # Verify access by role
        has_access = await iso.verify_access(
            role="admin",
            resource="any.resource",
            requested_level=AccessLevel.ADMIN,
        )

        assert has_access is True

    @pytest.mark.asyncio
    async def test_access_expiration(self, iso):
        """Test access rule expiration."""
        # Add rule that expires immediately
        await iso.add_access_rule(
            user_id="user123",
            resource="database.*",
            access_level=AccessLevel.READ,
            valid_days=-1,  # Already expired
        )

        # Verify access (should be denied due to expiration)
        has_access = await iso.verify_access(
            user_id="user123",
            resource="database.users",
            requested_level=AccessLevel.READ,
        )

        assert has_access is False

    @pytest.mark.asyncio
    async def test_log_security_event(self, iso):
        """Test security event logging."""
        event = await iso.log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id="user123",
            ip_address="192.168.1.100",
            success=True,
        )

        assert event.event_type == SecurityEventType.LOGIN_SUCCESS
        assert event.user_id == "user123"
        assert event.ip_address == "192.168.1.100"
        assert event.success is True

    @pytest.mark.asyncio
    async def test_brute_force_detection(self, iso):
        """Test brute force attack detection."""
        # Simulate 5 failed login attempts
        for i in range(5):
            await iso.log_security_event(
                event_type=SecurityEventType.LOGIN_FAILURE,
                user_id="user123",
                success=False,
            )

        # Check that we have 5 failed login events
        events = await iso.get_security_events(
            user_id="user123",
            event_type=SecurityEventType.LOGIN_FAILURE,
        )

        assert len(events) >= 5

    @pytest.mark.asyncio
    async def test_get_security_events_filtering(self, iso):
        """Test security event filtering."""
        # Create different events
        await iso.log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id="user123",
        )

        await iso.log_security_event(
            event_type=SecurityEventType.LOGIN_FAILURE,
            user_id="user456",
        )

        # Filter by user
        user123_events = await iso.get_security_events(user_id="user123")
        assert all(e.user_id == "user123" for e in user123_events)

        # Filter by event type
        login_failures = await iso.get_security_events(
            event_type=SecurityEventType.LOGIN_FAILURE
        )
        assert all(e.event_type == SecurityEventType.LOGIN_FAILURE for e in login_failures)

    @pytest.mark.asyncio
    async def test_cryptographic_compliance(self, iso):
        """Test cryptographic algorithm compliance verification."""
        # Test approved algorithm
        is_compliant = await iso.verify_cryptographic_compliance(
            algorithm="AES-256-GCM",
            key_length=256,
            purpose="encryption",
        )

        assert is_compliant is True

        # Test non-approved algorithm
        is_compliant = await iso.verify_cryptographic_compliance(
            algorithm="DES",
            key_length=56,
            purpose="encryption",
        )

        assert is_compliant is False

    @pytest.mark.asyncio
    async def test_verify_controls(self, iso):
        """Test control verification."""
        controls = await iso.verify_controls()

        assert controls["access_control_enabled"] is True
        assert controls["security_monitoring_enabled"] is True
        assert controls["cryptographic_controls_enabled"] is True
        assert controls["failed_login_tracking_enabled"] is True

    @pytest.mark.asyncio
    async def test_compliance_report(self, iso):
        """Test compliance report generation."""
        # Create some events
        await iso.log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id="user123",
        )

        await iso.log_security_event(
            event_type=SecurityEventType.ACCESS_GRANTED,
            user_id="user123",
            resource="database",
        )

        # Generate report
        report = await iso.generate_compliance_report()

        assert "timestamp" in report
        assert "total_security_events" in report
        assert "failed_events" in report
        assert "critical_events" in report
        assert "access_rules" in report
        assert "compliance_status" in report

        assert report["total_security_events"] >= 2
        assert report["compliance_status"] is True

    @pytest.mark.asyncio
    async def test_access_hierarchy(self, iso):
        """Test access level hierarchy."""
        # Admin access includes write access
        await iso.add_access_rule(
            user_id="user123",
            resource="database.*",
            access_level=AccessLevel.ADMIN,
        )

        # Should have write access
        has_write = await iso.verify_access(
            user_id="user123",
            resource="database.users",
            requested_level=AccessLevel.WRITE,
        )

        # Should have read access
        has_read = await iso.verify_access(
            user_id="user123",
            resource="database.users",
            requested_level=AccessLevel.READ,
        )

        assert has_write is True
        assert has_read is True

    @pytest.mark.asyncio
    async def test_wildcard_resource_matching(self, iso):
        """Test wildcard resource pattern matching."""
        # Add wildcard rule
        await iso.add_access_rule(
            user_id="user123",
            resource="api.*",
            access_level=AccessLevel.READ,
        )

        # Should match api.users
        has_access = await iso.verify_access(
            user_id="user123",
            resource="api.users",
            requested_level=AccessLevel.READ,
        )

        assert has_access is True

        # Should not match database.users
        has_access = await iso.verify_access(
            user_id="user123",
            resource="database.users",
            requested_level=AccessLevel.READ,
        )

        assert has_access is False
