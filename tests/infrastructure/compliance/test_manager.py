"""Tests for Compliance Manager."""

import pytest

from src.infrastructure.compliance import ComplianceManager


class TestComplianceManager:
    """Test Compliance Manager unified interface."""

    @pytest.fixture
    def manager(self):
        """Create Compliance Manager instance."""
        return ComplianceManager()

    @pytest.mark.asyncio
    async def test_initialization(self, manager):
        """Test manager initialization."""
        await manager.initialize()

        assert manager._initialized is True
        assert manager.hipaa is not None
        assert manager.gdpr is not None
        assert manager.iso27001 is not None
        assert manager.soc2 is not None

    @pytest.mark.asyncio
    async def test_verify_all_controls(self, manager):
        """Test verification of all controls."""
        await manager.initialize()

        results = await manager.verify_all_controls()

        assert "hipaa" in results
        assert "gdpr" in results
        assert "iso27001" in results
        assert "soc2" in results

        # Each framework should have control results
        assert isinstance(results["hipaa"], dict)
        assert isinstance(results["iso27001"], dict)
        assert isinstance(results["soc2"], dict)

    @pytest.mark.asyncio
    async def test_comprehensive_report(self, manager):
        """Test comprehensive compliance report."""
        await manager.initialize()

        report = await manager.generate_comprehensive_report()

        assert "timestamp" in report
        assert "overall_compliance" in report
        assert "framework_statuses" in report
        assert "frameworks" in report
        assert "summary" in report

        # Check framework statuses
        assert "hipaa" in report["framework_statuses"]
        assert "gdpr" in report["framework_statuses"]
        assert "iso27001" in report["framework_statuses"]
        assert "soc2" in report["framework_statuses"]

        # Check summary
        assert report["summary"]["total_frameworks"] == 4
        assert 0 <= report["summary"]["compliance_percentage"] <= 100

    @pytest.mark.asyncio
    async def test_compliance_status(self, manager):
        """Test quick compliance status."""
        await manager.initialize()

        status = await manager.get_compliance_status()

        assert "hipaa" in status
        assert "gdpr" in status
        assert "iso27001" in status
        assert "soc2" in status

        # All should be boolean
        assert isinstance(status["hipaa"], bool)
        assert isinstance(status["gdpr"], bool)
        assert isinstance(status["iso27001"], bool)
        assert isinstance(status["soc2"], bool)

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health check."""
        await manager.initialize()

        health = await manager.health_check()

        assert "timestamp" in health
        assert "healthy" in health
        assert "frameworks" in health
        assert "initialized" in health

        assert health["initialized"] is True
        assert isinstance(health["healthy"], bool)

    @pytest.mark.asyncio
    async def test_individual_framework_access(self, manager):
        """Test access to individual frameworks."""
        await manager.initialize()

        # Test HIPAA
        phi_data = {"ssn": "123-45-6789"}
        encrypted = await manager.hipaa.encrypt_phi(
            data=phi_data,
            user_id="user123",
        )
        assert encrypted is not None

        # Test GDPR
        consent = await manager.gdpr.record_consent(
            user_id="user123",
            purpose="marketing",
            consent_given=True,
        )
        assert consent.consent_given is True

        # Test ISO 27001
        await manager.iso27001.add_access_rule(
            user_id="user123",
            resource="database",
            access_level="read",
        )

        # Test SOC 2
        change = await manager.soc2.request_change(
            change_type="configuration",
            description="Update settings",
            requestor="admin",
        )
        assert change is not None

    @pytest.mark.asyncio
    async def test_all_frameworks_operational(self, manager):
        """Test that all frameworks are operational."""
        await manager.initialize()

        # Verify all controls
        results = await manager.verify_all_controls()

        # All frameworks should have at least one control
        for framework, controls in results.items():
            assert len(controls) > 0, f"{framework} has no controls"

        # Get comprehensive report
        report = await manager.generate_comprehensive_report()

        # Should have reports from all frameworks
        assert "hipaa" in report["frameworks"]
        assert "gdpr" in report["frameworks"]
        assert "iso27001" in report["frameworks"]
        assert "soc2" in report["frameworks"]
