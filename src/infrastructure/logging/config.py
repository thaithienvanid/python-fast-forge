"""Structured logging configuration with OpenTelemetry integration."""

import logging
import sys
from typing import Any, cast

import structlog
from opentelemetry import trace

from src.infrastructure.config import Settings
from src.utils.sanitizer import sanitize_dict


def sanitize_sensitive_data(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Sanitize sensitive fields from log events.

    Redacts sensitive information like passwords, API keys, tokens, etc.
    to prevent accidental exposure in logs.

    Uses shared sanitization logic from src.utils.sanitizer.

    Args:
        logger: Logger instance (unused)
        method_name: Method name (unused)
        event_dict: Event dictionary to sanitize

    Returns:
        Sanitized event dictionary
    """
    return sanitize_dict(event_dict, recursive=True)


def add_trace_context(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add OpenTelemetry trace context to log events.

    Adds only trace_id, span_id, and trace_flags (safe hex values) to logs for
    correlation. Span attributes containing sensitive data (HTTP headers, request
    bodies, DB queries) are NOT added to logs and are sanitized at export time
    by SanitizingSpanProcessor before being sent to Jaeger/OTLP collectors.
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        span_context = span.get_span_context()
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
        event_dict["trace_flags"] = format(span_context.trace_flags, "02x")
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structured logging with trace context."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_context,  # Add trace context to logs
        sanitize_sensitive_data,  # Sanitize sensitive fields (GDPR, PCI-DSS compliance)
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development:
        # Pretty console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=cast("Any", processors),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
