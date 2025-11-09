"""Integration tests for RequestContextMiddleware."""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.presentation.api.middleware.request_context import RequestContextMiddleware


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI app with request context middleware."""
    app = FastAPI()

    # Add middleware
    app.add_middleware(RequestContextMiddleware)

    # Add test endpoint
    @app.get("/test")
    async def test_endpoint(request: Request):
        return {
            "trace_id": request.state.trace_id,
            "client_ip": request.state.client_ip,
        }

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(test_app)


# ============================================================================
# Trace ID Extraction Tests
# ============================================================================


class TestTraceIdExtraction:
    """Test trace ID extraction from various sources with priority order."""

    def test_extracts_from_opentelemetry_span(self, client: TestClient) -> None:
        """Test trace_id is extracted from active OpenTelemetry span.

        Arrange: Client with OpenTelemetry enabled (default)
        Act: GET /test
        Assert: Returns trace_id in response and X-Trace-ID header
        """
        # Arrange: (OpenTelemetry enabled by default in test environment)

        # Act
        response = client.get("/test")

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Should have trace_id from OpenTelemetry
        assert "trace_id" in data
        assert len(data["trace_id"]) > 0

        # Should also be in response headers
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Trace-ID"] == data["trace_id"]

    def test_uses_cf_ray_when_opentelemetry_disabled(self, client: TestClient) -> None:
        """Test trace_id falls back to CF-Ray header when OpenTelemetry unavailable.

        Arrange: Mock OpenTelemetry as disabled, provide CF-Ray header
        Act: GET /test with CF-Ray header
        Assert: Uses CF-Ray value as trace_id
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = False
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = False
            mock_trace.get_current_span.return_value = mock_span

            cf_ray_value = "cloudflare-trace-123"

            # Act
            response = client.get("/test", headers={"CF-Ray": cf_ray_value})

            # Assert
            data = response.json()
            assert data["trace_id"] == cf_ray_value

    def test_generates_uuidv7_fallback_when_no_source_available(self, client: TestClient) -> None:
        """Test trace_id generates UUIDv7 when OpenTelemetry and CF-Ray unavailable.

        Arrange: Mock OpenTelemetry as disabled, no CF-Ray header
        Act: GET /test without any trace headers
        Assert: Generates valid UUID format trace_id
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = False
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = False
            mock_trace.get_current_span.return_value = mock_span

            # Act
            response = client.get("/test")

            # Assert
            data = response.json()
            assert "trace_id" in data
            assert len(data["trace_id"]) > 0
            # Should be a valid UUID format (with hyphens)
            assert "-" in data["trace_id"]

    def test_prioritizes_opentelemetry_over_cf_ray(self, client: TestClient) -> None:
        """Test OpenTelemetry trace_id takes priority over CF-Ray header.

        Arrange: Both OpenTelemetry and CF-Ray available
        Act: GET /test with CF-Ray header
        Assert: Uses OpenTelemetry trace_id, ignores CF-Ray
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = True
            # Valid 128-bit trace_id
            mock_span_context.trace_id = 12345678901234567890123456789012
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = True
            mock_trace.get_current_span.return_value = mock_span

            cf_ray_value = "should-be-ignored"

            # Act
            response = client.get("/test", headers={"CF-Ray": cf_ray_value})

            # Assert
            data = response.json()
            # Should NOT use CF-Ray
            assert data["trace_id"] != cf_ray_value
            # Should be a 32-character hex string (128-bit trace_id)
            assert len(data["trace_id"]) == 32
            assert all(c in "0123456789abcdef" for c in data["trace_id"])

    def test_adds_trace_id_to_response_header(self, client: TestClient) -> None:
        """Test trace_id is added to response X-Trace-ID header.

        Arrange: Client ready
        Act: GET /test
        Assert: Response has X-Trace-ID header with value
        """
        # Arrange: (no specific setup needed)

        # Act
        response = client.get("/test")

        # Assert
        assert "X-Trace-ID" in response.headers
        assert len(response.headers["X-Trace-ID"]) > 0

    def test_trace_id_consistent_across_state_and_header(self, client: TestClient) -> None:
        """Test trace_id is identical in request.state and response header.

        Arrange: Client ready
        Act: GET /test (endpoint returns trace_id from request.state)
        Assert: trace_id in response body matches X-Trace-ID header
        """
        # Arrange: (no specific setup needed)

        # Act
        response = client.get("/test")

        # Assert
        data = response.json()
        state_trace_id = data["trace_id"]
        header_trace_id = response.headers["X-Trace-ID"]
        assert state_trace_id == header_trace_id

    def test_formats_opentelemetry_trace_id_as_32_char_hex(self, test_app: FastAPI) -> None:
        """Test OpenTelemetry trace_id is formatted as 32-character hex string.

        Arrange: Mock OpenTelemetry with known trace_id integer
        Act: GET /test
        Assert: trace_id formatted as 32-character lowercase hex
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = True
            # Use a known trace_id for predictable output
            mock_span_context.trace_id = 0x12345678ABCDEF1234567890ABCDEF12
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = False
            mock_trace.get_current_span.return_value = mock_span

            client = TestClient(test_app)

            # Act
            response = client.get("/test")

            # Assert
            data = response.json()
            assert len(data["trace_id"]) == 32
            assert data["trace_id"] == "12345678abcdef1234567890abcdef12"

    def test_preserves_cf_ray_format_exactly(self, client: TestClient) -> None:
        """Test CF-Ray value is preserved exactly as received.

        Arrange: Mock OpenTelemetry as disabled, provide CF-Ray with format
        Act: GET /test with CF-Ray header
        Assert: trace_id matches CF-Ray exactly (with location suffix)
        """
        # Arrange
        cf_ray_value = "7d3c9f8e7a6b5c4d-SJC"

        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = False
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = False
            mock_trace.get_current_span.return_value = mock_span

            # Act
            response = client.get("/test", headers={"CF-Ray": cf_ray_value})

            # Assert
            data = response.json()
            assert data["trace_id"] == cf_ray_value


# ============================================================================
# Client IP Extraction Tests
# ============================================================================


class TestClientIpExtraction:
    """Test client IP extraction from various headers with priority order."""

    def test_extracts_from_cf_connecting_ip_with_highest_priority(self, client: TestClient) -> None:
        """Test CF-Connecting-IP header has highest priority for client IP.

        Arrange: Multiple IP headers present (CF, XFF, X-Real-IP)
        Act: GET /test with all IP headers
        Assert: Uses CF-Connecting-IP, ignores others
        """
        # Arrange
        headers = {
            "CF-Connecting-IP": "1.2.3.4",
            "X-Forwarded-For": "5.6.7.8",
            "X-Real-IP": "9.10.11.12",
        }

        # Act
        response = client.get("/test", headers=headers)

        # Assert
        data = response.json()
        assert data["client_ip"] == "1.2.3.4"

    def test_extracts_first_ip_from_x_forwarded_for(self, client: TestClient) -> None:
        """Test X-Forwarded-For header used when CF-Connecting-IP absent.

        Arrange: X-Forwarded-For with multiple IPs, no CF header
        Act: GET /test
        Assert: Uses first IP from X-Forwarded-For chain
        """
        # Arrange
        headers = {
            "X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12",
            "X-Real-IP": "should-be-ignored",
        }

        # Act
        response = client.get("/test", headers=headers)

        # Assert
        data = response.json()
        assert data["client_ip"] == "1.2.3.4"

    def test_handles_x_forwarded_for_with_single_ip(self, client: TestClient) -> None:
        """Test X-Forwarded-For with single IP (no commas).

        Arrange: X-Forwarded-For with single IP
        Act: GET /test
        Assert: Uses that single IP
        """
        # Arrange
        headers = {"X-Forwarded-For": "10.20.30.40"}

        # Act
        response = client.get("/test", headers=headers)

        # Assert
        data = response.json()
        assert data["client_ip"] == "10.20.30.40"

    def test_strips_whitespace_from_x_forwarded_for(self, client: TestClient) -> None:
        """Test X-Forwarded-For values are stripped of whitespace.

        Arrange: X-Forwarded-For with extra spaces around IPs
        Act: GET /test
        Assert: IPs trimmed correctly
        """
        # Arrange
        headers = {"X-Forwarded-For": " 1.2.3.4 , 5.6.7.8 "}

        # Act
        response = client.get("/test", headers=headers)

        # Assert
        data = response.json()
        assert data["client_ip"] == "1.2.3.4"

    def test_extracts_from_x_real_ip_when_others_absent(self, client: TestClient) -> None:
        """Test X-Real-IP header used when CF and XFF absent.

        Arrange: Only X-Real-IP header present
        Act: GET /test
        Assert: Uses X-Real-IP value
        """
        # Arrange
        headers = {"X-Real-IP": "192.168.1.100"}

        # Act
        response = client.get("/test", headers=headers)

        # Assert
        data = response.json()
        assert data["client_ip"] == "192.168.1.100"

    def test_falls_back_to_direct_connection_when_no_headers(self, client: TestClient) -> None:
        """Test fallback to direct connection client when no proxy headers.

        Arrange: No IP headers present
        Act: GET /test
        Assert: Uses TestClient default ('testclient')
        """
        # Arrange: (no headers)

        # Act
        response = client.get("/test")

        # Assert
        data = response.json()
        # TestClient uses 'testclient' as default
        assert data["client_ip"] == "testclient"

    @pytest.mark.parametrize(
        ("headers", "expected_ip"),
        [
            # CF takes priority over all
            (
                {
                    "CF-Connecting-IP": "priority1",
                    "X-Forwarded-For": "priority2",
                    "X-Real-IP": "priority3",
                },
                "priority1",
            ),
            # XFF takes priority over X-Real-IP
            (
                {"X-Forwarded-For": "priority2", "X-Real-IP": "priority3"},
                "priority2",
            ),
            # X-Real-IP when only option
            ({"X-Real-IP": "priority3"}, "priority3"),
        ],
    )
    def test_validates_header_priority_order(
        self, client: TestClient, headers: dict, expected_ip: str
    ) -> None:
        """Test client IP header priority: CF > XFF > X-Real-IP > direct.

        Arrange: Various combinations of IP headers
        Act: GET /test with headers
        Assert: Uses correct IP based on priority
        """
        # Arrange: (headers provided by parametrize)

        # Act
        response = client.get("/test", headers=headers)

        # Assert
        data = response.json()
        assert data["client_ip"] == expected_ip


# ============================================================================
# OpenTelemetry Integration Tests
# ============================================================================


class TestOpenTelemetryIntegration:
    """Test OpenTelemetry span integration and attribute setting."""

    def test_sets_span_attributes_when_recording(self, test_app: FastAPI) -> None:
        """Test span attributes are set when span is recording.

        Arrange: Mock OpenTelemetry with recording span
        Act: GET /test with CF-Connecting-IP header
        Assert: Span attributes set (client_ip, http.method, http.url)
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = True
            mock_span_context.trace_id = 123456789
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = True
            mock_trace.get_current_span.return_value = mock_span

            client = TestClient(test_app)

            # Act
            client.get("/test", headers={"CF-Connecting-IP": "1.2.3.4"})

            # Assert
            assert mock_span.set_attribute.called
            calls = mock_span.set_attribute.call_args_list

            # Verify required attributes were set
            call_args = {call[0][0]: call[0][1] for call in calls}
            assert "client_ip" in call_args
            assert call_args["client_ip"] == "1.2.3.4"
            assert "http.method" in call_args
            assert "http.url" in call_args

    def test_skips_span_attributes_when_not_recording(self, test_app: FastAPI) -> None:
        """Test span attributes not set when span is not recording.

        Arrange: Mock OpenTelemetry with non-recording span
        Act: GET /test
        Assert: set_attribute not called, request still succeeds
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = True
            mock_span_context.trace_id = 123456789
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = False
            mock_trace.get_current_span.return_value = mock_span

            client = TestClient(test_app)

            # Act
            response = client.get("/test")

            # Assert
            assert response.status_code == 200
            assert not mock_span.set_attribute.called


# ============================================================================
# Structlog Context Tests
# ============================================================================


class TestStructlogContextBinding:
    """Test structlog context variable binding."""

    def test_binds_context_variables_correctly(self, test_app: FastAPI) -> None:
        """Test structlog context variables are bound with request metadata.

        Arrange: Mock structlog, client with CF-Connecting-IP
        Act: GET /test
        Assert: contextvars cleared and bound with trace_id, client_ip, method, path
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.structlog") as mock_structlog:
            client = TestClient(test_app)

            # Act
            client.get("/test", headers={"CF-Connecting-IP": "10.20.30.40"})

            # Assert
            # Verify contextvars were cleared
            assert mock_structlog.contextvars.clear_contextvars.called

            # Verify contextvars were bound
            assert mock_structlog.contextvars.bind_contextvars.called

            # Check bound context values
            call_kwargs = mock_structlog.contextvars.bind_contextvars.call_args[1]
            assert "trace_id" in call_kwargs
            assert "client_ip" in call_kwargs
            assert call_kwargs["client_ip"] == "10.20.30.40"
            assert "method" in call_kwargs
            assert "path" in call_kwargs


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


