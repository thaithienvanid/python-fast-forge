"""Extended unit tests for ComplianceManager.

Covers missing lines in src/infrastructure/compliance/manager.py:
- Lines 87-94: initialize() sets _initialized flag
- Lines 112-130: verify_all_controls() aggregates framework controls
- Lines 143-186: generate_comprehensive_report() structure and content
- Lines 199-205: get_compliance_status() boolean map
- Lines 218-229: health_check() result structure

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- AsyncMock for async framework methods
- Mock individual framework instances to isolate manager logic
- Test overall_compliance calculation with mixed framework results
- Test health check with initialized/uninitialized states
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.compliance.manager import ComplianceManager


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def manager():
    """Create a ComplianceManager instance with real sub-frameworks."""
    return ComplianceManager()


@pytest.fixture
def mock_manager():
    """Create a ComplianceManager with fully mocked sub-frameworks."""
    mgr = ComplianceManager.__new__(ComplianceManager)
    mgr._initialized = False

    # Mock all sub-frameworks
    mgr.hipaa = MagicMock()
    mgr.gdpr = MagicMock()
    mgr.iso27001 = MagicMock()
    mgr.soc2 = MagicMock()

    # Set up default async return values
    mgr.hipaa.verify_controls = AsyncMock(
        return_value={"encryption_enabled": True, "audit_logging_enabled": True}
    )
    mgr.iso27001.verify_controls = AsyncMock(
        return_value={"access_control_enabled": True, "incident_management_enabled": True}
    )
    mgr.soc2.verify_controls = AsyncMock(
        return_value={"change_management_enabled": True, "availability_enabled": True}
    )

    mgr.hipaa.generate_compliance_report = AsyncMock(
        return_value={
            "compliance_status": True,
            "framework": "HIPAA",
            "controls": {"encryption_enabled": True},
        }
    )
    mgr.gdpr.generate_compliance_report = AsyncMock(
        return_value={
            "framework": "GDPR",
            "data_protection": "enabled",
        }
    )
    mgr.iso27001.generate_compliance_report = AsyncMock(
        return_value={
            "compliance_status": True,
            "framework": "ISO27001",
        }
    )
    mgr.soc2.generate_compliance_report = AsyncMock(
        return_value={
            "compliance_status": True,
            "framework": "SOC2",
        }
    )

    return mgr


# ============================================================================
# initialize() Tests
# ============================================================================


class TestComplianceManagerInitialize:
    """Tests for initialize() covering lines 87-94."""

    async def test_sets_initialized_flag_to_true(self, manager):
        """Test initialize() sets _initialized to True.

        Arrange: Manager not yet initialized
        Act: Call initialize()
        Assert: _initialized is True (line 92)
        """
        # Arrange
        assert manager._initialized is False

        # Act
        await manager.initialize()

        # Assert
        assert manager._initialized is True

    async def test_initialize_is_idempotent(self, manager):
        """Test calling initialize() multiple times is safe.

        Arrange: Already initialized manager
        Act: Call initialize() again
        Assert: _initialized remains True
        """
        # Arrange
        await manager.initialize()
        assert manager._initialized is True

        # Act
        await manager.initialize()

        # Assert
        assert manager._initialized is True

    async def test_logs_initialization_events(self, manager):
        """Test initialize() logs start and completion.

        Arrange: Manager with mocked logger
        Act: Call initialize()
        Assert: logger.info called twice (lines 87, 94)
        """
        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            await manager.initialize()

        # Assert
        assert mock_logger.info.call_count >= 2
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert "compliance_manager_initializing" in log_messages
        assert "compliance_manager_initialized" in log_messages

    async def test_all_sub_frameworks_available_after_init(self, manager):
        """Test all sub-frameworks are accessible after initialization.

        Arrange: Fresh manager
        Act: Call initialize()
        Assert: hipaa, gdpr, iso27001, soc2 all accessible
        """
        # Act
        await manager.initialize()

        # Assert
        assert manager.hipaa is not None
        assert manager.gdpr is not None
        assert manager.iso27001 is not None
        assert manager.soc2 is not None


# ============================================================================
# verify_all_controls() Tests
# ============================================================================


class TestVerifyAllControls:
    """Tests for verify_all_controls() covering lines 112-130."""

    async def test_returns_dict_with_all_framework_keys(self, mock_manager):
        """Test returns dictionary with hipaa, gdpr, iso27001, soc2 keys.

        Arrange: Mock manager with mocked framework verify_controls
        Act: Call verify_all_controls()
        Assert: All four framework keys present (lines 114-119)
        """
        # Act
        results = await mock_manager.verify_all_controls()

        # Assert
        assert "hipaa" in results
        assert "gdpr" in results
        assert "iso27001" in results
        assert "soc2" in results

    async def test_hipaa_controls_from_verify_controls(self, mock_manager):
        """Test HIPAA controls come from hipaa.verify_controls().

        Arrange: Mock HIPAA returning specific controls
        Act: Call verify_all_controls()
        Assert: hipaa controls match mocked return value
        """
        # Act
        results = await mock_manager.verify_all_controls()

        # Assert
        assert results["hipaa"]["encryption_enabled"] is True
        assert results["hipaa"]["audit_logging_enabled"] is True
        mock_manager.hipaa.verify_controls.assert_called_once()

    async def test_gdpr_controls_hardcoded(self, mock_manager):
        """Test GDPR controls include consent_management_enabled.

        Arrange: Mock manager
        Act: Call verify_all_controls()
        Assert: GDPR has consent_management_enabled=True (line 116)
        """
        # Act
        results = await mock_manager.verify_all_controls()

        # Assert
        assert results["gdpr"]["consent_management_enabled"] is True

    async def test_logs_verification_start_and_completion(self, mock_manager):
        """Test logs compliance_verification_started and completed.

        Arrange: Mock manager with logger patched
        Act: Call verify_all_controls()
        Assert: logger.info called for start and completion (lines 112, 123-128)
        """
        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            await mock_manager.verify_all_controls()

        # Assert
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert "compliance_verification_started" in log_messages
        assert "compliance_verification_completed" in log_messages

    async def test_returns_all_compliant_true_when_all_pass(self, mock_manager):
        """Test all_compliant=True logged when all framework controls pass.

        Arrange: All frameworks return all True controls
        Act: Call verify_all_controls()
        Assert: all_compliant=True in completion log (line 122)
        """
        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            await mock_manager.verify_all_controls()

        # Assert
        completion_calls = [
            call
            for call in mock_logger.info.call_args_list
            if call[0][0] == "compliance_verification_completed"
        ]
        assert len(completion_calls) == 1
        assert completion_calls[0][1]["all_compliant"] is True

    async def test_returns_all_compliant_false_when_some_fail(self, mock_manager):
        """Test all_compliant=False logged when some controls fail.

        Arrange: HIPAA returns a failing control
        Act: Call verify_all_controls()
        Assert: all_compliant=False in completion log
        """
        # Arrange
        mock_manager.hipaa.verify_controls = AsyncMock(return_value={"encryption_enabled": False})

        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            await mock_manager.verify_all_controls()

        # Assert
        completion_calls = [
            call
            for call in mock_logger.info.call_args_list
            if call[0][0] == "compliance_verification_completed"
        ]
        assert completion_calls[0][1]["all_compliant"] is False


# ============================================================================
# generate_comprehensive_report() Tests
# ============================================================================


class TestGenerateComprehensiveReport:
    """Tests for generate_comprehensive_report() covering lines 143-186."""

    async def test_returns_report_with_required_keys(self, mock_manager):
        """Test report contains timestamp, overall_compliance, framework_statuses, etc.

        Arrange: Mock manager
        Act: Call generate_comprehensive_report()
        Assert: All required keys present (lines 161-178)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        assert "timestamp" in report
        assert "overall_compliance" in report
        assert "framework_statuses" in report
        assert "frameworks" in report
        assert "summary" in report

    async def test_framework_statuses_contain_all_four_frameworks(self, mock_manager):
        """Test framework_statuses has all four framework keys.

        Arrange: Mock manager
        Act: Call generate_comprehensive_report()
        Assert: hipaa, gdpr, iso27001, soc2 in framework_statuses (lines 152-157)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        statuses = report["framework_statuses"]
        assert "hipaa" in statuses
        assert "gdpr" in statuses
        assert "iso27001" in statuses
        assert "soc2" in statuses

    async def test_overall_compliance_true_when_all_frameworks_pass(self, mock_manager):
        """Test overall_compliance is True when all frameworks are compliant.

        Arrange: All frameworks return compliance_status=True
        Act: Call generate_comprehensive_report()
        Assert: overall_compliance is True (line 159)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        assert report["overall_compliance"] is True

    async def test_overall_compliance_false_when_any_framework_fails(self, mock_manager):
        """Test overall_compliance is False when any framework fails.

        Arrange: HIPAA returns compliance_status=False
        Act: Call generate_comprehensive_report()
        Assert: overall_compliance is False
        """
        # Arrange
        mock_manager.hipaa.generate_compliance_report = AsyncMock(
            return_value={"compliance_status": False, "framework": "HIPAA"}
        )

        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        assert report["overall_compliance"] is False

    async def test_summary_has_correct_total_frameworks(self, mock_manager):
        """Test summary.total_frameworks is 4.

        Arrange: Mock manager
        Act: Call generate_comprehensive_report()
        Assert: summary.total_frameworks == 4 (line 172)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        assert report["summary"]["total_frameworks"] == 4

    async def test_summary_compliance_percentage_is_100_when_all_pass(self, mock_manager):
        """Test compliance_percentage is 100.0 when all frameworks pass.

        Arrange: All frameworks compliant
        Act: Call generate_comprehensive_report()
        Assert: compliance_percentage == 100.0 (lines 174-176)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        assert report["summary"]["compliance_percentage"] == 100.0

    async def test_summary_compliance_percentage_when_half_fail(self, mock_manager):
        """Test compliance_percentage is 50.0 when half of frameworks fail.

        Arrange: 2 of 4 frameworks fail
        Act: Call generate_comprehensive_report()
        Assert: compliance_percentage == 50.0
        """
        # Arrange
        mock_manager.hipaa.generate_compliance_report = AsyncMock(
            return_value={"compliance_status": False}
        )
        mock_manager.iso27001.generate_compliance_report = AsyncMock(
            return_value={"compliance_status": False}
        )

        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        assert report["summary"]["compliance_percentage"] == 50.0

    async def test_report_timestamp_is_iso_format(self, mock_manager):
        """Test report timestamp is valid ISO format string.

        Arrange: Mock manager
        Act: Call generate_comprehensive_report()
        Assert: timestamp is parseable ISO string (line 162)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        timestamp = report["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        assert parsed is not None

    async def test_frameworks_section_contains_individual_reports(self, mock_manager):
        """Test frameworks section contains individual framework reports.

        Arrange: Mock manager
        Act: Call generate_comprehensive_report()
        Assert: frameworks contains hipaa, gdpr, iso27001, soc2 reports (lines 165-170)
        """
        # Act
        report = await mock_manager.generate_comprehensive_report()

        # Assert
        frameworks = report["frameworks"]
        assert "hipaa" in frameworks
        assert "gdpr" in frameworks
        assert "iso27001" in frameworks
        assert "soc2" in frameworks

    async def test_logs_report_generation(self, mock_manager):
        """Test logs report generation start and completion.

        Arrange: Mock manager
        Act: Call generate_comprehensive_report()
        Assert: logger.info called for start and completion
        """
        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            await mock_manager.generate_comprehensive_report()

        # Assert
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert "comprehensive_report_generation_started" in log_messages
        assert "comprehensive_report_generated" in log_messages


# ============================================================================
# get_compliance_status() Tests
# ============================================================================


class TestGetComplianceStatus:
    """Tests for get_compliance_status() covering lines 199-205."""

    async def test_returns_boolean_dict_for_all_frameworks(self, mock_manager):
        """Test returns boolean status for each framework.

        Arrange: All frameworks compliant
        Act: Call get_compliance_status()
        Assert: Returns dict with boolean values for each framework (lines 201-204)
        """
        # Act
        status = await mock_manager.get_compliance_status()

        # Assert
        assert isinstance(status["hipaa"], bool)
        assert isinstance(status["gdpr"], bool)
        assert isinstance(status["iso27001"], bool)
        assert isinstance(status["soc2"], bool)

    async def test_returns_true_for_compliant_frameworks(self, mock_manager):
        """Test returns True for frameworks where all controls pass.

        Arrange: All frameworks with all-True controls
        Act: Call get_compliance_status()
        Assert: All framework statuses are True
        """
        # Act
        status = await mock_manager.get_compliance_status()

        # Assert
        assert status["hipaa"] is True
        assert status["gdpr"] is True
        assert status["iso27001"] is True
        assert status["soc2"] is True

    async def test_returns_false_for_failing_framework(self, mock_manager):
        """Test returns False for frameworks with failing controls.

        Arrange: HIPAA has one failing control
        Act: Call get_compliance_status()
        Assert: hipaa status is False
        """
        # Arrange
        mock_manager.hipaa.verify_controls = AsyncMock(
            return_value={"encryption_enabled": False, "audit_logging": True}
        )

        # Act
        status = await mock_manager.get_compliance_status()

        # Assert
        assert status["hipaa"] is False
        assert status["gdpr"] is True  # Other frameworks still pass


# ============================================================================
# health_check() Tests
# ============================================================================


class TestHealthCheck:
    """Tests for health_check() covering lines 218-229."""

    async def test_returns_health_check_result_with_required_keys(self, mock_manager):
        """Test health_check returns dict with required keys.

        Arrange: Mock manager
        Act: Call health_check()
        Assert: timestamp, healthy, frameworks, initialized present (lines 220-225)
        """
        # Act
        health = await mock_manager.health_check()

        # Assert
        assert "timestamp" in health
        assert "healthy" in health
        assert "frameworks" in health
        assert "initialized" in health

    async def test_healthy_true_when_all_frameworks_pass(self, mock_manager):
        """Test healthy=True when all frameworks are compliant.

        Arrange: All frameworks compliant
        Act: Call health_check()
        Assert: healthy is True (line 222)
        """
        # Act
        health = await mock_manager.health_check()

        # Assert
        assert health["healthy"] is True

    async def test_healthy_false_when_any_framework_fails(self, mock_manager):
        """Test healthy=False when any framework has failing controls.

        Arrange: One framework failing
        Act: Call health_check()
        Assert: healthy is False
        """
        # Arrange
        mock_manager.hipaa.verify_controls = AsyncMock(return_value={"encryption_enabled": False})

        # Act
        health = await mock_manager.health_check()

        # Assert
        assert health["healthy"] is False

    async def test_initialized_reflects_manager_state(self, mock_manager):
        """Test initialized field reflects _initialized attribute.

        Arrange: Manager with _initialized=False
        Act: Call health_check()
        Assert: initialized is False (line 224)
        """
        # Arrange
        mock_manager._initialized = False

        # Act
        health = await mock_manager.health_check()

        # Assert
        assert health["initialized"] is False

    async def test_initialized_true_after_initialize(self, mock_manager):
        """Test initialized=True when manager has been initialized.

        Arrange: Manager with _initialized=True
        Act: Call health_check()
        Assert: initialized is True
        """
        # Arrange
        mock_manager._initialized = True

        # Act
        health = await mock_manager.health_check()

        # Assert
        assert health["initialized"] is True

    async def test_health_timestamp_is_valid_iso_format(self, mock_manager):
        """Test health_check timestamp is valid ISO format.

        Arrange: Mock manager
        Act: Call health_check()
        Assert: timestamp is parseable ISO string (line 221)
        """
        # Act
        health = await mock_manager.health_check()

        # Assert
        timestamp = health["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        assert parsed is not None

    async def test_logs_health_check_result(self, mock_manager):
        """Test health_check logs the result.

        Arrange: Mock manager with logger patched
        Act: Call health_check()
        Assert: logger.info called including 'compliance_health_check' (line 227)
        """
        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            await mock_manager.health_check()

        # Assert - logger.info is called multiple times (verify_all_controls also logs)
        # Verify that 'compliance_health_check' is among the logged events
        log_event_names = [call[0][0] for call in mock_logger.info.call_args_list]
        assert "compliance_health_check" in log_event_names

        # Find the health_check log call and verify the 'health' kwarg
        health_calls = [
            call
            for call in mock_logger.info.call_args_list
            if call[0][0] == "compliance_health_check"
        ]
        assert len(health_calls) == 1
        assert "health" in health_calls[0][1]

    async def test_frameworks_in_health_check_are_boolean_values(self, mock_manager):
        """Test frameworks dict in health_check has boolean values.

        Arrange: Mock manager
        Act: Call health_check()
        Assert: Each framework value is a boolean
        """
        # Act
        health = await mock_manager.health_check()

        # Assert
        for framework, status in health["frameworks"].items():
            assert isinstance(status, bool), f"{framework} should be bool, got {type(status)}"


# ============================================================================
# ComplianceManager Constructor Tests
# ============================================================================


class TestComplianceManagerConstructor:
    """Tests for ComplianceManager.__init__ covering initialization."""

    def test_creates_with_default_encryption_key(self):
        """Test creates manager without providing an encryption key.

        Arrange: No encryption_key
        Act: Create ComplianceManager()
        Assert: Manager created with auto-generated encryption key
        """
        # Act
        mgr = ComplianceManager()

        # Assert
        assert mgr.hipaa is not None
        assert mgr._initialized is False

    def test_creates_with_custom_encryption_key(self):
        """Test creates manager with a custom encryption key.

        Arrange: Custom 32-byte key
        Act: Create ComplianceManager(encryption_key=key)
        Assert: Manager created successfully
        """
        # Arrange
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()

        # Act
        mgr = ComplianceManager(encryption_key=key)

        # Assert
        assert mgr.hipaa is not None

    def test_logs_manager_creation(self):
        """Test logs compliance_manager_created on init.

        Arrange: Mock logger
        Act: Create ComplianceManager()
        Assert: logger.info called with 'compliance_manager_created'
        """
        # Act
        with patch("src.infrastructure.compliance.manager.logger") as mock_logger:
            ComplianceManager()

        # Assert
        mock_logger.info.assert_called_once_with("compliance_manager_created")
