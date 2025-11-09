"""Tests for log sanitization.

Validates that sensitive data is properly redacted from logs to comply with
GDPR, PCI-DSS, and other security regulations.
"""

from hypothesis import given
from hypothesis import strategies as st

from src.infrastructure.logging.config import sanitize_sensitive_data


class TestSanitizeBasicAuthenticationFields:
    """Test sanitization of basic authentication fields.

    These tests verify that common authentication-related fields
    (password, api_key, token, etc.) are properly redacted.
    """

    def test_sanitizes_password_field(self) -> None:
        """Test password field is redacted.

        Arrange: Create event dict with password field
        Act: Call sanitize_sensitive_data
        Assert: Password is redacted, other fields unchanged
        """
        # Arrange
        event_dict = {
            "message": "User login",
            "password": "super-secret-password",
            "username": "testuser",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["username"] == "testuser"
        assert result["message"] == "User login"

    def test_sanitizes_api_key_field(self) -> None:
        """Test api_key field is redacted.

        Arrange: Create event dict with api_key
        Act: Call sanitize_sensitive_data
        Assert: API key is redacted
        """
        # Arrange
        event_dict = {
            "message": "API request",
            "api_key": "sk-1234567890abcdef",
            "endpoint": "/api/users",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["api_key"]
        assert result["endpoint"] == "/api/users"

    def test_sanitizes_access_token_field(self) -> None:
        """Test access_token field is redacted.

        Arrange: Create event dict with access_token
        Act: Call sanitize_sensitive_data
        Assert: Access token is redacted
        """
        # Arrange
        event_dict = {
            "message": "Authentication",
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "user_id": "123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["access_token"]
        assert result["user_id"] == "123"

    def test_sanitizes_refresh_token_field(self) -> None:
        """Test refresh_token field is redacted.

        Arrange: Create event dict with refresh_token
        Act: Call sanitize_sensitive_data
        Assert: Refresh token is redacted
        """
        # Arrange
        event_dict = {
            "message": "Token refresh",
            "refresh_token": "refresh-token-value",
            "user_id": "123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["refresh_token"]
        assert result["user_id"] == "123"

    def test_sanitizes_multiple_auth_fields_simultaneously(self) -> None:
        """Test multiple auth fields are all redacted.

        Arrange: Create event dict with multiple sensitive auth fields
        Act: Call sanitize_sensitive_data
        Assert: All auth fields are redacted
        """
        # Arrange
        event_dict = {
            "message": "Full authentication",
            "password": "secret-password",
            "api_key": "sk-1234567890",
            "access_token": "eyJhbGci...",
            "refresh_token": "refresh-token",
            "username": "testuser",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["password"]
        assert "***REDACTED" in result["api_key"]
        assert "***REDACTED" in result["access_token"]
        assert "***REDACTED" in result["refresh_token"]
        assert result["username"] == "testuser"


class TestSanitizeHTTPHeaders:
    """Test sanitization of HTTP headers.

    HTTP headers often contain sensitive authentication data
    that must be redacted from logs.
    """

    def test_sanitizes_authorization_header(self) -> None:
        """Test Authorization header is redacted.

        Arrange: Create event dict with Authorization header
        Act: Call sanitize_sensitive_data
        Assert: Authorization is redacted, Content-Type unchanged
        """
        # Arrange
        event_dict = {
            "message": "HTTP request",
            "headers": {
                "Authorization": "Bearer token123",
                "Content-Type": "application/json",
            },
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["headers"]["Authorization"]
        assert result["headers"]["Content-Type"] == "application/json"

    def test_preserves_non_sensitive_headers(self) -> None:
        """Test non-sensitive headers are preserved.

        Note: Cookie header is not redacted at top level (only as
        http.request.header.cookie in telemetry spans).

        Arrange: Create event dict with headers
        Act: Call sanitize_sensitive_data
        Assert: Non-sensitive headers are preserved
        """
        # Arrange
        event_dict = {
            "message": "HTTP request",
            "headers": {
                "Cookie": "session=abc123; token=xyz789",
                "Accept": "application/json",
            },
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        # Cookie is not a sensitive key pattern (only http.request.header.cookie is)
        assert result["headers"]["Cookie"] == "session=abc123; token=xyz789"
        assert result["headers"]["Accept"] == "application/json"

    def test_sanitizes_multiple_sensitive_headers(self) -> None:
        """Test multiple sensitive headers are redacted.

        Arrange: Create event dict with multiple sensitive headers
        Act: Call sanitize_sensitive_data
        Assert: All sensitive headers are redacted
        """
        # Arrange
        event_dict = {
            "message": "HTTP request",
            "headers": {
                "Authorization": "Bearer token123",
                "X-API-Key": "sk-1234567890",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["headers"]["Authorization"]
        assert "***REDACTED" in result["headers"]["X-API-Key"]
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["headers"]["User-Agent"] == "Mozilla/5.0"


class TestSanitizePaymentFields:
    """Test sanitization of payment/PCI-DSS fields.

    Payment card data must be redacted to comply with PCI-DSS.
    """

    def test_sanitizes_credit_card_field(self) -> None:
        """Test credit_card field is redacted.

        Arrange: Create event dict with credit_card
        Act: Call sanitize_sensitive_data
        Assert: Credit card is redacted, amount unchanged
        """
        # Arrange
        event_dict = {
            "message": "Payment processing",
            "credit_card": "4111111111111111",
            "amount": "99.99",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["credit_card"]
        assert result["amount"] == "99.99"

    def test_sanitizes_credit_card_number_field(self) -> None:
        """Test credit_card_number field is redacted.

        Arrange: Create event dict with credit_card_number
        Act: Call sanitize_sensitive_data
        Assert: Card number is redacted
        """
        # Arrange
        event_dict = {
            "message": "Payment processing",
            "credit_card_number": "4111111111111111",
            "amount": "99.99",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["credit_card_number"]
        assert result["amount"] == "99.99"

    def test_sanitizes_cvv_field(self) -> None:
        """Test cvv field is redacted.

        Arrange: Create event dict with cvv
        Act: Call sanitize_sensitive_data
        Assert: CVV is redacted
        """
        # Arrange
        event_dict = {
            "message": "Payment validation",
            "cvv": "123",
            "last_four": "1111",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["cvv"]
        # last_four might or might not be redacted depending on implementation

    def test_sanitizes_pin_field(self) -> None:
        """Test pin field is redacted.

        Arrange: Create event dict with pin
        Act: Call sanitize_sensitive_data
        Assert: PIN is redacted
        """
        # Arrange
        event_dict = {
            "message": "PIN verification",
            "pin": "1234",
            "user_id": "123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["pin"]
        assert result["user_id"] == "123"

    def test_sanitizes_all_payment_fields(self) -> None:
        """Test all payment fields are redacted together.

        Arrange: Create event dict with multiple payment fields
        Act: Call sanitize_sensitive_data
        Assert: All payment fields are redacted
        """
        # Arrange
        event_dict = {
            "message": "Payment processing",
            "credit_card": "4111111111111111",
            "credit_card_number": "4111111111111111",
            "cvv": "123",
            "pin": "1234",
            "amount": "99.99",
            "currency": "USD",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["credit_card"]
        assert "***REDACTED" in result["credit_card_number"]
        assert "***REDACTED" in result["cvv"]
        assert "***REDACTED" in result["pin"]
        assert result["amount"] == "99.99"
        assert result["currency"] == "USD"


class TestSanitizePIIFields:
    """Test sanitization of PII fields.

    Personal Identifiable Information must be redacted for GDPR compliance.
    """

    def test_sanitizes_ssn_field(self) -> None:
        """Test ssn field is redacted.

        Arrange: Create event dict with ssn
        Act: Call sanitize_sensitive_data
        Assert: SSN is redacted
        """
        # Arrange
        event_dict = {
            "message": "User registration",
            "ssn": "123-45-6789",
            "name": "John Doe",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["ssn"]
        assert result["name"] == "John Doe"

    def test_sanitizes_social_security_number_field(self) -> None:
        """Test social_security_number field is redacted.

        Arrange: Create event dict with social_security_number
        Act: Call sanitize_sensitive_data
        Assert: SSN is redacted
        """
        # Arrange
        event_dict = {
            "message": "User verification",
            "social_security_number": "987-65-4321",
            "user_id": "123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["social_security_number"]
        assert result["user_id"] == "123"


class TestSanitizeDatabaseFields:
    """Test sanitization of database connection fields.

    Database URLs and connection strings often contain passwords.
    """

    def test_sanitizes_database_url_field(self) -> None:
        """Test database_url field is redacted.

        Arrange: Create event dict with database_url
        Act: Call sanitize_sensitive_data
        Assert: Database URL is redacted
        """
        # Arrange
        event_dict = {
            "message": "Database connection",
            "database_url": "postgresql://user:password@localhost:5432/db",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["database_url"]

    def test_sanitizes_connection_string_field(self) -> None:
        """Test connection_string field is redacted.

        Arrange: Create event dict with connection_string
        Act: Call sanitize_sensitive_data
        Assert: Connection string is redacted
        """
        # Arrange
        event_dict = {
            "message": "Database setup",
            "connection_string": "Server=localhost;Database=db;User=user;Password=pass",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["connection_string"]


class TestSanitizeSecretFields:
    """Test sanitization of secret/key fields.

    Secret keys and encryption keys must be protected.
    """

    def test_sanitizes_secret_key_field(self) -> None:
        """Test secret_key field is redacted.

        Arrange: Create event dict with secret_key
        Act: Call sanitize_sensitive_data
        Assert: Secret key is redacted
        """
        # Arrange
        event_dict = {
            "message": "Configuration loaded",
            "secret_key": "my-secret-key-123",
            "app_name": "MyApp",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["secret_key"]
        assert result["app_name"] == "MyApp"

    def test_sanitizes_uppercase_secret_key(self) -> None:
        """Test SECRET_KEY field is redacted.

        Arrange: Create event dict with uppercase SECRET_KEY
        Act: Call sanitize_sensitive_data
        Assert: Secret key is redacted
        """
        # Arrange
        event_dict = {
            "message": "Config",
            "SECRET_KEY": "another-secret",
            "DEBUG": "true",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["SECRET_KEY"]
        assert result["DEBUG"] == "true"

    def test_preserves_non_sensitive_key_fields(self) -> None:
        """Test non-sensitive key fields are preserved.

        Note: Fields like 'encryption_key' don't match sensitive patterns
        (only 'secret', 'secret_key', 'api_key' match).

        Arrange: Create event dict with encryption_key
        Act: Call sanitize_sensitive_data
        Assert: Non-sensitive fields are preserved
        """
        # Arrange
        event_dict = {
            "message": "Encryption setup",
            "encryption_key": "aes-256-key",
            "algorithm": "AES-256-GCM",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        # encryption_key doesn't match any pattern (only 'secret', 'secret_key', etc.)
        assert result["encryption_key"] == "aes-256-key"
        assert result["algorithm"] == "AES-256-GCM"


class TestSanitizeNestedStructures:
    """Test sanitization of nested data structures.

    Sensitive fields in nested dicts and lists must be sanitized recursively.
    """

    def test_sanitizes_nested_dict(self) -> None:
        """Test nested dict fields are sanitized recursively.

        Arrange: Create event dict with nested user dict
        Act: Call sanitize_sensitive_data
        Assert: Nested password is redacted, other fields unchanged
        """
        # Arrange
        event_dict = {
            "message": "User data",
            "user": {
                "username": "testuser",
                "password": "secret123",
                "email": "test@example.com",
            },
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["user"]["username"] == "testuser"
        assert "***REDACTED" in result["user"]["password"]
        assert result["user"]["email"] == "test@example.com"

    def test_sanitizes_deeply_nested_dict(self) -> None:
        """Test deeply nested structures are sanitized.

        Arrange: Create event dict with 4-level nested structure
        Act: Call sanitize_sensitive_data
        Assert: Deeply nested api_key is redacted
        """
        # Arrange
        event_dict = {
            "message": "Complex data",
            "data": {
                "level1": {
                    "level2": {
                        "level3": {
                            "api_key": "secret-key-123",
                            "public_data": "public",
                        }
                    }
                }
            },
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["data"]["level1"]["level2"]["level3"]["api_key"]
        assert result["data"]["level1"]["level2"]["level3"]["public_data"] == "public"

    def test_sanitizes_list_of_dicts(self) -> None:
        """Test list of dicts is sanitized.

        Arrange: Create event dict with list of user dicts
        Act: Call sanitize_sensitive_data
        Assert: Passwords in all list items are redacted
        """
        # Arrange
        event_dict = {
            "message": "Multiple users",
            "users": [
                {"username": "user1", "password": "pass1"},
                {"username": "user2", "password": "pass2"},
            ],
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["users"][0]["username"] == "user1"
        assert "***REDACTED" in result["users"][0]["password"]
        assert result["users"][1]["username"] == "user2"
        assert "***REDACTED" in result["users"][1]["password"]

    def test_sanitizes_mixed_nested_structures(self) -> None:
        """Test mixed nested structures (dicts and lists).

        Arrange: Create event dict with nested dicts and lists
        Act: Call sanitize_sensitive_data
        Assert: All sensitive fields in nested structures are redacted
        """
        # Arrange
        event_dict = {
            "message": "Complex structure",
            "data": {
                "configs": [
                    {"name": "config1", "api_key": "key1"},
                    {"name": "config2", "secret": "secret1"},
                ],
                "metadata": {"token": "token123", "version": "1.0"},
            },
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["data"]["configs"][0]["name"] == "config1"
        assert "***REDACTED" in result["data"]["configs"][0]["api_key"]
        assert result["data"]["configs"][1]["name"] == "config2"
        assert "***REDACTED" in result["data"]["configs"][1]["secret"]
        assert "***REDACTED" in result["data"]["metadata"]["token"]
        assert result["data"]["metadata"]["version"] == "1.0"

    def test_sanitizes_triple_nested_list_of_dicts(self) -> None:
        """Test triple-nested list of dicts is sanitized.

        Arrange: Create event dict with list -> dict -> list -> dict
        Act: Call sanitize_sensitive_data
        Assert: All nested passwords are redacted
        """
        # Arrange
        event_dict = {
            "message": "Complex nesting",
            "groups": [
                {
                    "name": "admin",
                    "users": [
                        {"username": "admin1", "password": "secret1"},
                        {"username": "admin2", "password": "secret2"},
                    ],
                }
            ],
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["groups"][0]["name"] == "admin"
        assert "***REDACTED" in result["groups"][0]["users"][0]["password"]
        assert "***REDACTED" in result["groups"][0]["users"][1]["password"]


class TestSanitizeCaseInsensitivity:
    """Test case-insensitive field name matching.

    Sensitive field detection must work regardless of case.
    """

    def test_sanitizes_uppercase_fields(self) -> None:
        """Test uppercase sensitive field names are redacted.

        Arrange: Create event dict with uppercase field names
        Act: Call sanitize_sensitive_data
        Assert: All uppercase sensitive fields are redacted
        """
        # Arrange
        event_dict = {
            "PASSWORD": "secret",
            "API_KEY": "key123",
            "TOKEN": "token456",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["PASSWORD"]
        assert "***REDACTED" in result["API_KEY"]
        assert "***REDACTED" in result["TOKEN"]

    def test_sanitizes_mixed_case_fields(self) -> None:
        """Test mixed-case sensitive field names are redacted.

        Arrange: Create event dict with PascalCase and camelCase fields
        Act: Call sanitize_sensitive_data
        Assert: All mixed-case sensitive fields are redacted
        """
        # Arrange
        event_dict = {
            "Password": "secret",
            "ApiKey": "key123",
            "accessToken": "token456",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["Password"]
        assert "***REDACTED" in result["ApiKey"]
        assert "***REDACTED" in result["accessToken"]

    def test_sanitizes_fields_with_hyphens(self) -> None:
        """Test field names with hyphens are sanitized.

        Arrange: Create event dict with hyphenated field names
        Act: Call sanitize_sensitive_data
        Assert: Hyphenated sensitive fields are redacted
        """
        # Arrange
        event_dict = {
            "api-key": "key123",
            "access-token": "token123",
            "public-id": "id123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["api-key"]
        assert "***REDACTED" in result["access-token"]
        assert result["public-id"] == "id123"

    def test_sanitizes_fields_with_underscores(self) -> None:
        """Test field names with underscores are sanitized.

        Arrange: Create event dict with underscored field names
        Act: Call sanitize_sensitive_data
        Assert: Underscored sensitive fields are redacted
        """
        # Arrange
        event_dict = {
            "api_key": "key456",
            "access_token": "token456",
            "user_id": "user123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["api_key"]
        assert "***REDACTED" in result["access_token"]
        assert result["user_id"] == "user123"


class TestSanitizeOAuthFields:
    """Test sanitization of OAuth-related fields.

    OAuth tokens and secrets must be redacted.
    """

    def test_sanitizes_oauth_token(self) -> None:
        """Test oauth_token field is redacted.

        Arrange: Create event dict with oauth_token
        Act: Call sanitize_sensitive_data
        Assert: OAuth token is redacted
        """
        # Arrange
        event_dict = {
            "oauth_token": "token123",
            "provider": "google",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["oauth_token"]
        assert result["provider"] == "google"

    def test_sanitizes_oauth_secret(self) -> None:
        """Test oauth_secret field is redacted.

        Arrange: Create event dict with oauth_secret
        Act: Call sanitize_sensitive_data
        Assert: OAuth secret is redacted
        """
        # Arrange
        event_dict = {
            "oauth_secret": "secret456",
            "provider": "github",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["oauth_secret"]
        assert result["provider"] == "github"

    def test_sanitizes_client_secret(self) -> None:
        """Test client_secret field is redacted.

        Arrange: Create event dict with client_secret
        Act: Call sanitize_sensitive_data
        Assert: Client secret is redacted, client_id unchanged
        """
        # Arrange
        event_dict = {
            "client_secret": "client-secret",
            "client_id": "client-123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["client_secret"]
        assert result["client_id"] == "client-123"


class TestSanitizeJWTFields:
    """Test sanitization of JWT-related fields.

    JWT tokens must be redacted from logs.
    """

    def test_sanitizes_jwt_field(self) -> None:
        """Test jwt field is redacted.

        Arrange: Create event dict with jwt
        Act: Call sanitize_sensitive_data
        Assert: JWT is redacted
        """
        # Arrange
        event_dict = {
            "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "algorithm": "HS256",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["jwt"]
        assert result["algorithm"] == "HS256"

    def test_sanitizes_jwt_token_field(self) -> None:
        """Test jwt_token field is redacted.

        Arrange: Create event dict with jwt_token
        Act: Call sanitize_sensitive_data
        Assert: JWT token is redacted
        """
        # Arrange
        event_dict = {
            "jwt_token": "token123",
            "issuer": "auth-server",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["jwt_token"]
        assert result["issuer"] == "auth-server"

    def test_sanitizes_bearer_token_field(self) -> None:
        """Test bearer_token field is redacted.

        Note: Fields containing 'token' or 'auth' are redacted
        (e.g., 'token_type', 'auth_scheme' match sensitive patterns).

        Arrange: Create event dict with bearer_token
        Act: Call sanitize_sensitive_data
        Assert: Bearer token is redacted
        """
        # Arrange
        event_dict = {
            "bearer_token": "bearer123",
            "scheme": "Bearer",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["bearer_token"]
        assert result["scheme"] == "Bearer"


class TestSanitizeSessionFields:
    """Test sanitization of session-related fields.

    Session tokens and CSRF tokens must be redacted.
    """

    def test_sanitizes_session_token(self) -> None:
        """Test session_token field is redacted.

        Arrange: Create event dict with session_token
        Act: Call sanitize_sensitive_data
        Assert: Session token is redacted
        """
        # Arrange
        event_dict = {
            "session_token": "token456",
            "user_id": "123",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["session_token"]
        assert result["user_id"] == "123"

    def test_sanitizes_csrf_token(self) -> None:
        """Test csrf_token field is redacted.

        Arrange: Create event dict with csrf_token
        Act: Call sanitize_sensitive_data
        Assert: CSRF token is redacted
        """
        # Arrange
        event_dict = {
            "csrf_token": "csrf789",
            "method": "POST",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["csrf_token"]
        assert result["method"] == "POST"


class TestSanitizeEdgeCases:
    """Test edge cases in log sanitization.

    Ensure sanitizer handles unusual inputs gracefully.
    """

    def test_sanitizes_empty_dict(self) -> None:
        """Test empty dict returns empty dict.

        Arrange: Create empty event dict
        Act: Call sanitize_sensitive_data
        Assert: Result is empty dict
        """
        # Arrange
        event_dict = {}

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result == {}

    def test_preserves_none_values(self) -> None:
        """Test None values are preserved.

        Arrange: Create event dict with None value
        Act: Call sanitize_sensitive_data
        Assert: None value is preserved, password redacted
        """
        # Arrange
        event_dict = {
            "message": "Test",
            "data": None,
            "password": "secret",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["message"] == "Test"
        assert result["data"] is None
        assert "***REDACTED" in result["password"]

    def test_sanitizes_empty_string_password(self) -> None:
        """Test empty string password is still redacted.

        Arrange: Create event dict with empty string password
        Act: Call sanitize_sensitive_data
        Assert: Empty password is redacted
        """
        # Arrange
        event_dict = {
            "message": "",
            "password": "",
            "username": "",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["message"] == ""
        assert "***REDACTED" in result["password"]
        assert result["username"] == ""

    def test_preserves_numeric_values_in_non_sensitive_fields(self) -> None:
        """Test numeric values in non-sensitive fields are preserved.

        Arrange: Create event dict with numeric values
        Act: Call sanitize_sensitive_data
        Assert: Non-sensitive numeric values preserved, pin redacted
        """
        # Arrange
        event_dict = {
            "message": "User action",
            "user_id": 123,
            "count": 456,
            "amount": 99.99,
            "pin": 1234,
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["user_id"] == 123
        assert result["count"] == 456
        assert result["amount"] == 99.99
        assert "***REDACTED" in result["pin"]

    def test_preserves_boolean_values(self) -> None:
        """Test boolean values are preserved.

        Arrange: Create event dict with boolean values
        Act: Call sanitize_sensitive_data
        Assert: Boolean values are preserved
        """
        # Arrange
        event_dict = {
            "message": "Status",
            "is_active": True,
            "is_admin": False,
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["is_active"] is True
        assert result["is_admin"] is False

    def test_preserves_list_of_primitives_for_non_sensitive_fields(self) -> None:
        """Test lists of primitives in non-sensitive fields are preserved.

        Arrange: Create event dict with lists
        Act: Call sanitize_sensitive_data
        Assert: Non-sensitive lists preserved, sensitive lists redacted
        """
        # Arrange
        event_dict = {
            "message": "Data",
            "ids": [1, 2, 3],
            "tags": ["tag1", "tag2"],
            "passwords": ["pass1", "pass2"],
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["ids"] == [1, 2, 3]
        assert result["tags"] == ["tag1", "tag2"]
        # Sensitive field name causes entire value to be redacted
        assert "***REDACTED" in result["passwords"]

    def test_handles_dict_with_only_sensitive_fields(self) -> None:
        """Test dict with only sensitive fields.

        Arrange: Create event dict with only sensitive fields
        Act: Call sanitize_sensitive_data
        Assert: All fields are redacted
        """
        # Arrange
        event_dict = {
            "password": "secret",
            "api_key": "key123",
            "token": "token456",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["password"]
        assert "***REDACTED" in result["api_key"]
        assert "***REDACTED" in result["token"]

    def test_handles_dict_with_no_sensitive_fields(self) -> None:
        """Test dict with no sensitive fields.

        Arrange: Create event dict with only non-sensitive fields
        Act: Call sanitize_sensitive_data
        Assert: All fields are unchanged
        """
        # Arrange
        event_dict = {
            "message": "Test message",
            "user_id": "123",
            "action": "login",
            "timestamp": "2024-01-01T00:00:00",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result == event_dict


class TestSanitizeProcessorInterface:
    """Test the processor interface contract.

    The sanitize_sensitive_data function must work as a structlog processor.
    """

    def test_accepts_three_positional_arguments(self) -> None:
        """Test processor accepts logger, method_name, event_dict.

        Arrange: Create event dict with password
        Act: Call with all three arguments
        Assert: Password is redacted
        """
        # Arrange
        logger = None
        method_name = "info"
        event_dict = {"password": "secret", "message": "test"}

        # Act
        result = sanitize_sensitive_data(logger, method_name, event_dict)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["message"] == "test"

    def test_ignores_logger_argument(self) -> None:
        """Test processor ignores logger argument.

        Arrange: Create event dict, pass mock logger
        Act: Call with mock logger
        Assert: Result is same regardless of logger value
        """
        # Arrange
        event_dict = {"password": "secret", "user_id": "123"}

        # Act
        result1 = sanitize_sensitive_data(None, None, event_dict)
        result2 = sanitize_sensitive_data("mock_logger", None, event_dict)

        # Assert
        assert result1 == result2

    def test_ignores_method_name_argument(self) -> None:
        """Test processor ignores method_name argument.

        Arrange: Create event dict, pass different method names
        Act: Call with different method names
        Assert: Result is same regardless of method_name value
        """
        # Arrange
        event_dict = {"api_key": "key123", "endpoint": "/api/test"}

        # Act
        result1 = sanitize_sensitive_data(None, "info", event_dict)
        result2 = sanitize_sensitive_data(None, "error", event_dict)

        # Assert
        assert result1 == result2

    def test_returns_dict(self) -> None:
        """Test processor returns a dict.

        Arrange: Create event dict
        Act: Call sanitize_sensitive_data
        Assert: Result is a dict
        """
        # Arrange
        event_dict = {"message": "test", "password": "secret"}

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert isinstance(result, dict)


class TestSanitizePropertyBased:
    """Property-based tests for sanitization.

    Use Hypothesis to test sanitization with generated inputs.
    """

    @given(st.text(min_size=1, max_size=100))
    def test_always_redacts_password_field(self, password_value: str) -> None:
        """Test password field is always redacted regardless of value.

        Arrange: Create event dict with generated password value
        Act: Call sanitize_sensitive_data
        Assert: Password is redacted
        """
        # Arrange
        event_dict = {"password": password_value, "user_id": "123"}

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["user_id"] == "123"

    @given(st.text(min_size=1, max_size=100))
    def test_always_redacts_api_key_field(self, api_key_value: str) -> None:
        """Test api_key field is always redacted regardless of value.

        Arrange: Create event dict with generated api_key value
        Act: Call sanitize_sensitive_data
        Assert: API key is redacted
        """
        # Arrange
        event_dict = {"api_key": api_key_value, "endpoint": "/test"}

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert "***REDACTED" in result["api_key"]
        assert result["endpoint"] == "/test"

    @given(st.integers(), st.floats(allow_nan=False, allow_infinity=False))
    def test_preserves_numeric_types_in_safe_fields(self, int_val: int, float_val: float) -> None:
        """Test numeric values in safe fields are preserved.

        Arrange: Create event dict with generated numeric values
        Act: Call sanitize_sensitive_data
        Assert: Numeric values are preserved
        """
        # Arrange
        event_dict = {
            "count": int_val,
            "amount": float_val,
            "message": "test",
        }

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["count"] == int_val
        assert result["amount"] == float_val

    @given(st.booleans())
    def test_preserves_boolean_values_in_safe_fields(self, bool_val: bool) -> None:
        """Test boolean values are preserved.

        Arrange: Create event dict with generated boolean
        Act: Call sanitize_sensitive_data
        Assert: Boolean is preserved
        """
        # Arrange
        event_dict = {"is_active": bool_val, "message": "test"}

        # Act
        result = sanitize_sensitive_data(None, None, event_dict)

        # Assert
        assert result["is_active"] == bool_val
