"""Unit tests for user event handlers.

Tests event-driven architecture handlers using best practices:
- AAA pattern (Arrange-Act-Assert)
- Mocking external dependencies (Temporal, event bus)
- Async testing with pytest-asyncio
- Error scenario coverage
- Integration testing of event flow
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.domain.events import UserCreatedEvent, UserDeletedEvent, UserUpdatedEvent


class TestSendWelcomeEmailHandler:
    """Tests for send_welcome_email_handler.

    Best Practice: Test event handlers in isolation
    Design Pattern: Observer pattern testing
    """

    @pytest.mark.asyncio
    async def test_handler_starts_temporal_workflow_on_user_created(self):
        """Test that handler starts Temporal workflow when user is created.

        AAA Pattern:
        - Arrange: Create UserCreatedEvent and mock Temporal client
        - Act: Trigger handler
        - Assert: Workflow started with correct parameters
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            send_welcome_email_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        mock_client = AsyncMock()
        mock_workflow = Mock()

        # Act
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                return_value=mock_client,
            ),
            patch(
                "src.app.tasks.user_tasks.SendWelcomeEmailWorkflow",
                mock_workflow,
            ),
        ):
            await send_welcome_email_handler(event)

        # Assert
        mock_client.start_workflow.assert_called_once()
        call_args = mock_client.start_workflow.call_args

        # Verify workflow parameters
        assert call_args[1]["args"] == [str(user_id), "test@example.com"]
        assert call_args[1]["id"] == f"welcome-email-{user_id}"
        assert call_args[1]["task_queue"] == "user-tasks"

    @pytest.mark.asyncio
    async def test_handler_logs_workflow_start(self):
        """Test that handler logs when starting workflow.

        Best Practice: Verify observability logging
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            send_welcome_email_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        mock_client = AsyncMock()

        # Act
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                return_value=mock_client,
            ),
            patch("src.app.tasks.user_tasks.SendWelcomeEmailWorkflow"),
            patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger,
        ):
            await send_welcome_email_handler(event)

        # Assert - Should log start and completion
        assert mock_logger.info.call_count >= 2
        start_call = mock_logger.info.call_args_list[0]
        assert "sending_welcome_email" in start_call[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception_type",
        [ConnectionError, TimeoutError, OSError],
        ids=["connection_error", "timeout_error", "os_error"],
    )
    async def test_handler_handles_temporal_connection_errors_gracefully(self, exception_type):
        """Test that handler gracefully handles Temporal connection failures.

        Best Practice: Resilience testing - handler failures don't break use case
        Parametrized: Test different connection error types
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            send_welcome_email_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        mock_client = AsyncMock()
        mock_client.start_workflow.side_effect = exception_type("Connection failed")

        # Act & Assert - Should not raise, just log warning
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                return_value=mock_client,
            ),
            patch("src.app.tasks.user_tasks.SendWelcomeEmailWorkflow"),
            patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger,
        ):
            await send_welcome_email_handler(event)  # Should not raise

        # Assert - Warning logged
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args
        assert "failed_to_start_welcome_email_workflow_connection_error" in warning_call[0]

    @pytest.mark.asyncio
    async def test_handler_handles_import_error_when_temporal_not_installed(self):
        """Test that handler handles missing Temporal dependency gracefully.

        Edge Case: Temporal not installed (dev/test environments)
        Best Practice: Graceful degradation
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            send_welcome_email_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act & Assert - Simulate ImportError
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                side_effect=ImportError("No module named 'temporalio'"),
            ),
            patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger,
        ):
            await send_welcome_email_handler(event)  # Should not raise

        # Assert - Info logged (not error, since it's acceptable)
        mock_logger.info.assert_called()
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("temporal_not_available" in call for call in info_calls)

    @pytest.mark.asyncio
    async def test_handler_logs_unexpected_errors_without_failing(self):
        """Test that unexpected errors are logged but don't fail handler.

        Best Practice: Resilient error handling - don't break event processing
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            send_welcome_email_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        mock_client = AsyncMock()
        mock_client.start_workflow.side_effect = RuntimeError("Unexpected error")

        # Act & Assert
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                return_value=mock_client,
            ),
            patch("src.app.tasks.user_tasks.SendWelcomeEmailWorkflow"),
            patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger,
        ):
            await send_welcome_email_handler(event)  # Should not raise

        # Assert - Exception logged
        mock_logger.exception.assert_called_once()
        exception_call = mock_logger.exception.call_args
        assert "failed_to_start_welcome_email_workflow_unexpected" in exception_call[0]


