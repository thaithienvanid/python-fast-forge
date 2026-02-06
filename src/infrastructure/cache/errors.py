"""Cache-specific error types for Result-based error handling.

This module defines error types for cache operations, providing more
context than simple None returns or generic exceptions.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CacheError:
    """Base class for cache errors."""

    message: str
    key: str | None = None
    original_error: Exception | None = None

    def __str__(self) -> str:
        """String representation of error."""
        parts = [self.message]
        if self.key:
            parts.append(f"key={self.key}")
        if self.original_error:
            parts.append(f"cause={type(self.original_error).__name__}: {self.original_error}")
        return " | ".join(parts)


@dataclass(frozen=True)
class CacheMiss(CacheError):
    """Cache miss - key not found in cache.

    This is not necessarily an error, but explicitly indicates
    the value was not found in cache and needs to be fetched
    from the primary source.
    """

    def __init__(self, key: str) -> None:
        """Initialize cache miss error.

        Args:
            key: Cache key that was not found
        """
        object.__setattr__(self, "message", "Cache miss")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "original_error", None)


@dataclass(frozen=True)
class CacheConnectionError(CacheError):
    """Cache connection failed - Redis unavailable."""

    def __init__(self, key: str | None, original_error: Exception) -> None:
        """Initialize connection error.

        Args:
            key: Cache key (if applicable)
            original_error: Original exception from connection attempt
        """
        object.__setattr__(self, "message", "Cache connection failed")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "original_error", original_error)


@dataclass(frozen=True)
class CacheSerializationError(CacheError):
    """Failed to serialize/deserialize cache value."""

    def __init__(
        self,
        key: str,
        operation: str,
        original_error: Exception,
    ) -> None:
        """Initialize serialization error.

        Args:
            key: Cache key
            operation: Operation that failed ("serialize" or "deserialize")
            original_error: Original serialization exception
        """
        object.__setattr__(self, "message", f"Cache {operation} failed")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "original_error", original_error)


@dataclass(frozen=True)
class CacheCompressionError(CacheError):
    """Failed to compress/decompress cache value."""

    def __init__(
        self,
        key: str,
        operation: str,
        original_error: Exception,
    ) -> None:
        """Initialize compression error.

        Args:
            key: Cache key
            operation: Operation that failed ("compress" or "decompress")
            original_error: Original compression exception
        """
        object.__setattr__(self, "message", f"Cache {operation} failed")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "original_error", original_error)


@dataclass(frozen=True)
class CacheTimeoutError(CacheError):
    """Cache operation timed out."""

    def __init__(self, key: str | None, timeout_ms: float) -> None:
        """Initialize timeout error.

        Args:
            key: Cache key (if applicable)
            timeout_ms: Timeout value in milliseconds
        """
        object.__setattr__(
            self,
            "message",
            f"Cache operation timed out after {timeout_ms}ms",
        )
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "original_error", None)


@dataclass(frozen=True)
class CacheDisabledError(CacheError):
    """Cache is disabled in configuration."""

    def __init__(self) -> None:
        """Initialize disabled error."""
        object.__setattr__(
            self,
            "message",
            "Cache is disabled (CACHE_ENABLED=false)",
        )
        object.__setattr__(self, "key", None)
        object.__setattr__(self, "original_error", None)


@dataclass(frozen=True)
class CacheInvalidDataError(CacheError):
    """Cached data is invalid or corrupted."""

    def __init__(self, key: str, reason: str) -> None:
        """Initialize invalid data error.

        Args:
            key: Cache key
            reason: Why the data is invalid
        """
        object.__setattr__(self, "message", f"Invalid cached data: {reason}")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "original_error", None)


def cache_error_from_exception(
    exc: Exception,
    key: str | None = None,
    operation: str = "unknown",
) -> CacheError:
    """Convert an exception to appropriate CacheError type.

    Args:
        exc: Exception that occurred
        key: Cache key (if applicable)
        operation: Operation being performed

    Returns:
        Appropriate CacheError subclass

    Example:
        >>> try:
        ...     await redis.get("key")
        ... except ConnectionError as e:
        ...     error = cache_error_from_exception(e, key="key")
        ...     return err(error)
    """
    import asyncio  # noqa: PLC0415

    if isinstance(exc, (ConnectionError, OSError)):
        return CacheConnectionError(key, exc)
    if isinstance(exc, asyncio.TimeoutError):
        return CacheTimeoutError(key, 0.0)
    if isinstance(exc, (ValueError, TypeError)):
        return CacheSerializationError(key or "unknown", operation, exc)

    # Generic error for unknown exception types
    return CacheError(
        message=f"Cache {operation} failed",
        key=key,
        original_error=exc,
    )