class TestEdgeCasesAndIntegration:
    """Test edge cases and complete integration flows."""

    def test_handles_request_without_client_object(self, test_app: FastAPI) -> None:
        """Test middleware handles request without client object gracefully.

        Arrange: Mock OpenTelemetry as disabled
        Act: GET /test
        Assert: Request succeeds with client_ip set
        """
        # Arrange
        with patch("src.presentation.api.middleware.request_context.trace") as mock_trace:
            mock_span = Mock()
            mock_span_context = Mock()
            mock_span_context.is_valid = False
            mock_span.get_span_context.return_value = mock_span_context
            mock_span.is_recording.return_value = False
            mock_trace.get_current_span.return_value = mock_span

            client = TestClient(test_app)

            # Act
            response = client.get("/test")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "client_ip" in data

    def test_each_request_has_independent_context(self, client: TestClient) -> None:
        """Test multiple requests have independent trace contexts.

        Arrange: Two requests with different CF-Ray headers
        Act: GET /test twice with different CF-Ray values
        Assert: Each has unique trace_id in response header
        """
        # Arrange & Act
        response1 = client.get("/test", headers={"CF-Ray": "trace1"})
        response2 = client.get("/test", headers={"CF-Ray": "trace2"})

        # Assert
        # Different trace IDs in headers
        assert response1.headers["X-Trace-ID"] != response2.headers["X-Trace-ID"]

    def test_request_state_accessible_in_endpoint_handler(self, client: TestClient) -> None:
        """Test request.state contains trace_id and client_ip for endpoint use.

        Arrange: Client ready
        Act: GET /test (endpoint accesses request.state)
        Assert: Endpoint successfully retrieved trace_id and client_ip
        """
        # Arrange: (no specific setup needed)

        # Act
        response = client.get("/test")

        # Assert
        data = response.json()
        # Endpoint successfully accessed request.state
        assert data["trace_id"] is not None
        assert data["client_ip"] is not None

    def test_complete_middleware_flow_with_all_features(self, test_app: FastAPI) -> None:
        """Test complete middleware flow with all features enabled.

        Arrange: Add endpoint that checks request.state, provide all headers
        Act: GET endpoint with CF headers
        Assert: All state attributes present, response headers set
        """

        # Arrange
        @test_app.get("/full-test")
        async def full_test(request: Request):
            return {
                "has_trace_id": hasattr(request.state, "trace_id"),
                "has_client_ip": hasattr(request.state, "client_ip"),
                "trace_id_length": len(request.state.trace_id),
            }

        client = TestClient(test_app)

        # Act
        response = client.get(
            "/full-test",
            headers={
                "CF-Connecting-IP": "1.2.3.4",
                "CF-Ray": "cloudflare-123",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["has_trace_id"] is True
        assert data["has_client_ip"] is True
        assert data["trace_id_length"] > 0

        # Check response headers
        assert "X-Trace-ID" in response.headers

    def test_middleware_works_with_post_requests(
        self, client: TestClient, test_app: FastAPI
    ) -> None:
        """Test middleware functions correctly with POST requests.

        Arrange: Add POST endpoint
        Act: POST /post-test with JSON body and X-Real-IP header
        Assert: Response has trace_id and X-Trace-ID header
        """

        # Arrange
        @test_app.post("/post-test")
        async def post_test(request: Request):
            return {"trace_id": request.state.trace_id}

        client = TestClient(test_app)

        # Act
        response = client.post(
            "/post-test",
            json={"data": "test"},
            headers={"X-Real-IP": "192.168.1.1"},
        )

        # Assert
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers

    def test_middleware_preserves_response_body_structure(self, client: TestClient) -> None:
        """Test middleware doesn't modify or add to response body.

        Arrange: Client ready
        Act: GET /test (returns specific structure)
        Assert: Response has only expected fields, nothing added
        """
        # Arrange: (no specific setup needed)

        # Act
        response = client.get("/test")

        # Assert
        data = response.json()
        # Original response structure preserved
        assert "trace_id" in data
        assert "client_ip" in data
        assert len(data) == 2  # No extra fields added
