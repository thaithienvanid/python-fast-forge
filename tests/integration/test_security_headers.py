"""Integration tests for security headers middleware."""

import re

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from src.presentation.api.middleware.security_headers import SecurityHeadersMiddleware


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application with security headers middleware.

    Returns:
        FastAPI: App instance with security headers middleware
    """
    test_app = FastAPI()
    test_app.add_middleware(SecurityHeadersMiddleware)

    @test_app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client for the application.

    Args:
        app: FastAPI application

    Returns:
        TestClient: Test client for making requests
    """
    return TestClient(app)


# ============================================================================
# Test Classes
# ============================================================================


class TestXFrameOptionsHeader:
    """Test X-Frame-Options header for clickjacking protection.

    X-Frame-Options prevents the page from being loaded in iframes,
    protecting against clickjacking attacks.
    """

    def test_header_is_present(self, client: TestClient) -> None:
        """Test X-Frame-Options header is present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: X-Frame-Options header exists
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert "X-Frame-Options" in response.headers

    def test_header_value_is_deny(self, client: TestClient) -> None:
        """Test X-Frame-Options is set to DENY.

        DENY is the most secure option, preventing all framing.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: X-Frame-Options is "DENY"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert response.headers["X-Frame-Options"] == "DENY"


class TestXContentTypeOptionsHeader:
    """Test X-Content-Type-Options header for MIME-sniffing protection.

    X-Content-Type-Options: nosniff prevents browsers from MIME-sniffing
    responses, forcing them to respect the Content-Type header.
    """

    def test_header_is_present(self, client: TestClient) -> None:
        """Test X-Content-Type-Options header is present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: X-Content-Type-Options header exists
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert "X-Content-Type-Options" in response.headers

    def test_header_value_is_nosniff(self, client: TestClient) -> None:
        """Test X-Content-Type-Options is set to nosniff.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: X-Content-Type-Options is "nosniff"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestXSSProtectionHeader:
    """Test X-XSS-Protection header for XSS attack protection.

    X-XSS-Protection enables browser's XSS filter in block mode.
    Note: Modern browsers prefer Content-Security-Policy over this header.
    """

    def test_header_is_present(self, client: TestClient) -> None:
        """Test X-XSS-Protection header is present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: X-XSS-Protection header exists
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert "X-XSS-Protection" in response.headers

    def test_header_enables_blocking_mode(self, client: TestClient) -> None:
        """Test X-XSS-Protection enables blocking mode.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: X-XSS-Protection is "1; mode=block"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert response.headers["X-XSS-Protection"] == "1; mode=block"


class TestReferrerPolicyHeader:
    """Test Referrer-Policy header for information leakage protection.

    Referrer-Policy controls how much referrer information is sent
    with requests, preventing information leakage.
    """

    def test_header_is_present(self, client: TestClient) -> None:
        """Test Referrer-Policy header is present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Referrer-Policy header exists
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert "Referrer-Policy" in response.headers

    def test_header_value_balances_privacy_and_functionality(self, client: TestClient) -> None:
        """Test Referrer-Policy uses a secure value.

        strict-origin-when-cross-origin is a good balance between
        privacy and functionality.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Referrer-Policy is a secure value
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        policy = response.headers["Referrer-Policy"]

        # Assert: Should use a secure policy
        assert policy in [
            "strict-origin-when-cross-origin",
            "no-referrer",
            "same-origin",
        ]


