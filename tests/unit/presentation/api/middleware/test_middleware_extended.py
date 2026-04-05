"""Extended unit tests for API middleware.

Covers missing lines in:
- src/presentation/api/middleware/security_headers.py (19 lines, 26% coverage)
  - HSTS headers in production
  - CSP headers for API endpoints
  - CSP headers for docs endpoints
  - X-Frame-Options
  - X-Content-Type-Options
  - Referrer-Policy
  - Permissions-Policy

- src/presentation/api/middleware/request_context.py (41 lines, 18% coverage)
  - Trace ID from OpenTelemetry span
  - Trace ID from CF-Ray header
  - Trace ID auto-generated (fallback)
  - Client IP from CF-Connecting-IP
  - Client IP from X-Forwarded-For
  - Client IP from X-Real-IP
  - Client IP from direct connection
  - Client IP fallback
  - structlog context binding
  - Response X-Trace-ID header

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- Mock Request/Response/Settings objects
- pytest.mark.parametrize for multiple scenarios
"""

from unittest.mock import MagicMock, patch

import pytest

from src.presentation.api.middleware.request_context import RequestContextMiddleware
from src.presentation.api.middleware.security_headers import SecurityHeadersMiddleware


# ============================================================================
# Shared Fixtures
# ============================================================================


