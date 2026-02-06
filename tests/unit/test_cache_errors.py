"""Unit tests for cache error types.

Tests the cache-specific error types used with Result.
"""


from src.infrastructure.cache.errors import (
    CacheCompressionError,
    CacheConnectionError,
    CacheDisabledError,
    CacheError,
    CacheInvalidDataError,
    CacheMiss,
    CacheSerializationError,
    CacheTimeoutError,
    cache_error_from_exception,
)


class TestCacheError:
    """Test suite for base CacheError."""

    def test_cache_error_basic(self) -> None:
        """Test basic CacheError creation."""
        error = CacheError(message="Test error", key="test:key")

        assert error.message == "Test error"
        assert error.key == "test:key"
        assert error.original_error is None

    def test_cache_error_with_exception(self) -> None:
        """Test CacheError with original exception."""
        original = ValueError("Original error")
        error = CacheError(
            message="Wrapper error",
            key="test:key",
            original_error=original,
        )

        assert error.message == "Wrapper error"
        assert error.key == "test:key"
        assert error.original_error == original

    def test_cache_error_str(self) -> None:
        """Test CacheError string representation."""
        error = CacheError(message="Test error", key="test:key")
        error_str = str(error)

        assert "Test error" in error_str
        assert "test:key" in error_str

    def test_cache_error_str_with_cause(self) -> None:
        """Test CacheError string with original error."""
        original = ValueError("Original error")
        error = CacheError(
            message="Test error",
            key="test:key",
            original_error=original,
        )
        error_str = str(error)

        assert "Test error" in error_str
        assert "ValueError" in error_str


class TestCacheMiss:
    """Test suite for CacheMiss error."""

    def test_cache_miss_creation(self) -> None:
        """Test CacheMiss creation."""
        error = CacheMiss(key="user:123")

        assert error.message == "Cache miss"
        assert error.key == "user:123"
        assert error.original_error is None

    def test_cache_miss_str(self) -> None:
        """Test CacheMiss string representation."""
        error = CacheMiss(key="user:123")
        error_str = str(error)

        assert "Cache miss" in error_str
        assert "user:123" in error_str


class TestCacheConnectionError:
    """Test suite for CacheConnectionError."""

    def test_connection_error_with_key(self) -> None:
        """Test connection error with cache key."""
        original = ConnectionError("Connection refused")
        error = CacheConnectionError(key="user:123", original_error=original)

        assert error.message == "Cache connection failed"
        assert error.key == "user:123"
        assert error.original_error == original

    def test_connection_error_without_key(self) -> None:
        """Test connection error without cache key."""
        original = ConnectionError("Connection refused")
        error = CacheConnectionError(key=None, original_error=original)

        assert error.message == "Cache connection failed"
        assert error.key is None

    def test_connection_error_str(self) -> None:
        """Test connection error string representation."""
        original = ConnectionError("Connection refused")
        error = CacheConnectionError(key="user:123", original_error=original)
        error_str = str(error)

        assert "Cache connection failed" in error_str
        assert "ConnectionError" in error_str


class TestCacheSerializationError:
    """Test suite for CacheSerializationError."""

    def test_serialization_error(self) -> None:
        """Test serialization error."""
        original = ValueError("Cannot serialize")
        error = CacheSerializationError(
            key="user:123",
            operation="serialize",
            original_error=original,
        )

        assert error.message == "Cache serialize failed"
        assert error.key == "user:123"
        assert error.original_error == original

    def test_deserialization_error(self) -> None:
        """Test deserialization error."""
        original = ValueError("Cannot deserialize")
        error = CacheSerializationError(
            key="user:123",
            operation="deserialize",
            original_error=original,
        )

        assert error.message == "Cache deserialize failed"
        assert error.key == "user:123"


class TestCacheCompressionError:
    """Test suite for CacheCompressionError."""

    def test_compression_error(self) -> None:
        """Test compression error."""
        original = Exception("Compression failed")
        error = CacheCompressionError(
            key="user:123",
            operation="compress",
            original_error=original,
        )

        assert error.message == "Cache compress failed"
        assert error.key == "user:123"
        assert error.original_error == original

    def test_decompression_error(self) -> None:
        """Test decompression error."""
        original = Exception("Decompression failed")
        error = CacheCompressionError(
            key="user:123",
            operation="decompress",
            original_error=original,
        )

        assert error.message == "Cache decompress failed"


class TestCacheTimeoutError:
    """Test suite for CacheTimeoutError."""

    def test_timeout_error_with_key(self) -> None:
        """Test timeout error with cache key."""
        error = CacheTimeoutError(key="user:123", timeout_ms=5000.0)

        assert "timed out after 5000.0ms" in error.message
        assert error.key == "user:123"

    def test_timeout_error_without_key(self) -> None:
        """Test timeout error without cache key."""
        error = CacheTimeoutError(key=None, timeout_ms=5000.0)

        assert "timed out" in error.message
        assert error.key is None


class TestCacheDisabledError:
    """Test suite for CacheDisabledError."""

    def test_disabled_error(self) -> None:
        """Test cache disabled error."""
        error = CacheDisabledError()

        assert "disabled" in error.message.lower()
        assert error.key is None
        assert error.original_error is None


class TestCacheInvalidDataError:
    """Test suite for CacheInvalidDataError."""

    def test_invalid_data_error(self) -> None:
        """Test invalid data error."""
        error = CacheInvalidDataError(
            key="user:123",
            reason="Data format mismatch",
        )

        assert "Invalid cached data" in error.message
        assert "Data format mismatch" in error.message
        assert error.key == "user:123"


class TestCacheErrorFromException:
    """Test suite for cache_error_from_exception helper."""

    def test_connection_error_conversion(self) -> None:
        """Test conversion of ConnectionError."""
        exc = ConnectionError("Connection refused")
        error = cache_error_from_exception(exc, key="user:123")

        assert isinstance(error, CacheConnectionError)
        assert error.key == "user:123"
        assert error.original_error == exc

    def test_timeout_error_conversion(self) -> None:
        """Test conversion of TimeoutError."""

        exc = TimeoutError()
        error = cache_error_from_exception(exc, key="user:123")

        assert isinstance(error, CacheTimeoutError)
        assert error.key == "user:123"

    def test_value_error_conversion(self) -> None:
        """Test conversion of ValueError to serialization error."""
        exc = ValueError("Invalid JSON")
        error = cache_error_from_exception(exc, key="user:123", operation="deserialize")

        assert isinstance(error, CacheSerializationError)
        assert error.key == "user:123"
        assert "deserialize" in error.message

    def test_type_error_conversion(self) -> None:
        """Test conversion of TypeError to serialization error."""
        exc = TypeError("Cannot serialize type")
        error = cache_error_from_exception(exc, key="user:123", operation="serialize")

        assert isinstance(error, CacheSerializationError)
        assert "serialize" in error.message

    def test_generic_exception_conversion(self) -> None:
        """Test conversion of generic exception."""
        exc = Exception("Something went wrong")
        error = cache_error_from_exception(exc, key="user:123", operation="get")

        assert isinstance(error, CacheError)
        assert error.key == "user:123"
        assert error.original_error == exc
        assert "get" in error.message

    def test_exception_conversion_without_key(self) -> None:
        """Test conversion without cache key."""
        exc = ConnectionError("Connection refused")
        error = cache_error_from_exception(exc)

        assert isinstance(error, CacheConnectionError)
        assert error.key is None