class TestContentSecurityPolicyHeader:
    """Test Content-Security-Policy header for XSS protection.

    CSP is a powerful security mechanism that helps prevent XSS,
    clickjacking, and other code injection attacks.
    """

    def test_header_is_present(self, client: TestClient) -> None:
        """Test Content-Security-Policy header is present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Content-Security-Policy header exists
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert "Content-Security-Policy" in response.headers

    def test_default_src_is_self(self, client: TestClient) -> None:
        """Test CSP default-src directive is 'self'.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "default-src 'self'"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "default-src 'self'" in csp

    def test_includes_script_src_directive(self, client: TestClient) -> None:
        """Test CSP includes script-src directive.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "script-src"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "script-src" in csp

    def test_includes_style_src_directive(self, client: TestClient) -> None:
        """Test CSP includes style-src directive.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "style-src"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "style-src" in csp

    def test_includes_img_src_directive(self, client: TestClient) -> None:
        """Test CSP includes img-src directive.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "img-src"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "img-src" in csp

    def test_includes_font_src_directive(self, client: TestClient) -> None:
        """Test CSP includes font-src directive.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "font-src"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "font-src" in csp

    def test_includes_connect_src_directive(self, client: TestClient) -> None:
        """Test CSP includes connect-src directive.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "connect-src"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "connect-src" in csp

    def test_frame_ancestors_prevents_framing(self, client: TestClient) -> None:
        """Test CSP frame-ancestors is 'none' to prevent framing.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "frame-ancestors 'none'"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "frame-ancestors 'none'" in csp

    def test_base_uri_is_restricted(self, client: TestClient) -> None:
        """Test CSP base-uri is restricted to 'self'.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: CSP contains "base-uri 'self'"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        csp = response.headers["Content-Security-Policy"]

        # Assert
        assert "base-uri 'self'" in csp


class TestPermissionsPolicyHeader:
    """Test Permissions-Policy header for browser feature control.

    Permissions-Policy (formerly Feature-Policy) controls which
    browser features and APIs can be used by the page.
    """

    def test_header_is_present(self, client: TestClient) -> None:
        """Test Permissions-Policy header is present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Permissions-Policy header exists
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert "Permissions-Policy" in response.headers

    def test_geolocation_is_disabled(self, client: TestClient) -> None:
        """Test Permissions-Policy disables geolocation.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Permissions-Policy contains "geolocation=()"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        permissions = response.headers["Permissions-Policy"]

        # Assert
        assert "geolocation=()" in permissions

    def test_microphone_is_disabled(self, client: TestClient) -> None:
        """Test Permissions-Policy disables microphone access.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Permissions-Policy contains "microphone=()"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        permissions = response.headers["Permissions-Policy"]

        # Assert
        assert "microphone=()" in permissions

    def test_camera_is_disabled(self, client: TestClient) -> None:
        """Test Permissions-Policy disables camera access.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Permissions-Policy contains "camera=()"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        permissions = response.headers["Permissions-Policy"]

        # Assert
        assert "camera=()" in permissions

    def test_payment_is_disabled(self, client: TestClient) -> None:
        """Test Permissions-Policy disables payment API.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Permissions-Policy contains "payment=()"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        permissions = response.headers["Permissions-Policy"]

        # Assert
        assert "payment=()" in permissions

    def test_usb_is_disabled(self, client: TestClient) -> None:
        """Test Permissions-Policy disables USB API.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Permissions-Policy contains "usb=()"
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")
        permissions = response.headers["Permissions-Policy"]

        # Assert
        assert "usb=()" in permissions


class TestStrictTransportSecurityHeader:
    """Test Strict-Transport-Security header for HTTPS enforcement.

    HSTS tells browsers to only connect via HTTPS, protecting
    against man-in-the-middle attacks.
    """

    def test_header_present_in_production(self, app: FastAPI, monkeypatch) -> None:
        """Test HSTS header is present in production environment.

        Arrange: Mock production environment
        Act: GET /test
        Assert: Strict-Transport-Security header exists
        """
        # Arrange: Mock production environment
        from src.infrastructure.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "app_env", "production")
        client = TestClient(app)

        # Act
        response = client.get("/test")

        # Assert
        assert "Strict-Transport-Security" in response.headers

    def test_header_absent_in_development(self, app: FastAPI, monkeypatch) -> None:
        """Test HSTS header is NOT present in development.

        HSTS should not be set in development to avoid issues
        with local HTTP connections.

        Arrange: Mock development environment
        Act: GET /test
        Assert: Strict-Transport-Security header does not exist
        """
        # Arrange: Mock development environment
        from src.infrastructure.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "app_env", "development")
        client = TestClient(app)

        # Act
        response = client.get("/test")

        # Assert
        assert "Strict-Transport-Security" not in response.headers

    def test_max_age_at_least_one_year_in_production(self, app: FastAPI, monkeypatch) -> None:
        """Test HSTS max-age is at least 1 year in production.

        Arrange: Mock production environment
        Act: GET /test, extract max-age
        Assert: max-age >= 31536000 (1 year in seconds)
        """
        # Arrange: Mock production environment
        from src.infrastructure.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "app_env", "production")
        client = TestClient(app)

        # Act
        response = client.get("/test")

        if "Strict-Transport-Security" in response.headers:
            hsts = response.headers["Strict-Transport-Security"]
            max_age_match = re.search(r"max-age=(\d+)", hsts)

            # Assert
            assert max_age_match is not None
            max_age = int(max_age_match.group(1))
            assert max_age >= 31536000, "HSTS max-age should be at least 1 year"

    def test_includes_subdomains_in_production(self, app: FastAPI, monkeypatch) -> None:
        """Test HSTS includes includeSubDomains directive.

        Arrange: Mock production environment
        Act: GET /test
        Assert: HSTS contains "includeSubDomains"
        """
        # Arrange: Mock production environment
        from src.infrastructure.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "app_env", "production")
        client = TestClient(app)

        # Act
        response = client.get("/test")

        if "Strict-Transport-Security" in response.headers:
            hsts = response.headers["Strict-Transport-Security"]

            # Assert
            assert "includeSubDomains" in hsts

    def test_includes_preload_directive_in_production(self, app: FastAPI, monkeypatch) -> None:
        """Test HSTS includes preload directive.

        Arrange: Mock production environment
        Act: GET /test
        Assert: HSTS contains "preload"
        """
        # Arrange: Mock production environment
        from src.infrastructure.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "app_env", "production")
        client = TestClient(app)

        # Act
        response = client.get("/test")

        if "Strict-Transport-Security" in response.headers:
            hsts = response.headers["Strict-Transport-Security"]

            # Assert
            assert "preload" in hsts


class TestSecurityHeadersCompleteness:
    """Test that all expected security headers are present.

    Verifies the middleware adds all required security headers
    in a single response.
    """

    def test_all_core_security_headers_present(self, client: TestClient) -> None:
        """Test all core security headers are present.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: All expected headers exist
        """
        # Arrange
        expected_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Permissions-Policy",
            "Referrer-Policy",
        ]

        # Act
        response = client.get("/test")

        # Assert
        for header in expected_headers:
            assert header in response.headers, f"Missing security header: {header}"


class TestSecurityHeadersAcrossStatusCodes:
    """Test security headers are added to different HTTP status codes.

    Security headers should be present regardless of status code.
    """

    def test_headers_present_on_201_created(self, app: FastAPI) -> None:
        """Test security headers on 201 Created response.

        Arrange: Add endpoint that returns 201
        Act: GET /created
        Assert: Security headers are present
        """

        # Arrange
        @app.get("/created")
        async def created_endpoint():
            return Response(
                content='{"status": "created"}',
                status_code=201,
                media_type="application/json",
            )

        client = TestClient(app)

        # Act
        response = client.get("/created")

        # Assert
        assert response.status_code == 201
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_headers_present_on_404_not_found(self, client: TestClient) -> None:
        """Test security headers on 404 Not Found response.

        Arrange: Client with security headers middleware
        Act: GET /nonexistent-endpoint
        Assert: Security headers are present on 404
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/nonexistent-endpoint")

        # Assert
        assert response.status_code == 404
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "Content-Security-Policy" in response.headers


