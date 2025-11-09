"""Shared sanitization utilities for logs and telemetry.

This module provides common sanitization logic used by both:
- Logging: sanitize_sensitive_data() in structlog processor pipeline
- Telemetry: SanitizingSpanProcessor for OpenTelemetry span attributes

The goal is to prevent sensitive data (passwords, tokens, PII) from being
exposed in logs or distributed traces.
"""

from typing import Any


# Sensitive field patterns that should be redacted
# Used by both logging and telemetry sanitization
SENSITIVE_PATTERNS = {
    # Authentication & Authorization
    "password",
    "passwd",
    "pwd",
    "secret",
    "secret_key",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "bearer",
    "authorization",
    "auth",
    "credentials",
    # API Signatures
    "signature",
    "x-api-signature",
    "x-api-key",
    # Personal Information
    "ssn",
    "social_security",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
    # Database
    "connection_string",
    "database_url",
    "db_password",
    # HTTP Headers (for telemetry span attributes)
    "http.request.header.authorization",
    "http.request.header.cookie",
    "http.request.header.set-cookie",
    "http.request.header.proxy-authorization",
    "http.request.header.x-api-key",
    "http.request.body",
    "http.request.body.content",
    "http.response.header.set-cookie",
    "http.response.body",
    "http.response.body.content",
    # Database (for telemetry span attributes)
    "db.statement",  # SQL queries may contain PII in WHERE clauses
    "db.query.text",
    "db.query.parameters",
    # Messaging (for telemetry span attributes)
    "messaging.message.payload",
    "messaging.message.body",
    "messaging.header.authorization",
    # RPC (for telemetry span attributes)
    "rpc.request.metadata",
    "rpc.response.metadata",
}


def is_sensitive_key(key: str, patterns: set[str] | None = None) -> bool:
    """Check if a key matches any sensitive pattern.

    Args:
        key: The key to check (case-insensitive, normalized)
        patterns: Optional custom patterns (defaults to SENSITIVE_PATTERNS)

    Returns:
        True if key matches any sensitive pattern, False otherwise

    Example:
        >>> is_sensitive_key("password")
        True
        >>> is_sensitive_key("http.request.header.authorization")
        True
        >>> is_sensitive_key("http.url")
        False
    """
    if patterns is None:
        patterns = SENSITIVE_PATTERNS

    # Normalize key: lowercase, replace separators with underscores
    normalized_key = key.lower().replace("-", "_").replace(".", "_").replace(" ", "_")

    # Check if any pattern matches
    for pattern in patterns:
        normalized_pattern = pattern.replace(".", "_").replace("-", "_")
        if normalized_pattern in normalized_key:
            return True

    return False


def sanitize_value(
    key: str, value: Any, patterns: set[str] | None = None, show_length: bool = False
) -> Any:
    """Sanitize a value if its key is sensitive.

    Args:
        key: The key name
        value: The value to potentially sanitize
        patterns: Optional custom patterns (defaults to SENSITIVE_PATTERNS)
        show_length: Whether to show the length of sanitized strings (useful for debugging)

    Returns:
        Sanitized value if key is sensitive, original value otherwise

    Example:
        >>> sanitize_value("password", "secret123")
        '***REDACTED***'
        >>> sanitize_value("username", "john")
        'john'
        >>> sanitize_value("http.request.body", "data", show_length=True)
        '***REDACTED(4 chars)***'
    """
    if not is_sensitive_key(key, patterns):
        return value

    # Redact sensitive values
    if isinstance(value, str) and len(value) > 0 and show_length:
        # Show length to help with debugging (useful for telemetry spans)
        return f"***REDACTED({len(value)} chars)***"
    # Simple redaction (cleaner for logs)
    return "***REDACTED***"


def sanitize_dict(
    data: dict[str, Any],
    patterns: set[str] | None = None,
    recursive: bool = True,
    show_length: bool = False,
) -> dict[str, Any]:
    """Recursively sanitize a dictionary.

    Args:
        data: Dictionary to sanitize
        patterns: Optional custom patterns (defaults to SENSITIVE_PATTERNS)
        recursive: Whether to recursively sanitize nested dicts/lists
        show_length: Whether to show the length of sanitized strings

    Returns:
        New dictionary with sensitive values redacted

    Example:
        >>> sanitize_dict({"password": "secret", "username": "john"})
        {'password': '***REDACTED***', 'username': 'john'}
        >>> sanitize_dict({"user": {"password": "secret", "id": 123}})
        {'user': {'password': '***REDACTED***', 'id': 123}}
    """
    sanitized = {}

    for key, value in data.items():
        # Check if key is sensitive first - if so, redact entire value
        if is_sensitive_key(key, patterns):
            sanitized[key] = sanitize_value(key, value, patterns, show_length)
        elif recursive and isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_dict(value, patterns, recursive, show_length)
        elif recursive and isinstance(value, list):
            # Recursively sanitize lists (check each dict item)
            sanitized[key] = [
                sanitize_dict(item, patterns, recursive, show_length)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            # Non-sensitive scalar value - keep as-is
            sanitized[key] = value

    return sanitized
