"""Tests for Redis cache implementation.

Test Organization:
- TestCacheMetricsDefaults: CacheMetrics initialization and defaults
- TestCacheMetricsHitRate: Hit rate calculation logic
- TestCacheMetricsToDict: Dictionary conversion
- TestRedisCacheInitialization: RedisCache init and config
- TestRedisCacheConnection: Connection and disconnection
- TestRedisCacheGet: Cache get operations
- TestRedisCacheGetCompression: Compression in get operations
- TestRedisCacheSet: Cache set operations
- TestRedisCacheSetCompression: Compression in set operations
- TestRedisCacheDelete: Delete operations
- TestRedisCacheClearPattern: Pattern-based clearing
- TestRedisCacheMetrics: Metrics tracking and reset
- TestRedisCacheEdgeCases: Edge cases and error handling
"""

from unittest.mock import AsyncMock, patch

import pytest
import zstandard as zstd

from src.infrastructure.cache.redis_cache import CacheMetrics, RedisCache
from src.infrastructure.config import Settings


# ============================================================================
# Test CacheMetrics Defaults
# ============================================================================


class TestCacheMetricsDefaults:
    """Test CacheMetrics default values."""

    def test_has_correct_default_values(self) -> None:
        """Test CacheMetrics initializes with zeros.

        Arrange: Create CacheMetrics with no args
        Act: Check default values
        Assert: All counters are zero
        """
        # Arrange & Act
        metrics = CacheMetrics()

        # Assert
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.errors == 0
        assert metrics.total_get_calls == 0
        assert metrics.total_set_calls == 0
        assert metrics.compression_ratio == 0.0
        assert metrics.avg_compression_time_ms == 0.0
        assert metrics.avg_decompression_time_ms == 0.0

    def test_accepts_custom_initial_values(self) -> None:
        """Test CacheMetrics accepts custom initial values.

        Arrange: Create CacheMetrics with custom values
        Act: Check values
        Assert: Custom values are set
        """
        # Arrange
        metrics = CacheMetrics(
            hits=50,
            misses=10,
            errors=2,
            total_get_calls=60,
            total_set_calls=100,
            compression_ratio=2.5,
            avg_compression_time_ms=1.5,
            avg_decompression_time_ms=0.8,
        )

        # Act & Assert
        assert metrics.hits == 50
        assert metrics.misses == 10
        assert metrics.errors == 2
        assert metrics.total_get_calls == 60
        assert metrics.total_set_calls == 100
        assert metrics.compression_ratio == 2.5
        assert metrics.avg_compression_time_ms == 1.5
        assert metrics.avg_decompression_time_ms == 0.8


# ============================================================================
# Test CacheMetrics Hit Rate
# ============================================================================