class TestSecurityHeadersAcrossHTTPMethods:
    """Test security headers work with all HTTP methods.

    Security headers should be added for GET, POST, PUT, DELETE, etc.
    """

    def test_headers_present_on_post_requests(self, app: FastAPI) -> None:
        """Test security headers on POST requests.

        Arrange: Add POST endpoint
        Act: POST /post-test
        Assert: Security headers are present
        """

        # Arrange
        @app.post("/post-test")
        async def post_endpoint():
            return {"method": "POST"}

        client = TestClient(app)

        # Act
        response = client.post("/post-test")

        # Assert
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_headers_present_on_put_requests(self, app: FastAPI) -> None:
        """Test security headers on PUT requests.

        Arrange: Add PUT endpoint
        Act: PUT /put-test
        Assert: Security headers are present
        """

        # Arrange
        @app.put("/put-test")
        async def put_endpoint():
            return {"method": "PUT"}

        client = TestClient(app)

        # Act
        response = client.put("/put-test")

        # Assert
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_headers_present_on_delete_requests(self, app: FastAPI) -> None:
        """Test security headers on DELETE requests.

        Arrange: Add DELETE endpoint
        Act: DELETE /delete-test
        Assert: Security headers are present
        """

        # Arrange
        @app.delete("/delete-test")
        async def delete_endpoint():
            return {"method": "DELETE"}

        client = TestClient(app)

        # Act
        response = client.delete("/delete-test")

        # Assert
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers


class TestSecurityHeadersMiddlewareIntegrity:
    """Test that middleware doesn't interfere with responses.

    Verifies the middleware only adds headers without modifying
    response body or other aspects.
    """

    def test_middleware_preserves_response_body(self, client: TestClient) -> None:
        """Test middleware doesn't modify response body.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Response body is unchanged
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"message": "test"}

    def test_middleware_preserves_status_code(self, client: TestClient) -> None:
        """Test middleware doesn't modify status code.

        Arrange: Client with security headers middleware
        Act: GET /test
        Assert: Status code is 200
        """
        # Arrange: (client fixture provides configured client)

        # Act
        response = client.get("/test")

        # Assert
        assert response.status_code == 200
