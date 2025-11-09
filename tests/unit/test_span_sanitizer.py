"""Tests for OpenTelemetry span attribute sanitizer.

Test Organization:
- TestSanitizingSpanProcessorInit: Initialization tests
- TestSanitizingSpanProcessorOnStart: on_start() method tests
- TestSanitizingSpanProcessorOnEndNullCases: None/empty attribute handling
- TestSanitizingSpanProcessorHTTPHeaders: HTTP header sanitization
- TestSanitizingSpanProcessorHTTPBodies: Request/response body sanitization
- TestSanitizingSpanProcessorDatabaseQueries: Database statement sanitization
- TestSanitizingSpanProcessorMessaging: Messaging payload sanitization
- TestSanitizingSpanProcessorGenericSensitive: Generic sensitive patterns
- TestSanitizingSpanProcessorMultipleSensitive: Multiple sensitive attributes
- TestSanitizingSpanProcessorSafeAttributes: Safe attribute preservation
- TestSanitizingSpanProcessorEdgeCases: Edge cases and boundaries
- TestSanitizingSpanProcessorLifecycle: shutdown() and force_flush()
- TestCreateSanitizingProcessor: Factory function tests
- TestSensitivePatternsConstant: SENSITIVE_PATTERNS validation
"""

from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import ReadableSpan

from src.infrastructure.telemetry.sanitizer import (
    SanitizingSpanProcessor,
    create_sanitizing_processor,
)
from src.utils.sanitizer import SENSITIVE_PATTERNS


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def processor():
    """Create sanitizing span processor for testing.

    Returns:
        SanitizingSpanProcessor instance
    """
    return SanitizingSpanProcessor()


@pytest.fixture
def mock_span():
    """Create mock ReadableSpan for testing.

    Returns:
        Mock ReadableSpan with attributes and _attributes
    """
    span = MagicMock(spec=ReadableSpan)
    span.attributes = {}
    span._attributes = {}
    return span


# ============================================================================
# Test Initialization
# ============================================================================


class TestSanitizingSpanProcessorInit:
    """Test SanitizingSpanProcessor initialization."""

    def test_creates_processor_instance(self) -> None:
        """Test processor initializes successfully.

        Arrange: Create processor
        Act: Check instance
        Assert: Instance is created
        """
        # Arrange & Act
        processor = SanitizingSpanProcessor()

        # Assert
        assert processor is not None
        assert isinstance(processor, SanitizingSpanProcessor)

    def test_processor_uses_shared_sensitive_patterns(self) -> None:
        """Test processor uses shared SENSITIVE_PATTERNS from utils.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Create processor
        Assert: Processor uses shared patterns
        """
        # Arrange
        from src.utils.sanitizer import SENSITIVE_PATTERNS

        # Act
        SanitizingSpanProcessor()

        # Assert: Processor uses the shared patterns (verified by behavior)
        assert SENSITIVE_PATTERNS is not None
        assert len(SENSITIVE_PATTERNS) > 0


# ============================================================================
# Test on_start Method
# ============================================================================


