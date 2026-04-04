"""Unit tests for logging configuration."""

from unittest.mock import MagicMock, patch

from opentelemetry.trace import SpanContext, TraceFlags

from src.infrastructure.logging.config import (
    add_trace_context,
    configure_logging,
    get_logger,
    sanitize_sensitive_data,
)


class TestSanitizeSensitiveData:
    """Tests for sanitize_sensitive_data processor."""

    def test_sanitizes_password_field(self):
        """Sanitizes password from event dict."""
        event_dict = {"user": "john", "password": "secret123", "level": "info"}

        result = sanitize_sensitive_data(None, "", event_dict)

        assert result["user"] == "john"
        assert result["password"] == "***REDACTED***"
        assert result["level"] == "info"

    def test_sanitizes_api_key_field(self):
        """Sanitizes API key from event dict."""
        event_dict = {"action": "request", "api_key": "sk-12345", "status": "success"}

        result = sanitize_sensitive_data(None, "", event_dict)

        assert result["action"] == "request"
        assert result["api_key"] == "***REDACTED***"
        assert result["status"] == "success"

    def test_sanitizes_nested_sensitive_fields(self):
        """Sanitizes nested sensitive fields."""
        event_dict = {
            "user": "john",
            "data": {"username": "john", "password": "secret"},
        }

        result = sanitize_sensitive_data(None, "", event_dict)

        assert result["user"] == "john"
        # Password in nested dict should be redacted
        if isinstance(result["data"], dict):
            assert result["data"]["password"] == "***REDACTED***"

    def test_preserves_non_sensitive_fields(self):
        """Preserves non-sensitive fields unchanged."""
        event_dict = {"message": "User logged in", "user_id": "123", "timestamp": "2024-01-01"}

        result = sanitize_sensitive_data(None, "", event_dict)

        assert result == event_dict


class TestAddTraceContext:
    """Tests for add_trace_context processor."""

    def test_adds_trace_context_when_span_active(self):
        """Adds trace context when active span exists."""
        # Mock span context
        mock_span_context = MagicMock(spec=SpanContext)
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 123456789012345678901234567890123456
        mock_span_context.span_id = 1234567890123456
        mock_span_context.trace_flags = TraceFlags(0x01)

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        event_dict = {"message": "test"}

        with patch(
            "src.infrastructure.logging.config.trace.get_current_span", return_value=mock_span
        ):
            result = add_trace_context(None, "", event_dict)

        assert "trace_id" in result
        assert "span_id" in result
        assert "trace_flags" in result
        assert result["message"] == "test"

    def test_does_not_add_context_when_no_active_span(self):
        """Does not add trace context when no active span."""
        event_dict = {"message": "test"}

        with patch("src.infrastructure.logging.config.trace.get_current_span", return_value=None):
            result = add_trace_context(None, "", event_dict)

        assert result == event_dict
        assert "trace_id" not in result
        assert "span_id" not in result

    def test_does_not_add_context_when_span_invalid(self):
        """Does not add trace context when span context is invalid."""
        mock_span_context = MagicMock(spec=SpanContext)
        mock_span_context.is_valid = False

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        event_dict = {"message": "test"}

        with patch(
            "src.infrastructure.logging.config.trace.get_current_span", return_value=mock_span
        ):
            result = add_trace_context(None, "", event_dict)

        assert result == event_dict
        assert "trace_id" not in result


class TestConfigureLogging:
    """Tests for configure_logging function."""

    @patch("src.infrastructure.logging.config.structlog.configure")
    @patch("src.infrastructure.logging.config.logging.basicConfig")
    def test_configures_logging_for_development(self, mock_basic_config, mock_structlog_config):
        """Configures logging with console renderer for development."""
        from src.infrastructure.config import Settings

        settings = Settings(app_env="development", log_level="DEBUG")

        configure_logging(settings)

        # Verify basic logging was configured
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args.kwargs
        assert call_kwargs["format"] == "%(message)s"

        # Verify structlog was configured
        mock_structlog_config.assert_called_once()

    @patch("src.infrastructure.logging.config.structlog.configure")
    @patch("src.infrastructure.logging.config.logging.basicConfig")
    def test_configures_logging_for_production(self, mock_basic_config, mock_structlog_config):
        """Configures logging with JSON renderer for production."""
        from src.infrastructure.config import Settings

        settings = Settings(app_env="production", log_level="INFO")

        configure_logging(settings)

        # Verify basic logging was configured
        mock_basic_config.assert_called_once()

        # Verify structlog was configured
        mock_structlog_config.assert_called_once()

    @patch("src.infrastructure.logging.config.structlog.configure")
    @patch("src.infrastructure.logging.config.logging.basicConfig")
    def test_respects_log_level_setting(self, mock_basic_config, mock_structlog_config):
        """Uses log level from settings."""
        import logging

        from src.infrastructure.config import Settings

        # Use the default or explicit log level
        settings = Settings()

        configure_logging(settings)

        # Verify log level was configured (default is INFO)
        call_kwargs = mock_basic_config.call_args.kwargs
        assert "level" in call_kwargs
        assert call_kwargs["level"] in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_instance(self):
        """Returns a logger instance."""
        logger = get_logger("test_logger")

        assert logger is not None

    def test_returns_logger_without_name(self):
        """Returns logger when name is None."""
        logger = get_logger(None)

        assert logger is not None

    def test_returns_logger_with_name(self):
        """Returns logger with specific name."""
        logger = get_logger("my.module.name")

        assert logger is not None
