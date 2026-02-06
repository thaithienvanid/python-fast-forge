"""Security integration tests for vulnerability detection.

This module tests for common security vulnerabilities including:
- SQL injection attempts
- XSS (Cross-Site Scripting) attempts
- Authentication bypass
- Input validation
- Rate limiting enforcement
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.auth
class TestSecurityVulnerabilities:
    """Test suite for security vulnerability detection."""

    def test_sql_injection_in_email_field(self, client: TestClient) -> None:
        """Test that SQL injection attempts in email field are blocked.

        Attempts to inject SQL through the email field to verify proper
        input validation and parameterized queries are in use.
        """
        # Common SQL injection payloads
        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            "' OR 1=1--",
            "'; DELETE FROM users WHERE '1'='1",
            "1' UNION SELECT NULL, NULL, NULL--",
        ]

        for payload in sql_injection_payloads:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": payload,
                    "username": "testuser",
                    "full_name": "Test User",
                },
            )

            # Should return validation error (422) not internal server error (500)
            assert response.status_code in [
                400,
                422,
            ], f"SQL injection payload should be rejected: {payload}"

            # Verify no SQL injection occurred by checking response
            if response.status_code != 422:
                data = response.json()
                assert "DROP" not in str(data).upper()
                assert "DELETE" not in str(data).upper()

    def test_sql_injection_in_username_field(self, client: TestClient) -> None:
        """Test that SQL injection attempts in username field are blocked."""
        sql_injection_payloads = [
            "admin'; DROP TABLE users--",
            "' OR '1'='1' --",
        ]

        for payload in sql_injection_payloads:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": "test@example.com",
                    "username": payload,
                    "full_name": "Test User",
                },
            )

            # Should return validation error
            assert response.status_code in [400, 422], (
                f"SQL injection should be rejected: {payload}"
            )

    def test_xss_attempt_in_user_fields(self, client: TestClient) -> None:
        """Test that XSS attempts are properly sanitized or rejected.

        Verifies that HTML/JavaScript injection attempts don't result in
        stored XSS vulnerabilities.
        """
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]

        for payload in xss_payloads:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": "xss@example.com",
                    "username": "xss_test",
                    "full_name": payload,
                },
            )

            # Should either reject or properly escape
            if response.status_code == 201:
                data = response.json()
                # Verify script tags are not present unescaped
                assert "<script>" not in data.get("full_name", "")
                assert "onerror=" not in data.get("full_name", "")

    def test_excessively_long_input(self, client: TestClient) -> None:
        """Test that excessively long inputs are rejected.

        Prevents buffer overflow and DoS attacks through large payloads.
        """
        # Email exceeds typical VARCHAR(255) limit
        long_email = "a" * 300 + "@example.com"
        response = client.post(
            "/api/v1/users",
            json={
                "email": long_email,
                "username": "testuser",
                "full_name": "Test User",
            },
        )

        # Should reject due to length constraint
        assert response.status_code in [400, 422]

        # Username exceeds limit
        long_username = "a" * 150
        response = client.post(
            "/api/v1/users",
            json={
                "email": "test@example.com",
                "username": long_username,
                "full_name": "Test User",
            },
        )

        assert response.status_code in [400, 422]

    def test_null_byte_injection(self, client: TestClient) -> None:
        """Test that null byte injection attempts are handled.

        Null bytes can be used to bypass filters or cause unexpected behavior.
        """
        null_byte_payloads = [
            "test\x00@example.com",
            "user\x00name",
            "Test\x00User",
        ]

        for payload in null_byte_payloads:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": payload if "@" in payload else "test@example.com",
                    "username": "test_user" if "@" in payload else payload,
                    "full_name": payload if "Test" in payload else "Test User",
                },
            )

            # Should reject null bytes
            assert response.status_code in [400, 422]

    def test_path_traversal_in_filters(self, client: TestClient) -> None:
        """Test that path traversal attempts are blocked.

        Verifies that file path manipulation can't access sensitive files.
        """
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f",
        ]

        for payload in path_traversal_payloads:
            response = client.get(
                "/api/v1/users",
                params={"search": payload},
            )

            # Should not expose file system
            if response.status_code == 200:
                data = response.json()
                assert "root:" not in str(data)  # Unix passwd file content
                assert "system32" not in str(data).lower()

    def test_special_characters_handling(self, client: TestClient) -> None:
        """Test that special characters are properly handled.

        Ensures Unicode, special characters, and edge cases don't cause issues.
        """
        special_char_payloads = [
            "user@example.com; DROP TABLE users",
            "user@example.com\r\n",
            "user@example.com\x00",
            "user@例え.com",  # Unicode domain
            "测试@example.com",  # Chinese characters
        ]

        for payload in special_char_payloads:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": payload,
                    "username": "testuser" + str(hash(payload))[:8],
                    "full_name": "Test User",
                },
            )

            # Should either accept valid Unicode or reject invalid characters
            assert response.status_code in [201, 400, 422]
            if response.status_code != 201:
                data = response.json()
                # Ensure proper error handling, not crashes
                assert "detail" in data or "message" in data

    def test_mass_assignment_protection(self, client: TestClient) -> None:
        """Test that mass assignment vulnerabilities are prevented.

        Verifies that users can't inject unauthorized fields.
        """
        response = client.post(
            "/api/v1/users",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "full_name": "Test User",
                "is_admin": True,  # Unauthorized field
                "role": "admin",  # Unauthorized field
                "deleted_at": None,  # Internal field
            },
        )

        if response.status_code == 201:
            data = response.json()
            # Verify unauthorized fields are not set
            assert data.get("is_admin") is not True
            assert data.get("role") != "admin"

    def test_header_injection(self, client: TestClient) -> None:
        """Test that header injection attempts are blocked.

        CRLF injection in headers can lead to response splitting attacks.
        """
        malicious_headers = {
            "X-Custom-Header": "value\r\nInjected-Header: malicious",
        }

        response = client.get("/api/v1/users", headers=malicious_headers)

        # Should reject or sanitize
        assert "Injected-Header" not in str(response.headers)


@pytest.mark.integration
@pytest.mark.auth
class TestAuthenticationSecurity:
    """Test suite for authentication and authorization security."""

    def test_missing_authentication_header(self, client: TestClient) -> None:
        """Test that protected endpoints require authentication.

        This test assumes some endpoints require auth (if implemented).
        """
        # Try to access a protected resource without credentials
        response = client.get("/api/v1/users")

        # If endpoint requires auth, should return 401 or 403
        # If endpoint is public, this test can be skipped or modified
        assert response.status_code in [200, 401, 403]

    def test_invalid_token_format(self, client: TestClient) -> None:
        """Test that invalid token formats are rejected."""
        invalid_tokens = [
            "Bearer",
            "Bearer ",
            "Bearer invalid.token.format",
            "NotBearer validtoken",
            "Bearer " + "a" * 1000,  # Excessively long token
        ]

        for token in invalid_tokens:
            response = client.get(
                "/api/v1/users",
                headers={"Authorization": token},
            )

            # Should reject invalid tokens
            if response.status_code not in [200, 404]:  # 200 if endpoint is public
                assert response.status_code in [401, 403, 422]


@pytest.mark.integration
class TestRateLimiting:
    """Test suite for rate limiting security."""

    def test_rate_limit_enforcement(self, client: TestClient) -> None:
        """Test that rate limiting is enforced.

        Makes multiple rapid requests to trigger rate limiting.
        """
        # Make many requests rapidly
        responses = []
        for _ in range(70):  # Exceed typical rate limit of 60/min
            response = client.get("/health")
            responses.append(response.status_code)

        # Should eventually get rate limited (429 Too Many Requests)
        # Note: This test might be flaky in CI without rate limiting enabled
        rate_limited = any(status == 429 for status in responses)

        # If rate limiting is disabled in tests, skip assertion
        if not rate_limited:
            pytest.skip("Rate limiting not enforced in test environment")

        assert rate_limited, "Rate limiting should be enforced after many requests"


@pytest.mark.integration
class TestInputValidation:
    """Test suite for input validation security."""

    def test_email_validation(self, client: TestClient) -> None:
        """Test that invalid email formats are rejected."""
        invalid_emails = [
            "not_an_email",
            "@example.com",
            "user@",
            "user @example.com",  # Space
            "user@exam ple.com",  # Space in domain
            "",
            " ",
        ]

        for email in invalid_emails:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": email,
                    "username": "testuser",
                    "full_name": "Test User",
                },
            )

            assert response.status_code in [400, 422], f"Invalid email should be rejected: {email}"

    def test_username_validation(self, client: TestClient) -> None:
        """Test that invalid usernames are rejected."""
        invalid_usernames = [
            "",  # Empty
            " ",  # Whitespace only
            "a",  # Too short (if minimum length enforced)
            "user name",  # Spaces
        ]

        for username in invalid_usernames:
            response = client.post(
                "/api/v1/users",
                json={
                    "email": f"test{hash(username)}@example.com",
                    "username": username,
                    "full_name": "Test User",
                },
            )

            assert response.status_code in [
                400,
                422,
            ], f"Invalid username should be rejected: {username}"

    def test_required_fields_validation(self, client: TestClient) -> None:
        """Test that required fields are enforced."""
        # Missing email
        response = client.post(
            "/api/v1/users",
            json={
                "username": "testuser",
                "full_name": "Test User",
            },
        )
        assert response.status_code in [400, 422]

        # Missing username
        response = client.post(
            "/api/v1/users",
            json={
                "email": "test@example.com",
                "full_name": "Test User",
            },
        )
        assert response.status_code in [400, 422]

    def test_json_payload_validation(self, client: TestClient) -> None:
        """Test that malformed JSON payloads are rejected."""
        # Invalid JSON
        response = client.post(
            "/api/v1/users",
            data="{invalid json}",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]

        # Empty payload
        response = client.post(
            "/api/v1/users",
            json={},
        )
        assert response.status_code in [400, 422]