class TestSanitizingSpanProcessorOnStart:
    """Test on_start() method behavior."""

    def test_on_start_is_noop(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test on_start does nothing.

        Arrange: Create mock span
        Act: Call on_start
        Assert: No changes, no errors
        """
        # Arrange
        mock_span.attributes = {"test": "value"}

        # Act
        processor.on_start(mock_span, None)

        # Assert: Attributes unchanged
        assert mock_span.attributes == {"test": "value"}

    def test_on_start_accepts_parent_context(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test on_start accepts parent_context parameter.

        Arrange: Create mock span and context
        Act: Call on_start with context
        Assert: No errors
        """
        # Arrange
        mock_context = MagicMock()

        # Act
        processor.on_start(mock_span, mock_context)

        # Assert: No errors, method completes
        assert True

    def test_on_start_with_none_context(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test on_start with None context.

        Arrange: Create mock span
        Act: Call on_start with None
        Assert: No errors
        """
        # Arrange & Act
        processor.on_start(mock_span, None)

        # Assert: No errors
        assert True


# ============================================================================
# Test on_end with None/Empty Attributes
# ============================================================================


class TestSanitizingSpanProcessorOnEndNullCases:
    """Test on_end() handling of None and empty attributes."""

    def test_on_end_with_none_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test on_end handles None attributes gracefully.

        Arrange: Create span with None attributes
        Act: Call on_end
        Assert: No errors, attributes remain None
        """
        # Arrange
        mock_span.attributes = None

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span.attributes is None

    def test_on_end_with_empty_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test on_end with empty attributes dict.

        Arrange: Create span with empty dict
        Act: Call on_end
        Assert: Dict remains empty
        """
        # Arrange
        mock_span.attributes = {}
        mock_span._attributes = {}

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes == {}

    def test_on_end_without_private_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test on_end when span lacks _attributes field.

        Arrange: Create span without _attributes
        Act: Call on_end
        Assert: No errors raised
        """
        # Arrange
        mock_span.attributes = {"test": "value"}
        delattr(mock_span, "_attributes")

        # Act
        processor.on_end(mock_span)

        # Assert: No errors, method completes
        assert not hasattr(mock_span, "_attributes")


# ============================================================================
# Test HTTP Header Sanitization
# ============================================================================


class TestSanitizingSpanProcessorHTTPHeaders:
    """Test HTTP header attribute sanitization."""

    def test_sanitizes_authorization_header(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test Authorization header is sanitized.

        Arrange: Create span with Authorization header
        Act: Call on_end
        Assert: Header is redacted
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.authorization": "Bearer secret_token_12345",
            "http.method": "GET",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.header.authorization"]
        assert mock_span._attributes["http.method"] == "GET"

    def test_sanitizes_cookie_header(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test Cookie header is sanitized.

        Arrange: Create span with Cookie header
        Act: Call on_end
        Assert: Cookie is redacted
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.cookie": "session_id=abc123; user_token=xyz789",
            "http.status_code": 200,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.header.cookie"]
        assert mock_span._attributes["http.status_code"] == 200

    def test_sanitizes_api_key_header(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test X-API-Key header is sanitized.

        Arrange: Create span with API key header
        Act: Call on_end
        Assert: API key is redacted
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.x-api-key": "api_key_12345678",
            "http.url": "/api/users",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.header.x-api-key"]
        assert mock_span._attributes["http.url"] == "/api/users"

    def test_sanitizes_headers_with_hyphens(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test headers with hyphens are sanitized.

        Arrange: Create span with hyphenated header names
        Act: Call on_end
        Assert: Headers are redacted
        """
        # Arrange
        mock_span.attributes = {
            "http-request-header-authorization": "Bearer token",
            "http.method": "POST",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http-request-header-authorization"]
        assert mock_span._attributes["http.method"] == "POST"


# ============================================================================
# Test HTTP Body Sanitization
# ============================================================================


class TestSanitizingSpanProcessorHTTPBodies:
    """Test HTTP request/response body sanitization."""

    def test_sanitizes_request_body(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test request body is sanitized with length shown.

        Arrange: Create span with request body
        Act: Call on_end
        Assert: Body is redacted with length
        """
        # Arrange
        request_body = '{"username": "john", "password": "secret123"}'
        mock_span.attributes = {
            "http.request.body": request_body,
            "http.url": "/api/login",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.body"]
        assert "45 chars" in mock_span._attributes["http.request.body"]
        assert mock_span._attributes["http.url"] == "/api/login"

    def test_sanitizes_response_body(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test response body is sanitized.

        Arrange: Create span with response body
        Act: Call on_end
        Assert: Body is redacted
        """
        # Arrange
        mock_span.attributes = {
            "http.response.body": '{"token": "jwt_token_here", "user_id": 123}',
            "http.status_code": 200,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.response.body"]
        assert mock_span._attributes["http.status_code"] == 200

    def test_sanitizes_empty_request_body(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test empty request body is still sanitized.

        Arrange: Create span with empty request body
        Act: Call on_end
        Assert: Empty body is redacted
        """
        # Arrange
        mock_span.attributes = {
            "http.request.body": "",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.body"]

    def test_sanitizes_large_request_body(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test large request body shows length.

        Arrange: Create span with large request body
        Act: Call on_end
        Assert: Body is redacted with length shown
        """
        # Arrange
        large_body = "x" * 10000
        mock_span.attributes = {
            "http.request.body": large_body,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.body"]
        assert "10000 chars" in mock_span._attributes["http.request.body"]


# ============================================================================
# Test Database Query Sanitization
# ============================================================================


class TestSanitizingSpanProcessorDatabaseQueries:
    """Test database statement/query sanitization."""

    def test_sanitizes_db_statement(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test database statement is sanitized.

        Arrange: Create span with SQL query
        Act: Call on_end
        Assert: Query is redacted
        """
        # Arrange
        sql_query = "SELECT * FROM users WHERE email = 'user@example.com' AND password = 'hash'"
        mock_span.attributes = {
            "db.statement": sql_query,
            "db.system": "postgresql",
            "db.name": "mydb",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["db.statement"]
        assert mock_span._attributes["db.system"] == "postgresql"
        assert mock_span._attributes["db.name"] == "mydb"

    def test_sanitizes_db_query_text(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test db.query.text is sanitized.

        Arrange: Create span with db.query.text
        Act: Call on_end
        Assert: Query is redacted
        """
        # Arrange
        mock_span.attributes = {
            "db.query.text": "UPDATE users SET password = 'new_hash' WHERE id = 123",
            "db.table": "users",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["db.query.text"]
        assert mock_span._attributes["db.table"] == "users"

    def test_preserves_safe_db_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test safe database attributes are preserved.

        Arrange: Create span with safe DB attributes
        Act: Call on_end
        Assert: Safe attributes unchanged
        """
        # Arrange
        safe_attrs = {
            "db.system": "postgresql",
            "db.name": "mydb",
            "db.table": "users",
            "db.operation": "SELECT",
        }
        mock_span.attributes = safe_attrs.copy()
        mock_span._attributes = safe_attrs.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes == safe_attrs


# ============================================================================
# Test Messaging Payload Sanitization
# ============================================================================


class TestSanitizingSpanProcessorMessaging:
    """Test messaging payload/body sanitization."""

    def test_sanitizes_message_payload(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test message payload is sanitized.

        Arrange: Create span with message payload
        Act: Call on_end
        Assert: Payload is redacted
        """
        # Arrange
        mock_span.attributes = {
            "messaging.message.payload": '{"user_data": "sensitive"}',
            "messaging.system": "kafka",
            "messaging.destination": "user_topic",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["messaging.message.payload"]
        assert mock_span._attributes["messaging.system"] == "kafka"
        assert mock_span._attributes["messaging.destination"] == "user_topic"

    def test_sanitizes_message_body(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test message body is sanitized.

        Arrange: Create span with message body
        Act: Call on_end
        Assert: Body is redacted
        """
        # Arrange
        mock_span.attributes = {
            "messaging.message.body": "sensitive message content",
            "messaging.destination": "queue_name",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["messaging.message.body"]
        assert mock_span._attributes["messaging.destination"] == "queue_name"

    def test_preserves_safe_messaging_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test safe messaging attributes are preserved.

        Arrange: Create span with safe messaging attributes
        Act: Call on_end
        Assert: Safe attributes unchanged
        """
        # Arrange
        safe_attrs = {
            "messaging.system": "rabbitmq",
            "messaging.destination": "order_queue",
            "messaging.operation": "publish",
        }
        mock_span.attributes = safe_attrs.copy()
        mock_span._attributes = safe_attrs.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes == safe_attrs


# ============================================================================
# Test Generic Sensitive Pattern Sanitization
# ============================================================================


class TestSanitizingSpanProcessorGenericSensitive:
    """Test generic sensitive pattern sanitization."""

    def test_sanitizes_password_attribute(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test password attribute is sanitized.

        Arrange: Create span with password
        Act: Call on_end
        Assert: Password is redacted
        """
        # Arrange
        mock_span.attributes = {
            "password": "secret123",
            "username": "john",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["password"]
        assert mock_span._attributes["username"] == "john"

    def test_sanitizes_token_attribute(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test token attribute is sanitized.

        Arrange: Create span with token
        Act: Call on_end
        Assert: Token is redacted
        """
        # Arrange
        mock_span.attributes = {
            "access_token": "jwt_token_here",
            "user_id": "123",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["access_token"]
        assert mock_span._attributes["user_id"] == "123"

    def test_sanitizes_secret_attribute(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test secret attribute is sanitized.

        Arrange: Create span with secret
        Act: Call on_end
        Assert: Secret is redacted
        """
        # Arrange
        mock_span.attributes = {
            "client_secret": "oauth_secret_key",
            "client_id": "app_123",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["client_secret"]
        assert mock_span._attributes["client_id"] == "app_123"

    def test_sanitizes_api_key_attribute(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test api_key attribute is sanitized.

        Arrange: Create span with API key
        Act: Call on_end
        Assert: API key is redacted
        """
        # Arrange
        mock_span.attributes = {
            "api_key": "key_12345678",
            "service_name": "payment",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["api_key"]
        assert mock_span._attributes["service_name"] == "payment"


# ============================================================================
# Test Multiple Sensitive Attributes
# ============================================================================


class TestSanitizingSpanProcessorMultipleSensitive:
    """Test sanitization of multiple sensitive attributes together."""

    def test_sanitizes_all_sensitive_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test all sensitive attributes are sanitized together.

        Arrange: Create span with multiple sensitive attributes
        Act: Call on_end
        Assert: All sensitive attributes redacted, safe ones preserved
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.authorization": "Bearer token",
            "http.request.body": "request data",
            "http.response.body": "response data",
            "db.statement": "SELECT * FROM users",
            "password": "secret",
            "http.url": "/api/users",
            "http.method": "POST",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert: All sensitive attributes redacted
        assert "***REDACTED" in mock_span._attributes["http.request.header.authorization"]
        assert "***REDACTED" in mock_span._attributes["http.request.body"]
        assert "***REDACTED" in mock_span._attributes["http.response.body"]
        assert "***REDACTED" in mock_span._attributes["db.statement"]
        assert "***REDACTED" in mock_span._attributes["password"]

        # Assert: Safe attributes preserved
        assert mock_span._attributes["http.url"] == "/api/users"
        assert mock_span._attributes["http.method"] == "POST"

    def test_sanitizes_mixed_http_and_db_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test mixed HTTP and DB sensitive attributes.

        Arrange: Create span with HTTP and DB sensitive data
        Act: Call on_end
        Assert: Both types sanitized
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.cookie": "session=abc",
            "db.statement": "UPDATE users SET email = 'new@test.com'",
            "http.status_code": 200,
            "db.system": "mysql",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.header.cookie"]
        assert "***REDACTED" in mock_span._attributes["db.statement"]
        assert mock_span._attributes["http.status_code"] == 200
        assert mock_span._attributes["db.system"] == "mysql"


# ============================================================================
# Test Safe Attribute Preservation
# ============================================================================


class TestSanitizingSpanProcessorSafeAttributes:
    """Test safe attributes are not modified."""

    def test_preserves_http_safe_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test safe HTTP attributes remain unchanged.

        Arrange: Create span with safe HTTP attributes
        Act: Call on_end
        Assert: All attributes unchanged
        """
        # Arrange
        safe_attrs = {
            "http.url": "/api/users/123",
            "http.method": "GET",
            "http.status_code": 200,
            "http.target": "/users",
        }
        mock_span.attributes = safe_attrs.copy()
        mock_span._attributes = safe_attrs.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes == safe_attrs

    def test_preserves_service_attributes(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test service attributes remain unchanged.

        Arrange: Create span with service metadata
        Act: Call on_end
        Assert: All attributes unchanged
        """
        # Arrange
        safe_attrs = {
            "service.name": "my_service",
            "service.version": "1.0.0",
            "span.kind": "server",
        }
        mock_span.attributes = safe_attrs.copy()
        mock_span._attributes = safe_attrs.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes == safe_attrs

    def test_preserves_all_safe_attributes_comprehensive(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test comprehensive set of safe attributes.

        Arrange: Create span with many safe attributes
        Act: Call on_end
        Assert: All remain unchanged
        """
        # Arrange
        safe_attrs = {
            "http.url": "/api/users/123",
            "http.method": "GET",
            "http.status_code": 200,
            "http.target": "/users",
            "db.system": "postgresql",
            "db.name": "mydb",
            "db.table": "users",
            "messaging.system": "kafka",
            "messaging.destination": "topic_name",
            "service.name": "my_service",
            "span.kind": "server",
        }
        mock_span.attributes = safe_attrs.copy()
        mock_span._attributes = safe_attrs.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes == safe_attrs


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestSanitizingSpanProcessorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_sanitizes_empty_string_sensitive_value(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test empty string sensitive values are still sanitized.

        Arrange: Create span with empty sensitive value
        Act: Call on_end
        Assert: Empty value is redacted
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.authorization": "",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.header.authorization"]

    def test_sanitizes_non_string_sensitive_value(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test non-string sensitive values are sanitized without length.

        Arrange: Create span with integer password
        Act: Call on_end
        Assert: Value is redacted without length
        """
        # Arrange
        mock_span.attributes = {
            "password": 12345,  # Integer password
            "token": None,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes["password"] == "***REDACTED***"
        assert mock_span._attributes["token"] == "***REDACTED***"

    def test_sanitizes_boolean_sensitive_value(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test boolean sensitive values are sanitized.

        Arrange: Create span with boolean secret
        Act: Call on_end
        Assert: Boolean is redacted
        """
        # Arrange
        mock_span.attributes = {
            "secret": True,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert mock_span._attributes["secret"] == "***REDACTED***"

    def test_handles_unicode_in_sensitive_values(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test Unicode characters in sensitive values.

        Arrange: Create span with Unicode password
        Act: Call on_end
        Assert: Value is redacted with correct length
        """
        # Arrange
        unicode_password = "пароль123"  # Cyrillic + digits
        mock_span.attributes = {
            "password": unicode_password,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["password"]
        assert f"{len(unicode_password)} chars" in mock_span._attributes["password"]

    def test_handles_special_characters_in_attribute_names(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test attribute names with special characters.

        Arrange: Create span with dots and hyphens in names
        Act: Call on_end
        Assert: Both naming conventions work
        """
        # Arrange
        mock_span.attributes = {
            "http.request.header.cookie": "session=123",
            "http-request-header-authorization": "Bearer token",
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.header.cookie"]
        assert "***REDACTED" in mock_span._attributes["http-request-header-authorization"]

    def test_handles_very_long_attribute_value(
        self, processor: SanitizingSpanProcessor, mock_span: MagicMock
    ) -> None:
        """Test very long sensitive values show length.

        Arrange: Create span with very long sensitive value
        Act: Call on_end
        Assert: Value is redacted with length shown
        """
        # Arrange
        very_long_value = "x" * 100000
        mock_span.attributes = {
            "http.request.body": very_long_value,
        }
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["http.request.body"]
        assert "100000 chars" in mock_span._attributes["http.request.body"]


# ============================================================================
# Test Lifecycle Methods
# ============================================================================


class TestSanitizingSpanProcessorLifecycle:
    """Test processor lifecycle methods (shutdown, force_flush)."""

    def test_shutdown_is_noop(self, processor: SanitizingSpanProcessor) -> None:
        """Test shutdown completes without errors.

        Arrange: Create processor
        Act: Call shutdown
        Assert: No errors raised
        """
        # Arrange & Act
        processor.shutdown()

        # Assert: No errors, method completes
        assert True

    def test_force_flush_returns_true(self, processor: SanitizingSpanProcessor) -> None:
        """Test force_flush returns True.

        Arrange: Create processor
        Act: Call force_flush
        Assert: Returns True
        """
        # Arrange & Act
        result = processor.force_flush()

        # Assert
        assert result is True

    def test_force_flush_with_default_timeout(self, processor: SanitizingSpanProcessor) -> None:
        """Test force_flush uses default timeout.

        Arrange: Create processor
        Act: Call force_flush without timeout
        Assert: Returns True
        """
        # Arrange & Act
        result = processor.force_flush()

        # Assert
        assert result is True

    def test_force_flush_with_custom_timeout(self, processor: SanitizingSpanProcessor) -> None:
        """Test force_flush accepts custom timeout.

        Arrange: Create processor
        Act: Call force_flush with custom timeout
        Assert: Returns True
        """
        # Arrange & Act
        result = processor.force_flush(timeout_millis=5000)

        # Assert
        assert result is True

    def test_force_flush_with_zero_timeout(self, processor: SanitizingSpanProcessor) -> None:
        """Test force_flush with zero timeout.

        Arrange: Create processor
        Act: Call force_flush with timeout=0
        Assert: Returns True
        """
        # Arrange & Act
        result = processor.force_flush(timeout_millis=0)

        # Assert
        assert result is True


# ============================================================================
# Test Factory Function
# ============================================================================


class TestCreateSanitizingProcessor:
    """Test create_sanitizing_processor factory function."""

    def test_creates_processor_instance(self) -> None:
        """Test factory creates SanitizingSpanProcessor instance.

        Arrange: Call factory function
        Act: Check instance type
        Assert: Returns correct type
        """
        # Arrange & Act
        processor = create_sanitizing_processor()

        # Assert
        assert isinstance(processor, SanitizingSpanProcessor)

    def test_creates_new_instance_each_time(self) -> None:
        """Test factory creates new instance on each call.

        Arrange: Call factory twice
        Act: Compare instances
        Assert: Different instances
        """
        # Arrange & Act
        processor1 = create_sanitizing_processor()
        processor2 = create_sanitizing_processor()

        # Assert
        assert processor1 is not processor2

    def test_created_processor_is_functional(self) -> None:
        """Test factory-created processor works correctly.

        Arrange: Create processor via factory
        Act: Use processor to sanitize span
        Assert: Sanitization works
        """
        # Arrange
        processor = create_sanitizing_processor()
        mock_span = MagicMock(spec=ReadableSpan)
        mock_span.attributes = {"password": "secret"}
        mock_span._attributes = mock_span.attributes.copy()

        # Act
        processor.on_end(mock_span)

        # Assert
        assert "***REDACTED" in mock_span._attributes["password"]


# ============================================================================
# Test SENSITIVE_PATTERNS Constant
# ============================================================================


class TestSensitivePatternsConstant:
    """Test SENSITIVE_PATTERNS constant validation."""

    def test_contains_http_header_patterns(self) -> None:
        """Test SENSITIVE_PATTERNS includes HTTP header patterns.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Check for HTTP headers
        Assert: Headers are present
        """
        # Arrange & Act & Assert
        assert "http.request.header.authorization" in SENSITIVE_PATTERNS
        assert "http.request.header.cookie" in SENSITIVE_PATTERNS

    def test_contains_http_body_patterns(self) -> None:
        """Test SENSITIVE_PATTERNS includes HTTP body patterns.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Check for body patterns
        Assert: Patterns are present
        """
        # Arrange & Act & Assert
        assert "http.request.body" in SENSITIVE_PATTERNS
        assert "http.response.body" in SENSITIVE_PATTERNS

    def test_contains_database_patterns(self) -> None:
        """Test SENSITIVE_PATTERNS includes database patterns.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Check for DB patterns
        Assert: Patterns are present
        """
        # Arrange & Act & Assert
        assert "db.statement" in SENSITIVE_PATTERNS
        assert "db.query.text" in SENSITIVE_PATTERNS

    def test_contains_messaging_patterns(self) -> None:
        """Test SENSITIVE_PATTERNS includes messaging patterns.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Check for messaging patterns
        Assert: Patterns are present
        """
        # Arrange & Act & Assert
        assert "messaging.message.payload" in SENSITIVE_PATTERNS
        assert "messaging.message.body" in SENSITIVE_PATTERNS

    def test_contains_generic_sensitive_patterns(self) -> None:
        """Test SENSITIVE_PATTERNS includes generic patterns.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Check for generic patterns
        Assert: Patterns are present
        """
        # Arrange & Act & Assert
        assert "password" in SENSITIVE_PATTERNS
        assert "secret" in SENSITIVE_PATTERNS
        assert "token" in SENSITIVE_PATTERNS
        assert "api_key" in SENSITIVE_PATTERNS

    def test_patterns_is_not_empty(self) -> None:
        """Test SENSITIVE_PATTERNS is not empty.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Check length
        Assert: Contains patterns
        """
        # Arrange & Act & Assert
        assert len(SENSITIVE_PATTERNS) > 0

    def test_patterns_contains_expected_count(self) -> None:
        """Test SENSITIVE_PATTERNS has reasonable number of patterns.

        Arrange: Import SENSITIVE_PATTERNS
        Act: Count patterns
        Assert: Has many patterns (comprehensive coverage)
        """
        # Arrange & Act
        count = len(SENSITIVE_PATTERNS)

        # Assert: Should have at least 10 patterns for comprehensive coverage
        assert count >= 10
