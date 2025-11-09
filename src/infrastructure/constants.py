"""Application-wide constants and limits."""


class SecurityLimits:
    """Security-related constants and limits."""

    # Cursor pagination limits (to prevent DoS attacks)
    MAX_CURSOR_LENGTH = 1024  # Maximum encoded cursor length in characters
    MAX_DECODED_SIZE = 768  # Maximum decoded cursor size in bytes

    # Rate limiting
    MIN_RATE_LIMIT = 1  # Minimum requests per minute
    MAX_RATE_LIMIT = 10000  # Maximum requests per minute

    # Password requirements
    MIN_PASSWORD_LENGTH = 8  # Minimum password length
    MAX_PASSWORD_LENGTH = 128  # Maximum password length

    # Username requirements
    MIN_USERNAME_LENGTH = 3  # Minimum username length
    MAX_USERNAME_LENGTH = 100  # Maximum username length


class PaginationDefaults:
    """Default values for pagination."""

    DEFAULT_PAGE_SIZE = 20  # Default number of items per page
    MAX_PAGE_SIZE = 100  # Maximum number of items per page
    MAX_SKIP = 10000  # Maximum offset for pagination


class CacheDefaults:
    """Default cache settings."""

    DEFAULT_TTL = 300  # Default cache TTL in seconds (5 minutes)
    DEFAULT_MAX_CONNECTIONS = 10  # Default Redis connection pool size


# Allowed fields for cursor pagination
CURSOR_ALLOWED_FIELDS = {"value", "sort_value"}