class TestLogUserCreationHandler:
    """Tests for log_user_creation_handler.

    Best Practice: Test audit logging separately
    """

    @pytest.mark.asyncio
    async def test_handler_logs_user_creation_event(self):
        """Test that handler logs user creation for audit trail.

        Best Practice: Verify audit logging compliance
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_creation_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await log_user_creation_handler(event)

        # Assert
        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args

        # Verify audit log structure
        assert "user_created_audit" in log_call[0]
        assert log_call[1]["user_id"] == str(user_id)
        assert log_call[1]["email"] == "test@example.com"
        assert log_call[1]["username"] == "testuser"
        assert log_call[1]["event_type"] == "user.created"
        assert "timestamp" in log_call[1]

    @pytest.mark.asyncio
    async def test_handler_includes_iso_timestamp(self):
        """Test that handler includes ISO format timestamp.

        Best Practice: Standard timestamp format for audit logs
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_creation_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await log_user_creation_handler(event)

        # Assert - Timestamp is ISO format
        log_call = mock_logger.info.call_args
        timestamp = log_call[1]["timestamp"]
        # Should be ISO format: 2024-01-01T12:00:00.123456
        assert "T" in timestamp  # ISO format contains 'T'
        assert len(timestamp) > 19  # At least YYYY-MM-DDTHH:MM:SS


class TestSyncUserToAnalyticsHandler:
    """Tests for sync_user_to_analytics_handler.

    Best Practice: Test placeholder implementations
    """

    @pytest.mark.asyncio
    async def test_handler_logs_analytics_sync_placeholder(self):
        """Test that placeholder handler logs sync attempt.

        Note: Currently placeholder implementation
        TODO: Update when actual analytics integration added
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            sync_user_to_analytics_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await sync_user_to_analytics_handler(event)

        # Assert - Debug log for placeholder
        mock_logger.debug.assert_called_once()
        debug_call = mock_logger.debug.call_args
        assert "user_analytics_sync" in debug_call[0]
        assert "placeholder" in debug_call[1]["message"]

    @pytest.mark.asyncio
    async def test_handler_handles_analytics_failures_gracefully(self):
        """Test that analytics failures don't break event processing.

        Best Practice: Non-critical operations should fail gracefully
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            sync_user_to_analytics_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act & Assert - Simulate logger.debug raising exception
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            mock_logger.debug.side_effect = RuntimeError("Analytics service down")

            # Should handle error gracefully
            await sync_user_to_analytics_handler(event)

            # Warning should be logged
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args
            assert "analytics_sync_failed" in warning_call[0]


class TestLogUserUpdateHandler:
    """Tests for log_user_update_handler.

    Best Practice: Test all event types
    """

    @pytest.mark.asyncio
    async def test_handler_logs_user_update_event(self):
        """Test that handler logs user updates for audit trail."""
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_update_handler,
        )

        user_id = uuid4()
        event = UserUpdatedEvent(aggregate_id=user_id, user_id=user_id)

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await log_user_update_handler(event)

        # Assert
        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args
        assert "user_updated_audit" in log_call[0]
        assert log_call[1]["user_id"] == str(user_id)
        assert log_call[1]["event_type"] == "user.updated"


