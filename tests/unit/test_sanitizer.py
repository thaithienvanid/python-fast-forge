"""Tests for shared sanitization utility.

Test Organization:
- TestIsSensitiveKey: Key sensitivity detection
- TestIsSensitiveKeyPatterns: Pattern matching behavior
- TestSanitizeValue: Value sanitization
- TestSanitizeDict: Dictionary sanitization
- TestSanitizeDictRecursive: Recursive sanitization
- TestSensitivePatterns: Pattern constant validation
- TestEdgeCases: Edge cases and boundary conditions
"""

from src.utils.sanitizer import (
    SENSITIVE_PATTERNS,
    is_sensitive_key,
    sanitize_dict,
    sanitize_value,
)


# ============================================================================
# Is Sensitive Key Tests
# ============================================================================


class TestIsSensitiveKey:
    """Test is_sensitive_key function."""

    def test_detects_password_key(self) -> None:
        """Test password key is detected as sensitive.

        Arrange: Key "password"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "password"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_api_key(self) -> None:
        """Test api_key is detected as sensitive.

        Arrange: Key "api_key"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "api_key"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_token_key(self) -> None:
        """Test token key is detected as sensitive.

        Arrange: Key "token"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "token"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_secret_key(self) -> None:
        """Test secret key is detected as sensitive.

        Arrange: Key "secret"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "secret"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_http_authorization_header(self) -> None:
        """Test HTTP authorization header is detected.

        Arrange: Key "http.request.header.authorization"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "http.request.header.authorization"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_db_statement_key(self) -> None:
        """Test database statement key is detected.

        Arrange: Key "db.statement"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "db.statement"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_non_sensitive_username_key(self) -> None:
        """Test non-sensitive username key.

        Arrange: Key "username"
        Act: Call is_sensitive_key
        Assert: Returns False
        """
        # Arrange
        key = "username"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is False

    def test_non_sensitive_http_url(self) -> None:
        """Test non-sensitive HTTP URL key.

        Arrange: Key "http.url"
        Act: Call is_sensitive_key
        Assert: Returns False
        """
        # Arrange
        key = "http.url"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is False

    def test_non_sensitive_db_system(self) -> None:
        """Test non-sensitive database system key.

        Arrange: Key "db.system"
        Act: Call is_sensitive_key
        Assert: Returns False
        """
        # Arrange
        key = "db.system"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is False


# ============================================================================
# Sensitive Key Pattern Tests
# ============================================================================


class TestIsSensitiveKeyPatterns:
    """Test pattern matching behavior."""

    def test_case_insensitive_uppercase(self) -> None:
        """Test case-insensitive detection with uppercase.

        Arrange: Key "PASSWORD" (all uppercase)
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "PASSWORD"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_case_insensitive_mixed_case(self) -> None:
        """Test case-insensitive detection with mixed case.

        Arrange: Key "PaSsWoRd" (mixed case)
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "PaSsWoRd"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_key_with_hyphens(self) -> None:
        """Test detection with hyphens.

        Arrange: Key "x-api-key" (with hyphens)
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "x-api-key"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_key_with_dots(self) -> None:
        """Test detection with dots.

        Arrange: Key "http.request.header.cookie"
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "http.request.header.cookie"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_detects_key_with_underscores(self) -> None:
        """Test detection with underscores.

        Arrange: Key "api_key" (with underscores)
        Act: Call is_sensitive_key
        Assert: Returns True
        """
        # Arrange
        key = "api_key"

        # Act
        result = is_sensitive_key(key)

        # Assert
        assert result is True

    def test_custom_patterns_matches(self) -> None:
        """Test custom patterns matching.

        Arrange: Custom patterns set, key in patterns
        Act: Call is_sensitive_key with custom patterns
        Assert: Returns True
        """
        # Arrange
        custom_patterns = {"custom_secret", "internal_key"}
        key = "custom_secret"

        # Act
        result = is_sensitive_key(key, custom_patterns)

        # Assert
        assert result is True

    def test_custom_patterns_default_not_matched(self) -> None:
        """Test default patterns not matched with custom patterns.

        Arrange: Custom patterns set, key is default pattern
        Act: Call is_sensitive_key with custom patterns
        Assert: Returns False (default patterns not used)
        """
        # Arrange
        custom_patterns = {"custom_secret"}
        key = "password"

        # Act
        result = is_sensitive_key(key, custom_patterns)

        # Assert
        assert result is False