def _make_mock_request(path: str = "/api/v1/users", headers: dict | None = None):
    """Create a mock FastAPI Request object.

    Args:
        path: Request URL path
        headers: Optional request headers dict

    Returns:
        MagicMock mimicking a FastAPI Request
    """
    request = MagicMock()
    request.url.path = path
    request.url.query = ""
    request.method = "GET"
    request.headers = headers or {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.state = MagicMock()
    return request


def _make_mock_response():
    """Create a mock Response with a mutable headers dict."""
    response = MagicMock()
    response.headers = {}
    return response


@pytest.fixture
def mock_request():
    """Default mock request for API endpoint."""
    return _make_mock_request()


@pytest.fixture
def mock_response():
    """Default mock response."""
    return _make_mock_response()


# ============================================================================
# SecurityHeadersMiddleware Tests
# ============================================================================


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware.dispatch."""

    async def _dispatch_request(
        self, path: str, is_production: bool = False, is_development: bool = False
    ):
        """Helper to dispatch a request and return the response headers.

        Args:
            path: Request path
            is_production: Whether settings should simulate production
            is_development: Whether settings should simulate development

        Returns:
            Response headers dict
        """
        mock_settings = MagicMock()
        mock_settings.is_production = is_production
        mock_settings.is_development = is_development

        request = _make_mock_request(path=path)
        response = _make_mock_response()

        async def call_next(req):
            return response

        with patch(
            "src.presentation.api.middleware.security_headers.get_settings",
            return_value=mock_settings,
        ):
            middleware = SecurityHeadersMiddleware(app=MagicMock())
            await middleware.dispatch(request, call_next)

        return response.headers

    async def test_sets_x_frame_options_deny(self):
        """Test X-Frame-Options is set to DENY on all responses.

        Arrange: Any request
        Act: Dispatch request
        Assert: X-Frame-Options header is DENY
        """
        headers = await self._dispatch_request("/api/v1/users")

        assert headers["X-Frame-Options"] == "DENY"

    async def test_sets_x_content_type_options_nosniff(self):
        """Test X-Content-Type-Options is set to nosniff.

        Arrange: Any request
        Act: Dispatch request
        Assert: X-Content-Type-Options is nosniff
        """
        headers = await self._dispatch_request("/api/v1/users")

        assert headers["X-Content-Type-Options"] == "nosniff"

    async def test_sets_x_xss_protection(self):
        """Test X-XSS-Protection is set.

        Arrange: Any request
        Act: Dispatch request
        Assert: X-XSS-Protection header is set
        """
        headers = await self._dispatch_request("/api/v1/users")

        assert headers["X-XSS-Protection"] == "1; mode=block"

    async def test_sets_referrer_policy(self):
        """Test Referrer-Policy is set.

        Arrange: Any request
        Act: Dispatch request
        Assert: Referrer-Policy header is set
        """
        headers = await self._dispatch_request("/api/v1/users")

        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_sets_permissions_policy(self):
        """Test Permissions-Policy is set.

        Arrange: Any request
        Act: Dispatch request
        Assert: Permissions-Policy header is set (contains geolocation)
        """
        headers = await self._dispatch_request("/api/v1/users")

        assert "Permissions-Policy" in headers
        assert "geolocation=()" in headers["Permissions-Policy"]

    async def test_hsts_not_set_in_development(self):
        """Test HSTS header is NOT set in non-production environments.

        Arrange: Non-production settings
        Act: Dispatch request
        Assert: Strict-Transport-Security header absent
        """
        headers = await self._dispatch_request("/api/v1/users", is_production=False)

        assert "Strict-Transport-Security" not in headers

    async def test_hsts_set_in_production(self):
        """Test HSTS header is set in production environment.

        Arrange: Production settings
        Act: Dispatch request
        Assert: Strict-Transport-Security header present with max-age
        """
        headers = await self._dispatch_request("/api/v1/users", is_production=True)

        assert "Strict-Transport-Security" in headers
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        assert "includeSubDomains" in headers["Strict-Transport-Security"]

    async def test_relaxed_csp_for_docs_endpoint(self):
        """Test relaxed CSP is applied for /docs endpoint.

        Arrange: Request to /docs path
        Act: Dispatch request
        Assert: CSP allows CDN resources (cdn.jsdelivr.net)
        """
        headers = await self._dispatch_request("/docs", is_development=False)

        assert "Content-Security-Policy" in headers
        assert "cdn.jsdelivr.net" in headers["Content-Security-Policy"]

    async def test_relaxed_csp_for_redoc_endpoint(self):
        """Test relaxed CSP is applied for /redoc endpoint.

        Arrange: Request to /redoc path
        Act: Dispatch request
        Assert: CSP allows CDN resources
        """
        headers = await self._dispatch_request("/redoc", is_development=False)

        assert "cdn.jsdelivr.net" in headers["Content-Security-Policy"]

    async def test_relaxed_csp_for_openapi_json_endpoint(self):
        """Test relaxed CSP is applied for /openapi.json endpoint.

        Arrange: Request to /openapi.json path
        Act: Dispatch request
        Assert: CSP allows CDN resources
        """
        headers = await self._dispatch_request("/openapi.json", is_development=False)

        assert "cdn.jsdelivr.net" in headers["Content-Security-Policy"]

    async def test_relaxed_csp_in_development(self):
        """Test relaxed CSP is applied in development regardless of path.

        Arrange: Development settings, non-docs path
        Act: Dispatch request
        Assert: CSP allows CDN resources
        """
        headers = await self._dispatch_request(
            "/api/v1/users", is_development=True, is_production=False
        )

        assert "cdn.jsdelivr.net" in headers["Content-Security-Policy"]

    async def test_strict_csp_for_api_endpoint_in_production(self):
        """Test strict CSP applied for API endpoints in production.

        Arrange: Production settings, API endpoint
        Act: Dispatch request
        Assert: CSP does not contain CDN URLs
        """
        headers = await self._dispatch_request(
            "/api/v1/users", is_production=True, is_development=False
        )

        assert "Content-Security-Policy" in headers
        assert "cdn.jsdelivr.net" not in headers["Content-Security-Policy"]

    @pytest.mark.parametrize(
        ("path", "is_development", "expects_cdn"),
        [
            ("/docs", False, True),
            ("/redoc", False, True),
            ("/openapi.json", False, True),
            ("/api/v1/users", True, True),
            ("/api/v1/users", False, False),
        ],
        ids=["docs_path", "redoc_path", "openapi_path", "dev_mode", "api_production"],
    )
    async def test_csp_cdn_based_on_path_and_env(self, path, is_development, expects_cdn):
        """Parametrized test for CSP CDN inclusion logic.

        Arrange: Various path and environment combinations
        Act: Dispatch request
        Assert: CSP contains CDN based on path/env
        """
        headers = await self._dispatch_request(path, is_development=is_development)

        if expects_cdn:
            assert "cdn.jsdelivr.net" in headers.get("Content-Security-Policy", "")
        else:
            assert "cdn.jsdelivr.net" not in headers.get("Content-Security-Policy", "")


# ============================================================================
# RequestContextMiddleware Tests
# ============================================================================


class TestRequestContextMiddleware:
    """Tests for RequestContextMiddleware.dispatch and helper methods."""

    async def test_adds_trace_id_to_response_headers(self):
        """Test that X-Trace-ID is added to the response.

        Arrange: Request, mock span with invalid context (fallback trace_id)
        Act: Dispatch request
        Assert: X-Trace-ID in response headers
        """
        request = _make_mock_request()
        response = _make_mock_response()

        async def call_next(req):
            return response

        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context = MagicMock(return_value=mock_span_context)
        mock_span.is_recording = MagicMock(return_value=False)

        with (
            patch("src.presentation.api.middleware.request_context.trace") as mock_trace,
            patch("src.presentation.api.middleware.request_context.structlog") as mock_structlog,
        ):
            mock_trace.get_current_span = MagicMock(return_value=mock_span)
            mock_structlog.contextvars.clear_contextvars = MagicMock()
            mock_structlog.contextvars.bind_contextvars = MagicMock()

            middleware = RequestContextMiddleware(app=MagicMock())
            await middleware.dispatch(request, call_next)

        assert "X-Trace-ID" in response.headers

    async def test_stores_trace_id_in_request_state(self):
        """Test that trace_id is stored in request.state.

        Arrange: Request with no OpenTelemetry span, no CF-Ray
        Act: Dispatch request
        Assert: request.state.trace_id is set
        """
        request = _make_mock_request()
        response = _make_mock_response()

        async def call_next(req):
            return response

        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context = MagicMock(return_value=mock_span_context)
        mock_span.is_recording = MagicMock(return_value=False)

        with (
            patch("src.presentation.api.middleware.request_context.trace") as mock_trace,
            patch("src.presentation.api.middleware.request_context.structlog") as mock_structlog,
        ):
            mock_trace.get_current_span = MagicMock(return_value=mock_span)
            mock_structlog.contextvars.clear_contextvars = MagicMock()
            mock_structlog.contextvars.bind_contextvars = MagicMock()

            middleware = RequestContextMiddleware(app=MagicMock())
            await middleware.dispatch(request, call_next)

        assert hasattr(request.state, "trace_id")

    async def test_stores_client_ip_in_request_state(self):
        """Test that client_ip is stored in request.state.

        Arrange: Request with direct IP
        Act: Dispatch request
        Assert: request.state.client_ip is set
        """
        request = _make_mock_request()
        response = _make_mock_response()

        async def call_next(req):
            return response

        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context = MagicMock(return_value=mock_span_context)
        mock_span.is_recording = MagicMock(return_value=False)

        with (
            patch("src.presentation.api.middleware.request_context.trace") as mock_trace,
            patch("src.presentation.api.middleware.request_context.structlog") as mock_structlog,
        ):
            mock_trace.get_current_span = MagicMock(return_value=mock_span)
            mock_structlog.contextvars.clear_contextvars = MagicMock()
            mock_structlog.contextvars.bind_contextvars = MagicMock()

            middleware = RequestContextMiddleware(app=MagicMock())
            await middleware.dispatch(request, call_next)

        assert hasattr(request.state, "client_ip")

    async def test_adds_span_attributes_when_recording(self):
        """Test that span attributes are set when span is recording.

        Arrange: Mock span that is_recording()=True
        Act: Dispatch request
        Assert: span.set_attribute called
        """
        request = _make_mock_request()
        response = _make_mock_response()

        async def call_next(req):
            return response

        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context = MagicMock(return_value=mock_span_context)
        mock_span.is_recording = MagicMock(return_value=True)
        mock_span.set_attribute = MagicMock()

        with (
            patch("src.presentation.api.middleware.request_context.trace") as mock_trace,
            patch("src.presentation.api.middleware.request_context.structlog") as mock_structlog,
        ):
            mock_trace.get_current_span = MagicMock(return_value=mock_span)
            mock_structlog.contextvars.clear_contextvars = MagicMock()
            mock_structlog.contextvars.bind_contextvars = MagicMock()

            middleware = RequestContextMiddleware(app=MagicMock())
            await middleware.dispatch(request, call_next)

        mock_span.set_attribute.assert_called()


class TestExtractTraceId:
    """Tests for RequestContextMiddleware._extract_trace_id."""

    def test_uses_otel_trace_id_when_valid_span(self):
        """Test that OpenTelemetry trace_id is used when span context is valid.

        Arrange: Valid OpenTelemetry span context
        Act: Call _extract_trace_id
        Assert: Returns formatted trace_id from span context
        """
        middleware = RequestContextMiddleware(app=MagicMock())

        request = _make_mock_request()
        span_context = MagicMock()
        span_context.is_valid = True
        span_context.trace_id = 0xABCDEF1234567890ABCDEF1234567890

        result = middleware._extract_trace_id(request, span_context)

        assert result == "abcdef1234567890abcdef1234567890"

    def test_uses_cf_ray_when_span_invalid(self):
        """Test that CF-Ray header is used when OpenTelemetry span is invalid.

        Arrange: Invalid span context, CF-Ray header present
        Act: Call _extract_trace_id
        Assert: Returns CF-Ray header value
        """
        middleware = RequestContextMiddleware(app=MagicMock())

        request = _make_mock_request(headers={"CF-Ray": "abc123xyz-AMS"})
        span_context = MagicMock()
        span_context.is_valid = False

        result = middleware._extract_trace_id(request, span_context)

        assert result == "abc123xyz-AMS"

    def test_generates_uuid_when_no_span_and_no_cf_ray(self):
        """Test that a UUID is generated when no span and no CF-Ray.

        Arrange: Invalid span context, no CF-Ray header
        Act: Call _extract_trace_id
        Assert: Returns a non-empty string (UUIDv7)
        """
        middleware = RequestContextMiddleware(app=MagicMock())

        request = _make_mock_request(headers={})
        span_context = MagicMock()
        span_context.is_valid = False

        with patch("src.presentation.api.middleware.request_context.uuid7") as mock_uuid7:
            mock_uuid7.return_value = MagicMock()
            mock_uuid7.return_value.__str__ = MagicMock(return_value="generated-uuid-value")

            result = middleware._extract_trace_id(request, span_context)

        assert result == "generated-uuid-value"
        mock_uuid7.assert_called_once()


class TestExtractClientIp:
    """Tests for RequestContextMiddleware._extract_client_ip."""

    def test_returns_cf_connecting_ip_first(self):
        """Test CF-Connecting-IP takes priority.

        Arrange: Request with CF-Connecting-IP header
        Act: Call _extract_client_ip
        Assert: Returns CF-Connecting-IP value
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={"CF-Connecting-IP": "1.2.3.4"})

        result = middleware._extract_client_ip(request)

        assert result == "1.2.3.4"

    def test_returns_x_forwarded_for_when_no_cf_ip(self):
        """Test X-Forwarded-For is used when CF-Connecting-IP absent.

        Arrange: Request with X-Forwarded-For header
        Act: Call _extract_client_ip
        Assert: Returns first IP from X-Forwarded-For
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2, 10.0.0.3"})

        result = middleware._extract_client_ip(request)

        assert result == "10.0.0.1"

    def test_returns_x_real_ip_when_no_forwarded_for(self):
        """Test X-Real-IP is used when X-Forwarded-For is absent.

        Arrange: Request with X-Real-IP header
        Act: Call _extract_client_ip
        Assert: Returns X-Real-IP value
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={"X-Real-IP": "192.168.1.100"})

        result = middleware._extract_client_ip(request)

        assert result == "192.168.1.100"

    def test_returns_direct_client_host(self):
        """Test direct connection host is used as fallback.

        Arrange: Request with no proxy headers but with client.host
        Act: Call _extract_client_ip
        Assert: Returns client.host
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={})
        request.client = MagicMock()
        request.client.host = "192.168.0.50"

        result = middleware._extract_client_ip(request)

        assert result == "192.168.0.50"

    def test_returns_unknown_when_no_client(self):
        """Test returns 'unknown' when client is None.

        Arrange: Request with no proxy headers and no client
        Act: Call _extract_client_ip
        Assert: Returns 'unknown'
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={})
        request.client = None

        result = middleware._extract_client_ip(request)

        assert result == "unknown"

    def test_returns_unknown_when_client_host_is_none(self):
        """Test returns 'unknown' when client.host is None.

        Arrange: Request with no proxy headers and client.host=None
        Act: Call _extract_client_ip
        Assert: Returns 'unknown'
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={})
        request.client = MagicMock()
        request.client.host = None

        result = middleware._extract_client_ip(request)

        assert result == "unknown"

    def test_x_forwarded_for_strips_whitespace(self):
        """Test that whitespace is stripped from X-Forwarded-For IPs.

        Arrange: X-Forwarded-For with spaces around IPs
        Act: Call _extract_client_ip
        Assert: Returns stripped IP
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers={"X-Forwarded-For": "  10.0.0.1  , 10.0.0.2"})

        result = middleware._extract_client_ip(request)

        assert result == "10.0.0.1"

    @pytest.mark.parametrize(
        ("headers", "expected_ip"),
        [
            ({"CF-Connecting-IP": "5.5.5.5"}, "5.5.5.5"),
            ({"X-Forwarded-For": "6.6.6.6, 7.7.7.7"}, "6.6.6.6"),
            ({"X-Real-IP": "8.8.8.8"}, "8.8.8.8"),
        ],
        ids=["cf_connecting_ip", "x_forwarded_for", "x_real_ip"],
    )
    def test_ip_extraction_priority(self, headers, expected_ip):
        """Parametrized test for IP extraction priority order.

        Arrange: Various header combinations
        Act: Call _extract_client_ip
        Assert: Correct IP returned based on priority
        """
        middleware = RequestContextMiddleware(app=MagicMock())
        request = _make_mock_request(headers=headers)

        result = middleware._extract_client_ip(request)

        assert result == expected_ip
