"""OpenTelemetry span attribute sanitizer to prevent sensitive data exposure."""

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

from src.utils.sanitizer import SENSITIVE_PATTERNS, sanitize_value


class SanitizingSpanProcessor(SpanProcessor):
    """Span processor that sanitizes sensitive attributes before export.

    This processor runs before spans are exported to Jaeger/OTLP collectors,
    preventing accidental exposure of sensitive data in distributed traces.

    It sanitizes:
    - HTTP headers (Authorization, Cookie, etc.)
    - Request/response bodies
    - Database queries (may contain PII in WHERE clauses)
    - Message payloads
    - Any attribute matching sensitive patterns

    Uses shared sanitization logic from src.utils.sanitizer.

    Note: This only sanitizes span attributes. Span IDs, trace IDs, and span
    names remain unchanged.
    """

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Called when a span is started.

        We don't need to do anything on start since we sanitize on end.
        """

    def on_end(self, span: ReadableSpan) -> None:
        """Called when a span is ended. Sanitize attributes before export.

        Args:
            span: The span that has ended
        """
        if not span.attributes:
            return

        # Sanitize span attributes using shared utility with length shown for debugging
        sanitized_attributes = {}
        for key, value in span.attributes.items():
            sanitized_attributes[key] = sanitize_value(
                key, value, SENSITIVE_PATTERNS, show_length=True
            )

        # Update span attributes in-place
        # Note: This is a bit hacky but necessary since ReadableSpan doesn't
        # provide a public API to modify attributes
        if hasattr(span, "_attributes"):
            span._attributes = sanitized_attributes

    def shutdown(self) -> None:
        """Called when the tracer provider is shutdown."""

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any buffered spans.

        Args:
            timeout_millis: Timeout in milliseconds

        Returns:
            True if flush succeeded, False otherwise
        """
        return True


def create_sanitizing_processor() -> SanitizingSpanProcessor:
    """Create a sanitizing span processor instance.

    Returns:
        Configured sanitizing span processor
    """
    return SanitizingSpanProcessor()