# ============================================================================
# Sanitize Value Tests
# ============================================================================


class TestSanitizeValue:
    """Test sanitize_value function."""

    def test_sanitizes_sensitive_string(self) -> None:
        """Test sanitizing sensitive string value.

        Arrange: Sensitive key and string value
        Act: Call sanitize_value
        Assert: Value is redacted
        """
        # Arrange
        key = "password"
        value = "secret123"

        # Act
        result = sanitize_value(key, value)

        # Assert
        assert result == "***REDACTED***"

    def test_sanitizes_with_length_shown(self) -> None:
        """Test sanitizing with length display.

        Arrange: Sensitive key and string value, show_length=True
        Act: Call sanitize_value
        Assert: Value is redacted with length
        """
        # Arrange
        key = "password"
        value = "secret123"

        # Act
        result = sanitize_value(key, value, show_length=True)

        # Assert
        assert "***REDACTED" in result
        assert "9 chars" in result

    def test_sanitizes_empty_string(self) -> None:
        """Test sanitizing empty string.

        Arrange: Sensitive key and empty string
        Act: Call sanitize_value
        Assert: Value is redacted
        """
        # Arrange
        key = "password"
        value = ""

        # Act
        result = sanitize_value(key, value)

        # Assert
        assert result == "***REDACTED***"

    def test_sanitizes_non_string_value(self) -> None:
        """Test sanitizing non-string value.

        Arrange: Sensitive key and integer value
        Act: Call sanitize_value
        Assert: Value is redacted
        """
        # Arrange
        key = "password"
        value = 12345

        # Act
        result = sanitize_value(key, value)

        # Assert
        assert result == "***REDACTED***"

    def test_sanitizes_none_value(self) -> None:
        """Test sanitizing None value.

        Arrange: Sensitive key and None value
        Act: Call sanitize_value
        Assert: Value is redacted
        """
        # Arrange
        key = "token"
        value = None

        # Act
        result = sanitize_value(key, value)

        # Assert
        assert result == "***REDACTED***"

    def test_preserves_non_sensitive_string(self) -> None:
        """Test non-sensitive string is preserved.

        Arrange: Non-sensitive key and string value
        Act: Call sanitize_value
        Assert: Original value is returned
        """
        # Arrange
        key = "username"
        value = "john_doe"

        # Act
        result = sanitize_value(key, value)

        # Assert
        assert result == "john_doe"

    def test_preserves_non_sensitive_number(self) -> None:
        """Test non-sensitive number is preserved.

        Arrange: Non-sensitive key and number value
        Act: Call sanitize_value
        Assert: Original value is returned
        """
        # Arrange
        key = "age"
        value = 25

        # Act
        result = sanitize_value(key, value)

        # Assert
        assert result == 25

    def test_custom_patterns_redacts(self) -> None:
        """Test custom patterns cause redaction.

        Arrange: Custom patterns set, key in patterns
        Act: Call sanitize_value with custom patterns
        Assert: Value is redacted
        """
        # Arrange
        custom_patterns = {"my_secret"}
        key = "my_secret"
        value = "sensitive_value"

        # Act
        result = sanitize_value(key, value, custom_patterns)

        # Assert
        assert "***REDACTED" in result

    def test_custom_patterns_default_not_redacted(self) -> None:
        """Test default patterns not redacted with custom patterns.

        Arrange: Custom patterns set, key is default pattern
        Act: Call sanitize_value with custom patterns
        Assert: Original value is returned
        """
        # Arrange
        custom_patterns = {"my_secret"}
        key = "password"
        value = "should_not_redact"

        # Act
        result = sanitize_value(key, value, custom_patterns)

        # Assert
        assert result == "should_not_redact"