class TestLogUserDeletionHandler:
    """Tests for log_user_deletion_handler.

    Best Practice: Test deletion audit trail
    """

    @pytest.mark.asyncio
    async def test_handler_logs_user_deletion_event(self):
        """Test that handler logs user deletions for compliance."""
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_deletion_handler,
        )

        user_id = uuid4()
        event = UserDeletedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test@example.com",
            username="testuser",
            deleted_at=datetime.now(UTC),
        )

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await log_user_deletion_handler(event)

        # Assert
        mock_logger.info.assert_called_once()
        log_call = mock_logger.info.call_args
        assert "user_deleted_audit" in log_call[0]
        assert log_call[1]["user_id"] == str(user_id)
        assert log_call[1]["event_type"] == "user.deleted"
        assert log_call[1]["soft_delete"] is True


# Integration tests marker
@pytest.mark.integration
class TestEventHandlerIntegration:
    """Integration tests for event handler system.

    Best Practice: Test event flow end-to-end
    """

    @pytest.mark.asyncio
    async def test_multiple_handlers_triggered_for_single_event(self):
        """Test that multiple handlers can subscribe to same event.

        Integration Test: Event bus publishes to all subscribers
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_creation_handler,
            send_welcome_email_handler,
            sync_user_to_analytics_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act - Call all handlers manually (simulating event bus)
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                return_value=AsyncMock(),
            ),
            patch("src.app.tasks.user_tasks.SendWelcomeEmailWorkflow"),
            patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger,
        ):
            # Simulate event bus calling all handlers
            await send_welcome_email_handler(event)
            await log_user_creation_handler(event)
            await sync_user_to_analytics_handler(event)

        # Assert - All handlers executed
        # At least 3 info logs (1 from each handler minimum)
        assert mock_logger.info.call_count >= 3

    @pytest.mark.asyncio
    async def test_handler_failure_does_not_affect_other_handlers(self):
        """Test that one handler failing doesn't break others.

        Best Practice: Isolation - handlers should be independent
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_creation_handler,
            send_welcome_email_handler,
        )

        user_id = uuid4()
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username="testuser"
        )

        # Act - First handler fails
        with (
            patch(
                "src.infrastructure.temporal_client.get_temporal_client",
                side_effect=RuntimeError("Temporal down"),
            ),
            patch("src.app.tasks.user_tasks.SendWelcomeEmailWorkflow"),
            patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger,
        ):
            # First handler fails but doesn't raise
            await send_welcome_email_handler(event)

            # Second handler should still work
            await log_user_creation_handler(event)

        # Assert - Both handlers executed
        # First handler logged exception
        assert mock_logger.exception.call_count >= 1
        # Second handler logged successfully
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("user_created_audit" in call for call in info_calls)


class TestEventHandlerEdgeCases:
    """Edge case tests for event handlers.

    Best Practice: Comprehensive edge case coverage
    """

    @pytest.mark.asyncio
    async def test_handler_with_special_characters_in_email(self):
        """Test handler with email containing special characters."""
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_creation_handler,
        )

        user_id = uuid4()
        # Email with special characters
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="test+tag@example.co.uk",
            username="test_user-123",
        )

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await log_user_creation_handler(event)

        # Assert - Should handle special characters
        log_call = mock_logger.info.call_args
        assert log_call[1]["email"] == "test+tag@example.co.uk"
        assert log_call[1]["username"] == "test_user-123"

    @pytest.mark.asyncio
    async def test_handler_with_very_long_username(self):
        """Test handler with maximum length username.

        Edge Case: Boundary value testing
        """
        # Arrange
        from src.app.events.handlers.user_event_handlers import (
            log_user_creation_handler,
        )

        user_id = uuid4()
        long_username = "a" * 255  # Maximum typical username length
        event = UserCreatedEvent(
            aggregate_id=user_id, user_id=user_id, email="test@example.com", username=long_username
        )

        # Act
        with patch("src.app.events.handlers.user_event_handlers.logger") as mock_logger:
            await log_user_creation_handler(event)

        # Assert - Should handle long username
        log_call = mock_logger.info.call_args
        assert log_call[1]["username"] == long_username
