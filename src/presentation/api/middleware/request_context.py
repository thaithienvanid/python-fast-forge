"""Request context middleware with OpenTelemetry trace_id support.

Implements W3C Trace Context standard with automatic trace_id extraction:
1. traceparent header (W3C Trace Context via OpenTelemetry)
2. CF-Ray (Cloudflare trace - for CDN deployments)
3. Auto-generated UUIDv7 (fallback when OpenTelemetry disabled)

When OpenTelemetry is enabled:
- FastAPIInstrumentor automatically extracts trace_id from traceparent header
- If no traceparent, automatically generates new trace_id for root span
- trace_id flows through all services via W3C Trace Context propagation

The trace_id flows through:
- Request context (request.state.trace_id)
- Structured logging (structlog context)
- OpenTelemetry spans (automatic)
- Response headers (X-Trace-ID)
- Downstream services (automatic propagation via httpx instrumentation)
"""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from uuid_extension import uuid7


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware for trace_id management following W3C Trace Context standard.

    Provides a single source of truth for request tracing across:
    - Distributed tracing (OpenTelemetry W3C Trace Context)
    - External CDNs (Cloudflare CF-Ray)
    - Legacy systems (fallback to UUIDv7)
    - Downstream services (httpx automatic propagation)

    The middleware ensures trace_id is available in:
    - request.state.trace_id (for handlers)
    - structlog context (for logging)
    - OpenTelemetry span (automatic via FastAPIInstrumentor)
    - X-Trace-ID response header (for clients)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Extract/generate trace_id and bind to request context.

        Priority order for trace_id:
        1. OpenTelemetry trace_id (from traceparent header or auto-generated)
           - FastAPIInstrumentor extracts from traceparent
           - Auto-generates new trace_id if no traceparent
        2. CF-Ray (Cloudflare trace ID - when OpenTelemetry disabled)
        3. Generate new UUIDv7 (when OpenTelemetry disabled)

        Also extracts client IP for logging and rate limiting.
        """
        # Get current OpenTelemetry span context
        span = trace.get_current_span()
        span_context = span.get_span_context()

        # Extract trace_id (OpenTelemetry or fallback)
        trace_id = self._extract_trace_id(request, span_context)

        # Extract client IP
        client_ip = self._extract_client_ip(request)

        # Bind to structlog context (appears in all logs)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            client_ip=client_ip,
            method=request.method,
            path=request.url.path,
        )

        # Store in request state (accessible in handlers)
        request.state.trace_id = trace_id
        request.state.client_ip = client_ip

        # Add to OpenTelemetry span as attributes (if tracing enabled)
        if span.is_recording():
            span.set_attribute("trace_id", trace_id)
            span.set_attribute("client_ip", client_ip)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.client_ip", client_ip)

        # Process request
        response = await call_next(request)

        # Add trace_id to response headers (W3C standard)
        response.headers["X-Trace-ID"] = trace_id

        return response

    def _extract_trace_id(
        self,
        request: Request,
        span_context: trace.SpanContext,
    ) -> str:
        """Extract trace_id with proper priority.

        Args:
            request: FastAPI request object
            span_context: OpenTelemetry span context

        Returns:
            Trace ID string

        Priority:
        1. OpenTelemetry trace_id (from traceparent or auto-generated)
           - When FastAPIInstrumentor is active, it automatically:
             * Extracts trace_id from incoming traceparent header
             * Generates new trace_id if no traceparent (root span)
           - This is the W3C Trace Context standard
        2. CF-Ray (Cloudflare trace - when OpenTelemetry disabled)
        3. Generate UUIDv7 (when OpenTelemetry disabled)

        Note: X-Request-ID and X-Correlation-ID are deprecated.
        Use traceparent header (W3C standard) instead.
        """
        # Priority 1: OpenTelemetry trace_id (W3C Trace Context standard)
        # FastAPIInstrumentor automatically extracts from traceparent header
        # or generates new trace_id for root span
        if span_context.is_valid:
            # Format trace_id as 32-character hex string (128-bit)
            return format(span_context.trace_id, "032x")

        # Priority 2: Cloudflare CF-Ray (when OpenTelemetry disabled)
        # Useful for CDN deployments without full tracing
        if cf_ray := request.headers.get("CF-Ray"):
            return cf_ray

        # Priority 3: Generate new UUIDv7 (time-ordered, sortable)
        # Fallback when OpenTelemetry is disabled
        return str(uuid7())

    def _extract_client_ip(self, request: Request) -> str:
        """Extract client IP address with proper priority.

        Args:
            request: FastAPI request object

        Returns:
            Client IP address

        Priority:
        1. CF-Connecting-IP (Cloudflare real client IP)
        2. X-Forwarded-For (first IP, most trusted proxy)
        3. X-Real-IP (nginx/other reverse proxy)
        4. request.client.host (direct connection)
        """
        # Priority 1: Cloudflare real client IP (most trusted for CDN)
        if cf_connecting_ip := request.headers.get("CF-Connecting-IP"):
            return cf_connecting_ip

        # Priority 2: X-Forwarded-For (take first/leftmost IP)
        if x_forwarded_for := request.headers.get("X-Forwarded-For"):
            # Format: "client, proxy1, proxy2"
            # Take the leftmost (original client) IP
            return x_forwarded_for.split(",")[0].strip()

        # Priority 3: X-Real-IP (nginx/other reverse proxy)
        if x_real_ip := request.headers.get("X-Real-IP"):
            return x_real_ip

        # Priority 4: Direct connection (no proxy)
        if request.client and request.client.host:
            return request.client.host

        # Fallback
        return "unknown"