# ============================================================================
# Sanitize Dict Tests
# ============================================================================


class TestSanitizeDict:
    """Test sanitize_dict function."""

    def test_sanitizes_simple_dict(self) -> None:
        """Test sanitizing simple dictionary.

        Arrange: Dict with sensitive and non-sensitive keys
        Act: Call sanitize_dict
        Assert: Sensitive values redacted, others preserved
        """
        # Arrange
        data = {"password": "secret", "username": "john"}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["username"] == "john"

    def test_sanitizes_multiple_sensitive_keys(self) -> None:
        """Test sanitizing multiple sensitive keys.

        Arrange: Dict with multiple sensitive keys
        Act: Call sanitize_dict
        Assert: All sensitive values redacted
        """
        # Arrange
        data = {"password": "pwd123", "api_key": "key456", "token": "tok789"}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["password"]
        assert "***REDACTED" in result["api_key"]
        assert "***REDACTED" in result["token"]

    def test_preserves_all_non_sensitive_keys(self) -> None:
        """Test all non-sensitive keys preserved.

        Arrange: Dict with only non-sensitive keys
        Act: Call sanitize_dict
        Assert: All values preserved
        """
        # Arrange
        data = {"username": "john", "age": 30, "active": True}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert result["username"] == "john"
        assert result["age"] == 30
        assert result["active"] is True

    def test_empty_dict(self) -> None:
        """Test sanitizing empty dictionary.

        Arrange: Empty dict
        Act: Call sanitize_dict
        Assert: Empty dict returned
        """
        # Arrange
        data = {}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert result == {}


# ============================================================================
# Recursive Sanitization Tests
# ============================================================================


class TestSanitizeDictRecursive:
    """Test recursive dictionary sanitization."""

    def test_sanitizes_nested_dict(self) -> None:
        """Test sanitizing nested dictionary.

        Arrange: Dict with nested dict containing sensitive key
        Act: Call sanitize_dict
        Assert: Nested sensitive value redacted
        """
        # Arrange
        data = {
            "user": {"password": "secret", "username": "john"},
            "public_data": "visible",
        }

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["user"]["password"]
        assert result["user"]["username"] == "john"
        assert result["public_data"] == "visible"

    def test_sanitizes_list_of_dicts(self) -> None:
        """Test sanitizing list of dictionaries.

        Arrange: Dict with list of dicts
        Act: Call sanitize_dict
        Assert: All dict items in list sanitized
        """
        # Arrange
        data = {
            "users": [
                {"password": "secret1", "username": "user1"},
                {"password": "secret2", "username": "user2"},
            ]
        }

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["users"][0]["password"]
        assert "***REDACTED" in result["users"][1]["password"]
        assert result["users"][0]["username"] == "user1"
        assert result["users"][1]["username"] == "user2"

    def test_sanitizes_deeply_nested_structure(self) -> None:
        """Test sanitizing deeply nested structure.

        Arrange: Dict with 3+ levels of nesting
        Act: Call sanitize_dict
        Assert: Sensitive values at all levels redacted
        """
        # Arrange
        data = {
            "level1": {
                "level2": {
                    "level3": {"password": "secret", "id": 123},
                    "public": "data",
                },
                "token": "abc123",
            }
        }

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["level1"]["level2"]["level3"]["password"]
        assert result["level1"]["level2"]["level3"]["id"] == 123
        assert result["level1"]["level2"]["public"] == "data"
        assert "***REDACTED" in result["level1"]["token"]

    def test_non_recursive_mode(self) -> None:
        """Test non-recursive sanitization.

        Arrange: Nested dict with sensitive keys, recursive=False
        Act: Call sanitize_dict
        Assert: Only top-level sanitized
        """
        # Arrange
        data = {
            "password": "secret",
            "nested": {"password": "also_secret", "username": "john"},
        }

        # Act
        result = sanitize_dict(data, recursive=False)

        # Assert
        assert "***REDACTED" in result["password"]
        assert isinstance(result["nested"], dict)
        # Nested dict not sanitized - still has password
        assert result["nested"]["password"] == "also_secret"

    def test_list_of_primitives_preserved(self) -> None:
        """Test list of primitives is preserved.

        Arrange: Dict with lists of non-dict values
        Act: Call sanitize_dict
        Assert: Lists preserved as-is
        """
        # Arrange
        data = {"numbers": [1, 2, 3], "strings": ["a", "b", "c"]}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert result["numbers"] == [1, 2, 3]
        assert result["strings"] == ["a", "b", "c"]

    def test_mixed_types_in_dict(self) -> None:
        """Test mixed types in dictionary.

        Arrange: Dict with various value types
        Act: Call sanitize_dict
        Assert: Each type handled correctly
        """
        # Arrange
        data = {
            "password": "secret",
            "count": 42,
            "active": True,
            "tags": ["tag1", "tag2"],
            "config": {"api_key": "key123", "timeout": 30},
        }

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["count"] == 42
        assert result["active"] is True
        assert result["tags"] == ["tag1", "tag2"]
        assert "***REDACTED" in result["config"]["api_key"]
        assert result["config"]["timeout"] == 30


