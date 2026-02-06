"""Domain constants for business rules and limits.

This module contains configurable constants used across the domain layer.
These values define business constraints and can be adjusted based on
operational requirements.
"""


class UserLimits:
    """User-related business constraints."""

    # Maximum number of users that can be created in a single batch operation
    # Prevents memory issues and ensures reasonable transaction size
    MAX_BATCH_SIZE = 100

    # Default number of users returned in list operations
    # Balances between data transfer and user experience
    LIST_DEFAULT_LIMIT = 100

    # Maximum number of users that can be requested in a single list operation
    # Prevents excessive data transfer and server load
    LIST_MAX_LIMIT = 100

    # Minimum number of users in list operations (must be positive)
    LIST_MIN_LIMIT = 1


class PaginationDefaults:
    """Default pagination settings for cursor-based pagination."""

    # Default page size for cursor pagination
    # Optimized for most common use cases
    DEFAULT_PAGE_SIZE = 50

    # Maximum page size allowed for cursor pagination
    # Prevents excessive memory usage and response times
    MAX_PAGE_SIZE = 100

    # Minimum page size (must be positive)
    MIN_PAGE_SIZE = 1


class CacheDefaults:
    """Cache-related constants."""

    # Default TTL for cached items (in seconds)
    DEFAULT_TTL = 300  # 5 minutes

    # Minimum TTL (in seconds)
    MIN_TTL = 60  # 1 minute

    # Maximum TTL (in seconds)
    MAX_TTL = 86400  # 24 hours


class RateLimitDefaults:
    """Rate limiting constants."""

    # Default rate limit per minute for API endpoints
    DEFAULT_PER_MINUTE = 60

    # Minimum rate limit
    MIN_PER_MINUTE = 1

    # Maximum rate limit
    MAX_PER_MINUTE = 10000


class ValidationLimits:
    """Input validation constraints."""

    # Maximum email length
    MAX_EMAIL_LENGTH = 255

    # Maximum username length
    MAX_USERNAME_LENGTH = 100

    # Maximum full name length
    MAX_FULL_NAME_LENGTH = 255

    # Minimum password length (if password authentication added)
    MIN_PASSWORD_LENGTH = 8


# Export commonly used constants for convenience
__all__ = [
    "UserLimits",
    "PaginationDefaults",
    "CacheDefaults",
    "RateLimitDefaults",
    "ValidationLimits",
]