class TestCacheMetricsHitRate:
    """Test cache hit rate calculation."""

    def test_hit_rate_with_zero_calls(self) -> None:
        """Test hit rate returns 0.0 when no calls made.

        Arrange: Create metrics with 0 total calls
        Act: Get hit_rate
        Assert: Returns 0.0
        """
        # Arrange
        metrics = CacheMetrics()

        # Act
        result = metrics.hit_rate

        # Assert
        assert result == 0.0

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculates correct percentage.

        Arrange: Create metrics with 75 hits out of 100 calls
        Act: Get hit_rate
        Assert: Returns 75.0%
        """
        # Arrange
        metrics = CacheMetrics(hits=75, misses=25, total_get_calls=100)

        # Act
        result = metrics.hit_rate

        # Assert
        assert result == 75.0

    def test_hit_rate_all_hits(self) -> None:
        """Test hit rate with 100% hits.

        Arrange: Create metrics with all hits
        Act: Get hit_rate
        Assert: Returns 100.0%
        """
        # Arrange
        metrics = CacheMetrics(hits=100, misses=0, total_get_calls=100)

        # Act
        result = metrics.hit_rate

        # Assert
        assert result == 100.0

    def test_hit_rate_all_misses(self) -> None:
        """Test hit rate with 100% misses.

        Arrange: Create metrics with all misses
        Act: Get hit_rate
        Assert: Returns 0.0%
        """
        # Arrange
        metrics = CacheMetrics(hits=0, misses=100, total_get_calls=100)

        # Act
        result = metrics.hit_rate

        # Assert
        assert result == 0.0

    def test_hit_rate_with_partial_hits(self) -> None:
        """Test hit rate with various hit percentages.

        Arrange: Create metrics with 33 hits out of 100
        Act: Get hit_rate
        Assert: Returns 33.0%
        """
        # Arrange
        metrics = CacheMetrics(hits=33, misses=67, total_get_calls=100)

        # Act
        result = metrics.hit_rate

        # Assert
        assert result == 33.0


# ============================================================================
# Test CacheMetrics to_dict
# ============================================================================


class TestCacheMetricsToDict:
    """Test CacheMetrics dictionary conversion."""

    def test_to_dict_includes_all_fields(self) -> None:
        """Test to_dict() includes all metric fields.

        Arrange: Create metrics with various values
        Act: Call to_dict()
        Assert: Dict contains all fields
        """
        # Arrange
        metrics = CacheMetrics(
            hits=75,
            misses=25,
            errors=5,
            total_get_calls=100,
            total_set_calls=50,
            compression_ratio=2.5,
            avg_compression_time_ms=1.234,
            avg_decompression_time_ms=0.567,
        )

        # Act
        result = metrics.to_dict()

        # Assert
        assert result["hits"] == 75
        assert result["misses"] == 25
        assert result["errors"] == 5
        assert result["total_get_calls"] == 100
        assert result["total_set_calls"] == 50
        assert result["hit_rate_percent"] == 75.0
        assert result["compression_ratio"] == 2.5
        assert result["avg_compression_time_ms"] == 1.23
        assert result["avg_decompression_time_ms"] == 0.57

    def test_to_dict_rounds_hit_rate(self) -> None:
        """Test to_dict() rounds hit_rate to 2 decimals.

        Arrange: Create metrics with non-round hit rate
        Act: Call to_dict()
        Assert: hit_rate_percent is rounded
        """
        # Arrange
        metrics = CacheMetrics(hits=33, misses=67, total_get_calls=100)

        # Act
        result = metrics.to_dict()

        # Assert
        assert result["hit_rate_percent"] == 33.0

    def test_to_dict_rounds_compression_metrics(self) -> None:
        """Test to_dict() rounds compression metrics to 2 decimals.

        Arrange: Create metrics with precise compression values
        Act: Call to_dict()
        Assert: Values are rounded to 2 decimals
        """
        # Arrange
        metrics = CacheMetrics(
            compression_ratio=2.5678,
            avg_compression_time_ms=1.2345,
            avg_decompression_time_ms=0.5678,
        )

        # Act
        result = metrics.to_dict()

        # Assert
        assert result["compression_ratio"] == 2.57
        assert result["avg_compression_time_ms"] == 1.23
        assert result["avg_decompression_time_ms"] == 0.57


# ============================================================================
# Test RedisCache Initialization
# ============================================================================


class TestRedisCacheInitialization:
    """Test RedisCache initialization."""

    def test_init_with_compression_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with compression enabled.

        Arrange: Create Settings with cache enabled
        Act: Initialize RedisCache
        Assert: Compression components are created
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()

        # Act
        cache = RedisCache(settings)

        # Assert
        assert cache._compression_enabled is True
        assert cache._compression_threshold == 1024
        assert cache._compression_level == 3
        assert cache._compressor is not None
        assert cache._decompressor is not None

    def test_init_creates_metrics_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization creates CacheMetrics.

        Arrange: Create Settings
        Act: Initialize RedisCache
        Assert: Metrics object is created
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()

        # Act
        cache = RedisCache(settings)

        # Assert
        assert cache._metrics is not None
        assert isinstance(cache._metrics, CacheMetrics)

    def test_init_client_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test client is None before connect().

        Arrange: Create Settings
        Act: Initialize RedisCache
        Assert: Client is None
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()

        # Act
        cache = RedisCache(settings)

        # Assert
        assert cache._client is None


# ============================================================================
# Test RedisCache Connection
# ============================================================================


class TestRedisCacheConnection:
    """Test Redis connection and disconnection."""

    @pytest.mark.asyncio
    async def test_connect_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful Redis connection.

        Arrange: Create cache and mock Redis client
        Act: Call connect()
        Assert: Client is set and ping is called
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()

        with patch(
            "src.infrastructure.cache.redis_cache.aioredis.from_url",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            # Act
            await cache.connect()

            # Assert
            assert cache._client == mock_client
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_when_cache_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test connection when cache is disabled.

        Arrange: Create settings with cache disabled
        Act: Call connect()
        Assert: Client remains None
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "false")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        # Act
        await cache.connect()

        # Assert
        assert cache._client is None

    @pytest.mark.asyncio
    async def test_connect_failure_sets_client_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test connection failure sets client to None.

        Arrange: Create cache and mock connection failure
        Act: Call connect()
        Assert: Client is None (connection failed gracefully)
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        with patch(
            "src.infrastructure.cache.redis_cache.aioredis.from_url",
            side_effect=Exception("Connection failed"),
        ):
            # Act
            await cache.connect()

            # Assert
            assert cache._client is None

    @pytest.mark.asyncio
    async def test_disconnect_closes_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test disconnect closes the Redis client.

        Arrange: Create cache with mock client
        Act: Call disconnect()
        Assert: Client close() is called
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        cache._client = mock_client

        # Act
        await cache.disconnect()

        # Assert
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_with_no_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test disconnect when no client exists.

        Arrange: Create cache without connecting
        Act: Call disconnect()
        Assert: No errors raised
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)
        cache._client = None

        # Act & Assert: Should not raise
        await cache.disconnect()


# ============================================================================
# Test RedisCache Get Operations
# ============================================================================


class TestRedisCacheGet:
    """Test cache get operations."""

    @pytest.mark.asyncio
    async def test_get_when_client_not_connected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get() returns None when client not connected.

        Arrange: Create cache without connecting
        Act: Call get()
        Assert: Returns None and increments error count
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)
        cache._client = None

        # Act
        result = await cache.get("test_key")

        # Assert
        assert result is None
        assert cache._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit_uncompressed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cache hit with uncompressed data.

        Arrange: Create cache with mock client returning uncompressed JSON
        Act: Call get()
        Assert: Returns deserialized data and increments hits
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        test_data = {"name": "test", "value": 123}
        serialized = b'{"name":"test","value":123}'
        mock_client.get = AsyncMock(return_value=serialized)
        cache._client = mock_client

        # Act
        result = await cache.get("test_key")

        # Assert
        assert result == test_data
        assert cache._metrics.hits == 1
        assert cache._metrics.misses == 0
        assert cache._metrics.total_get_calls == 1

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cache miss returns None.

        Arrange: Create cache with mock client returning None
        Act: Call get()
        Assert: Returns None and increments misses
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        cache._client = mock_client

        # Act
        result = await cache.get("missing_key")

        # Assert
        assert result is None
        assert cache._metrics.hits == 0
        assert cache._metrics.misses == 1
        assert cache._metrics.total_get_calls == 1

    @pytest.mark.asyncio
    async def test_get_error_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get() handles Redis errors gracefully.

        Arrange: Create cache with mock client that raises exception
        Act: Call get()
        Assert: Returns None and increments error count
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Redis error"))
        cache._client = mock_client

        # Act
        result = await cache.get("test_key")

        # Assert
        assert result is None
        assert cache._metrics.errors == 1


# ============================================================================
# Test RedisCache Get with Compression
# ============================================================================


class TestRedisCacheGetCompression:
    """Test cache get with compressed data."""

    @pytest.mark.asyncio
    async def test_get_decompresses_compressed_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get() automatically decompresses compressed data.

        Arrange: Create cache with mock client returning compressed data
        Act: Call get()
        Assert: Returns decompressed data and tracks decompression time
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        test_data = {"name": "test", "value": 123}
        serialized = b'{"name":"test","value":123}'

        # Compress the data
        compressor = zstd.ZstdCompressor(level=3)
        compressed = compressor.compress(serialized)

        mock_client.get = AsyncMock(return_value=compressed)
        cache._client = mock_client

        # Act
        result = await cache.get("test_key")

        # Assert
        assert result == test_data
        assert cache._metrics.hits == 1
        assert cache._metrics.avg_decompression_time_ms > 0


# ============================================================================
# Test RedisCache Set Operations
# ============================================================================


class TestRedisCacheSet:
    """Test cache set operations."""

    @pytest.mark.asyncio
    async def test_set_when_client_not_connected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() returns False when client not connected.

        Arrange: Create cache without connecting
        Act: Call set()
        Assert: Returns False and increments error count
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)
        cache._client = None

        # Act
        result = await cache.set("test_key", {"test": "value"})

        # Assert
        assert result is False
        assert cache._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_set_without_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() without TTL uses set() method.

        Arrange: Create cache with mock client
        Act: Call set() without TTL
        Assert: Returns True and calls client.set()
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache._client = mock_client

        # Act: Small value that won't trigger compression
        result = await cache.set("test_key", {"small": "data"})

        # Assert
        assert result is True
        mock_client.set.assert_called_once()
        assert cache._metrics.total_set_calls == 1

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() with TTL uses setex() method.

        Arrange: Create cache with mock client
        Act: Call set() with TTL
        Assert: Returns True and calls client.setex() with correct TTL
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.setex = AsyncMock()
        cache._client = mock_client

        # Act
        result = await cache.set("test_key", {"test": "data"}, ttl=300)

        # Assert
        assert result is True
        mock_client.setex.assert_called_once()
        args = mock_client.setex.call_args[0]
        assert args[0] == "test_key"
        assert args[1] == 300

    @pytest.mark.asyncio
    async def test_set_error_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() handles Redis errors gracefully.

        Arrange: Create cache with mock client that raises exception
        Act: Call set()
        Assert: Returns False and increments error count
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock(side_effect=Exception("Redis error"))
        cache._client = mock_client

        # Act
        result = await cache.set("test_key", {"test": "data"})

        # Assert
        assert result is False
        assert cache._metrics.errors == 1


# ============================================================================
# Test RedisCache Set with Compression
# ============================================================================


class TestRedisCacheSetCompression:
    """Test cache set with compression."""

    @pytest.mark.asyncio
    async def test_set_auto_compresses_large_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() automatically compresses large values.

        Arrange: Create cache with mock client
        Act: Call set() with large value (> 1KB threshold)
        Assert: Compression metrics are updated
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache._client = mock_client

        # Act: Large value that triggers compression
        large_value = {"data": "x" * 2000}  # > 1KB threshold
        result = await cache.set("test_key", large_value)

        # Assert
        assert result is True
        assert cache._metrics.compression_ratio > 0
        assert cache._metrics.avg_compression_time_ms > 0

    @pytest.mark.asyncio
    async def test_set_force_compression(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() with forced compression.

        Arrange: Create cache with mock client
        Act: Call set() with compress=True on small value
        Assert: Compression occurs even for small value
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache._client = mock_client

        # Act
        result = await cache.set("test_key", {"small": "data"}, compress=True)

        # Assert
        assert result is True
        assert cache._metrics.compression_ratio > 0

    @pytest.mark.asyncio
    async def test_set_force_no_compression(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() with forced no compression.

        Arrange: Create cache with mock client
        Act: Call set() with compress=False on large value
        Assert: Compression is skipped
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache._client = mock_client

        # Act
        large_value = {"data": "x" * 2000}
        result = await cache.set("test_key", large_value, compress=False)

        # Assert
        assert result is True


# ============================================================================
# Test RedisCache Delete Operations
# ============================================================================


class TestRedisCacheDelete:
    """Test cache delete operations."""

    @pytest.mark.asyncio
    async def test_delete_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful delete operation.

        Arrange: Create cache with mock client that returns 1 (deleted)
        Act: Call delete()
        Assert: Returns True
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=1)
        cache._client = mock_client

        # Act
        result = await cache.delete("test_key")

        # Assert
        assert result is True
        mock_client.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_delete_key_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete when key doesn't exist.

        Arrange: Create cache with mock client that returns 0 (not found)
        Act: Call delete()
        Assert: Returns False
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=0)
        cache._client = mock_client

        # Act
        result = await cache.delete("missing_key")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_when_client_not_connected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete when client not connected.

        Arrange: Create cache without connecting
        Act: Call delete()
        Assert: Returns False
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)
        cache._client = None

        # Act
        result = await cache.delete("test_key")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_error_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test delete handles Redis errors gracefully.

        Arrange: Create cache with mock client that raises exception
        Act: Call delete()
        Assert: Returns False and increments error count
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(side_effect=Exception("Redis error"))
        cache._client = mock_client

        # Act
        result = await cache.delete("test_key")

        # Assert
        assert result is False
        assert cache._metrics.errors == 1


# ============================================================================
# Test RedisCache Clear Pattern
# ============================================================================


class TestRedisCacheClearPattern:
    """Test pattern-based cache clearing."""

    @pytest.mark.asyncio
    async def test_clear_pattern_with_matching_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test clear_pattern() with matching keys.

        Arrange: Create cache with mock client returning matching keys
        Act: Call clear_pattern()
        Assert: Returns count of deleted keys
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()

        # Mock scan_iter to return keys
        async def mock_scan_iter(match: str):  # type: ignore[no-untyped-def]
            for key in [b"user:1", b"user:2", b"user:3"]:
                yield key

        mock_client.scan_iter = mock_scan_iter
        mock_client.delete = AsyncMock(return_value=3)
        cache._client = mock_client

        # Act
        result = await cache.clear_pattern("user:*")

        # Assert
        assert result == 3
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_pattern_no_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test clear_pattern() with no matching keys.

        Arrange: Create cache with mock client returning no keys
        Act: Call clear_pattern()
        Assert: Returns 0
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()

        # Mock scan_iter to return nothing
        async def mock_scan_iter(match: str):  # type: ignore[no-untyped-def]
            return
            yield  # Make it a generator

        mock_client.scan_iter = mock_scan_iter
        cache._client = mock_client

        # Act
        result = await cache.clear_pattern("user:*")

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_pattern_when_client_not_connected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test clear_pattern when client not connected.

        Arrange: Create cache without connecting
        Act: Call clear_pattern()
        Assert: Returns 0
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)
        cache._client = None

        # Act
        result = await cache.clear_pattern("user:*")

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_pattern_error_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test clear_pattern handles Redis errors gracefully.

        Arrange: Create cache with mock scan_iter that raises exception
        Act: Call clear_pattern()
        Assert: Returns 0 and increments error count
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()

        async def mock_scan_iter(match: str):  # type: ignore[no-untyped-def]
            raise RuntimeError("Redis error")
            yield  # Make it a generator

        mock_client.scan_iter = mock_scan_iter
        cache._client = mock_client

        # Act
        result = await cache.clear_pattern("user:*")

        # Assert
        assert result == 0
        assert cache._metrics.errors == 1


# ============================================================================
# Test RedisCache Metrics
# ============================================================================


class TestRedisCacheMetrics:
    """Test cache metrics tracking and reset."""

    def test_get_metrics_returns_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_metrics() returns dictionary.

        Arrange: Create cache with some metrics
        Act: Call get_metrics()
        Assert: Returns dict with all metrics
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        cache._metrics.hits = 100
        cache._metrics.misses = 20
        cache._metrics.total_get_calls = 120

        # Act
        metrics = cache.get_metrics()

        # Assert
        assert metrics["hits"] == 100
        assert metrics["misses"] == 20
        assert pytest.approx(metrics["hit_rate_percent"], rel=0.01) == 83.33

    def test_reset_metrics_zeros_all_counters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test reset_metrics() zeros all counters.

        Arrange: Create cache with non-zero metrics
        Act: Call reset_metrics()
        Assert: All counters are zero
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        cache._metrics.hits = 100
        cache._metrics.misses = 20
        cache._metrics.errors = 5

        # Act
        cache.reset_metrics()

        # Assert
        assert cache._metrics.hits == 0
        assert cache._metrics.misses == 0
        assert cache._metrics.errors == 0


# ============================================================================
# Test RedisCache Edge Cases
# ============================================================================


class TestRedisCacheEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_set_with_none_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() with None value.

        Arrange: Create cache with mock client
        Act: Call set() with None value
        Assert: Serializes and stores None
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache._client = mock_client

        # Act
        result = await cache.set("test_key", None)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_set_with_empty_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test set() with empty dict value.

        Arrange: Create cache with mock client
        Act: Call set() with empty dict
        Assert: Serializes and stores empty dict
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        cache._client = mock_client

        # Act
        result = await cache.set("test_key", {})

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_get_with_empty_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get() with empty string key.

        Arrange: Create cache with mock client
        Act: Call get() with empty string
        Assert: Calls Redis with empty key
        """
        # Arrange
        monkeypatch.setenv("CACHE_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = Settings()
        cache = RedisCache(settings)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=None)
        cache._client = mock_client

        # Act
        result = await cache.get("")

        # Assert
        assert result is None
        mock_client.get.assert_called_once_with("")