# ============================================================================
# Sensitive Patterns Tests
# ============================================================================


class TestSensitivePatterns:
    """Test SENSITIVE_PATTERNS constant."""

    def test_contains_password_patterns(self) -> None:
        """Test contains password-related patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for password patterns
        Assert: All password patterns present
        """
        # Arrange & Act & Assert
        assert "password" in SENSITIVE_PATTERNS
        assert "passwd" in SENSITIVE_PATTERNS
        assert "pwd" in SENSITIVE_PATTERNS

    def test_contains_token_patterns(self) -> None:
        """Test contains token-related patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for token patterns
        Assert: All token patterns present
        """
        # Arrange & Act & Assert
        assert "token" in SENSITIVE_PATTERNS
        assert "access_token" in SENSITIVE_PATTERNS
        assert "refresh_token" in SENSITIVE_PATTERNS

    def test_contains_api_key_patterns(self) -> None:
        """Test contains API key patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for API key patterns
        Assert: All API key patterns present
        """
        # Arrange & Act & Assert
        assert "api_key" in SENSITIVE_PATTERNS
        assert "apikey" in SENSITIVE_PATTERNS
        assert "x-api-key" in SENSITIVE_PATTERNS

    def test_contains_secret_patterns(self) -> None:
        """Test contains secret patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for secret patterns
        Assert: All secret patterns present
        """
        # Arrange & Act & Assert
        assert "secret" in SENSITIVE_PATTERNS
        assert "secret_key" in SENSITIVE_PATTERNS

    def test_contains_http_header_patterns(self) -> None:
        """Test contains HTTP header patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for HTTP header patterns
        Assert: All HTTP header patterns present
        """
        # Arrange & Act & Assert
        assert "http.request.header.authorization" in SENSITIVE_PATTERNS
        assert "http.request.header.cookie" in SENSITIVE_PATTERNS
        assert "http.request.body" in SENSITIVE_PATTERNS

    def test_contains_database_patterns(self) -> None:
        """Test contains database patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for database patterns
        Assert: All database patterns present
        """
        # Arrange & Act & Assert
        assert "db.statement" in SENSITIVE_PATTERNS
        assert "db_password" in SENSITIVE_PATTERNS
        assert "database_url" in SENSITIVE_PATTERNS

    def test_contains_messaging_patterns(self) -> None:
        """Test contains messaging patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for messaging patterns
        Assert: All messaging patterns present
        """
        # Arrange & Act & Assert
        assert "messaging.message.payload" in SENSITIVE_PATTERNS

    def test_contains_pii_patterns(self) -> None:
        """Test contains PII patterns.

        Arrange: SENSITIVE_PATTERNS constant
        Act: Check for PII patterns
        Assert: All PII patterns present
        """
        # Arrange & Act & Assert
        assert "ssn" in SENSITIVE_PATTERNS
        assert "credit_card" in SENSITIVE_PATTERNS
        assert "cvv" in SENSITIVE_PATTERNS


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_values(self) -> None:
        """Test handling Unicode values.

        Arrange: Dict with Unicode sensitive and non-sensitive values
        Act: Call sanitize_dict
        Assert: Sensitive Unicode redacted, non-sensitive preserved
        """
        # Arrange
        data = {"password": "пароль123", "username": "用户"}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["username"] == "用户"

    def test_special_characters_in_values(self) -> None:
        """Test special characters in values.

        Arrange: Dict with special characters
        Act: Call sanitize_dict
        Assert: Sensitive values with special chars redacted
        """
        # Arrange
        data = {"token": "abc!@#$%^&*()_+-=[]{}|;:,.<>?", "name": "Test & Co."}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["token"]
        assert result["name"] == "Test & Co."

    def test_very_long_string_with_length(self) -> None:
        """Test very long string with length shown.

        Arrange: Very long sensitive string, show_length=True
        Act: Call sanitize_value
        Assert: Length is shown in redaction
        """
        # Arrange
        key = "password"
        value = "x" * 10000

        # Act
        result = sanitize_value(key, value, show_length=True)

        # Assert
        assert "***REDACTED" in result
        assert "10000 chars" in result

    def test_null_bytes_in_string(self) -> None:
        """Test null bytes in string.

        Arrange: Dict with null bytes in values
        Act: Call sanitize_dict
        Assert: Sensitive values redacted, non-sensitive preserved
        """
        # Arrange
        data = {"password": "secret\x00123", "name": "john\x00doe"}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["password"]
        assert result["name"] == "john\x00doe"

    def test_empty_string_with_length_shown(self) -> None:
        """Test empty string does not show length.

        Arrange: Empty sensitive string, show_length=True
        Act: Call sanitize_value
        Assert: Simple redaction (no length for empty string)
        """
        # Arrange
        key = "password"
        value = ""

        # Act
        result = sanitize_value(key, value, show_length=True)

        # Assert
        assert result == "***REDACTED***"

    def test_whitespace_only_string(self) -> None:
        """Test whitespace-only string.

        Arrange: Sensitive key with whitespace-only value
        Act: Call sanitize_value
        Assert: Value is redacted
        """
        # Arrange
        key = "password"
        value = "   "

        # Act
        result = sanitize_value(key, value, show_length=True)

        # Assert
        assert "***REDACTED" in result
        assert "3 chars" in result

    def test_nested_empty_dicts(self) -> None:
        """Test nested empty dictionaries.

        Arrange: Dict with nested empty dicts
        Act: Call sanitize_dict
        Assert: Structure preserved
        """
        # Arrange
        data = {"level1": {"level2": {}, "password": "secret"}}

        # Act
        result = sanitize_dict(data)

        # Assert
        assert result["level1"]["level2"] == {}
        assert "***REDACTED" in result["level1"]["password"]

    def test_mixed_list_with_dicts_and_primitives(self) -> None:
        """Test list with mixed dicts and primitives.

        Arrange: Dict with list containing dicts and primitives
        Act: Call sanitize_dict
        Assert: Dicts sanitized, primitives preserved
        """
        # Arrange
        data = {
            "items": [
                {"password": "secret1"},
                "string_value",
                42,
                {"token": "tok123"},
            ]
        }

        # Act
        result = sanitize_dict(data)

        # Assert
        assert "***REDACTED" in result["items"][0]["password"]
        assert result["items"][1] == "string_value"
        assert result["items"][2] == 42
        assert "***REDACTED" in result["items"][3]["token"]
