"""Redis-based caching implementation with compression and metrics support."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
import zstandard as zstd

from src.infrastructure.config import Settings
from src.infrastructure.logging.config import get_logger
from src.utils import serialization


logger = get_logger(__name__)


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    total_get_calls: int = 0
    total_set_calls: int = 0
    compression_ratio: float = 0.0
    avg_compression_time_ms: float = 0.0
    avg_decompression_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_get_calls == 0:
            return 0.0
        return (self.hits / self.total_get_calls) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "total_get_calls": self.total_get_calls,
            "total_set_calls": self.total_set_calls,
            "hit_rate_percent": round(self.hit_rate, 2),
            "compression_ratio": round(self.compression_ratio, 2),
            "avg_compression_time_ms": round(self.avg_compression_time_ms, 2),
            "avg_decompression_time_ms": round(self.avg_decompression_time_ms, 2),
        }


class RedisCache:
    """Redis cache implementation with async support, compression, and metrics.

    Features:
    - Automatic JSON serialization/deserialization
    - Optional zstd compression for large values
    - Performance metrics tracking
    - Configurable TTL per key
    - Pattern-based cache invalidation

    Compression:
    - Uses zstd (Zstandard) for fast compression with high ratio
    - Automatically compresses values > compression_threshold bytes
    - Compression level 3 balances speed and ratio (1-22 available)
    - Typical compression ratio: 2-5x for JSON data
    - Compression overhead: ~0.1-0.5ms for 1KB-100KB values
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize Redis cache.

        Args:
            settings: Application settings
        """
        self._settings = settings
        self._client: aioredis.Redis[bytes] | None = None
        self._metrics = CacheMetrics()

        # Compression settings
        self._compression_enabled = getattr(settings, "cache_compression_enabled", True)
        self._compression_threshold = getattr(settings, "cache_compression_threshold", 1024)  # 1KB
        self._compression_level = getattr(
            settings, "cache_compression_level", 3
        )  # Balance speed/ratio

        # Initialize compressor if enabled
        if self._compression_enabled:
            self._compressor = zstd.ZstdCompressor(level=self._compression_level)
            self._decompressor = zstd.ZstdDecompressor()
            logger.info(
                "cache_compression_enabled",
                threshold_bytes=self._compression_threshold,
                level=self._compression_level,
            )

    async def connect(self) -> None:
        """Connect to Redis."""
        if not self._settings.cache_enabled:
            logger.info("cache_disabled")
            return

        try:
            self._client = await aioredis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=False,  # Changed to False for binary compression support
                max_connections=self._settings.redis_max_connections,
            )
            assert self._client is not None
            ping_result = self._client.ping()
            if hasattr(ping_result, "__await__"):
                await ping_result
            logger.info("redis_connected", url=self._settings.redis_url)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            self._client = None

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            logger.info("redis_disconnected")

    async def get(self, key: str) -> Any | None:
        """Get value from cache with automatic decompression.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        if not self._client:
            self._metrics.errors += 1
            return None

        self._metrics.total_get_calls += 1

        try:
            value_bytes = await self._client.get(key)
            if value_bytes:
                # Check if value is compressed (starts with zstd magic number)
                if self._compression_enabled and value_bytes[:4] == b"\x28\xb5\x2f\xfd":
                    # Decompress
                    decompression_start = datetime.now()
                    decompressed = self._decompressor.decompress(value_bytes)
                    decompression_time = (
                        datetime.now() - decompression_start
                    ).total_seconds() * 1000

                    # Update metrics
                    if self._metrics.avg_decompression_time_ms == 0:
                        self._metrics.avg_decompression_time_ms = decompression_time
                    else:
                        self._metrics.avg_decompression_time_ms = (
                            self._metrics.avg_decompression_time_ms * 0.9 + decompression_time * 0.1
                        )

                    value_str = decompressed.decode("utf-8")
                    logger.debug(
                        "cache_hit_compressed",
                        key=key,
                        compressed_size=len(value_bytes),
                        decompressed_size=len(decompressed),
                        decompression_time_ms=round(decompression_time, 2),
                    )
                else:
                    # Uncompressed value
                    value_str = value_bytes.decode("utf-8")
                    logger.debug("cache_hit", key=key, size_bytes=len(value_bytes))

                self._metrics.hits += 1
                return serialization.loads(value_str)

            self._metrics.misses += 1
            logger.debug("cache_miss", key=key)
            return None
        except Exception as e:
            self._metrics.errors += 1
            logger.error("cache_get_error", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        compress: bool | None = None,
    ) -> bool:
        """Set value in cache with optional compression.

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (optional)
            compress: Force compression on/off (None = auto based on size)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            self._metrics.errors += 1
            return False

        self._metrics.total_set_calls += 1

        try:
            # Serialize with extended JSON encoder (handles UUID, datetime, Pydantic, etc.)
            serialized_bytes = serialization.dumps_bytes(value)
            original_size = len(serialized_bytes)

            # Determine if should compress
            should_compress = (
                compress
                if compress is not None
                else (self._compression_enabled and original_size >= self._compression_threshold)
            )

            if should_compress:
                # Compress the value
                compression_start = datetime.now()
                compressed_bytes = self._compressor.compress(serialized_bytes)
                compression_time = (datetime.now() - compression_start).total_seconds() * 1000
                compressed_size = len(compressed_bytes)

                # Update metrics
                ratio = original_size / compressed_size if compressed_size > 0 else 1.0
                if self._metrics.compression_ratio == 0:
                    self._metrics.compression_ratio = ratio
                else:
                    self._metrics.compression_ratio = (
                        self._metrics.compression_ratio * 0.9 + ratio * 0.1
                    )

                if self._metrics.avg_compression_time_ms == 0:
                    self._metrics.avg_compression_time_ms = compression_time
                else:
                    self._metrics.avg_compression_time_ms = (
                        self._metrics.avg_compression_time_ms * 0.9 + compression_time * 0.1
                    )

                final_bytes = compressed_bytes
                logger.debug(
                    "cache_set_compressed",
                    key=key,
                    original_size=original_size,
                    compressed_size=compressed_size,
                    ratio=round(ratio, 2),
                    compression_time_ms=round(compression_time, 2),
                    ttl=ttl,
                )
            else:
                final_bytes = serialized_bytes
                logger.debug("cache_set", key=key, size_bytes=original_size, ttl=ttl)

            # Store in Redis
            if ttl:
                await self._client.setex(key, ttl, final_bytes)
            else:
                await self._client.set(key, final_bytes)

            return True
        except Exception as e:
            self._metrics.errors += 1
            logger.error("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False otherwise
        """
        if not self._client:
            return False

        try:
            result = await self._client.delete(key)
            logger.debug("cache_delete", key=key, deleted=result > 0)
            return bool(result > 0)
        except Exception as e:
            self._metrics.errors += 1
            logger.error("cache_delete_error", key=key, error=str(e))
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern.

        Args:
            pattern: Key pattern (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        if not self._client:
            return 0

        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                result = await self._client.delete(*keys)
                logger.info("cache_pattern_cleared", pattern=pattern, count=result)
                return int(result)
            return 0
        except Exception as e:
            self._metrics.errors += 1
            logger.error("cache_clear_pattern_error", pattern=pattern, error=str(e))
            return 0

    def get_metrics(self) -> dict[str, Any]:
        """Get current cache metrics.

        Returns:
            Dictionary containing cache performance metrics
        """
        return self._metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset cache metrics to zero."""
        self._metrics = CacheMetrics()
        logger.info("cache_metrics_reset")
