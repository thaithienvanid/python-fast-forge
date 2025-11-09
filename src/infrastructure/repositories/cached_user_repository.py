"""Cached user repository - extends generic CachedBaseRepository.

This module implements user-specific cached repository by extending the generic
CachedBaseRepository class and adding user-specific caching logic for email
and username lookups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID


if TYPE_CHECKING:
    from src.infrastructure.filtering.filterset import FilterSet
else:
    FilterSet = Any
from typing import TYPE_CHECKING, Any

from src.domain.interfaces import IUserRepository
from src.domain.models.user import User
from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.repositories.cached_base_repository import CachedBaseRepository
from src.infrastructure.repositories.user_repository import UserRepository


class CachedUserRepository(CachedBaseRepository[User], IUserRepository[User]):
    """Cached user repository with user-specific caching logic.

    Extends the generic CachedBaseRepository to provide user-specific caching
    functionality. Inherits common CRUD caching from base class and adds
    specialized caching for user queries by email and username.

    Cache Strategy:
    - Read operations: Try cache first, fall back to DB, then populate cache
    - Write operations: Perform DB operation, then invalidate related cache keys
    - TTL: 5 minutes (300 seconds) for cached entries

    Cached Operations:
    - get_by_id: Inherited from CachedBaseRepository
    - get_by_email: User-specific caching by email
    - get_by_username: User-specific caching by username
    - create: Inherited from CachedBaseRepository
    - update: Inherited, invalidates all keys (ID, email, username)
    - delete: Inherited, invalidates all keys
    - restore: Inherited, invalidates all keys
    - force_delete: Inherited, invalidates all keys

    Not Cached:
    - get_all: List operations (complex invalidation)
    - search_with_filters: Dynamic filtering (too many combinations)
    - count_with_filters: Count operations (can change frequently)
    - get_deleted: Admin operations (infrequent)

    Example:
        ```python
        base_repo = UserRepository(session)
        cache = RedisCache(settings)
        cached_repo = CachedUserRepository(base_repo, cache)

        # Uses cache
        user = await cached_repo.get_by_id(user_id)
        user = await cached_repo.get_by_email("user@example.com")

        # Invalidates cache
        await cached_repo.update(user)
        ```
    """

    def __init__(
        self,
        repository: UserRepository,
        cache: RedisCache,
        default_ttl: int = 300,
    ) -> None:
        """Initialize cached user repository.

        Args:
            repository: Base UserRepository instance to wrap
            cache: Redis cache instance for caching operations
            default_ttl: Default TTL in seconds (default: 300s = 5 min)
        """
        super().__init__(repository, cache, default_ttl)
        # Store typed reference for user-specific operations
        self._user_repository = repository

    # Cache key generation methods (required by CachedBaseRepository)

    def _get_cache_key_by_id(self, id: UUID) -> str:
        """Generate cache key for user by ID.

        Args:
            id: User UUID

        Returns:
            Cache key in format "user:{uuid}"
        """
        return f"user:{id}"

    def _get_all_cache_keys(self, entity: User) -> list[str]:
        """Get all cache keys related to a user for invalidation.

        Returns all cache keys that should be invalidated when user is modified:
        - Primary key: user:{id}
        - Email key: user:email:{email}
        - Username key: user:username:{username}

        Args:
            entity: User entity instance

        Returns:
            List of all cache keys associated with this user
        """
        return [
            self._get_cache_key_by_id(entity.id),
            self._cache_key_by_email(entity.email),
            self._cache_key_by_username(entity.username),
        ]

    # Helper methods for user-specific cache keys

    @staticmethod
    def _cache_key_by_email(email: str) -> str:
        """Generate cache key for user by email.

        Args:
            email: User email address

        Returns:
            Cache key in format "user:email:{email}" (lowercase)
        """
        return f"user:email:{email.lower()}"

    @staticmethod
    def _cache_key_by_username(username: str) -> str:
        """Generate cache key for user by username.

        Args:
            username: Username

        Returns:
            Cache key in format "user:username:{username}" (lowercase)
        """
        return f"user:username:{username.lower()}"

    # User-specific cached methods

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email with caching.

        Uses cache-aside pattern with email as lookup key.

        Args:
            email: User email address

        Returns:
            User if found and active, None otherwise
        """
        # Try cache first (gracefully handle cache failures)
        cache_key = self._cache_key_by_email(email)
        try:
            cached = await self._cache.get(cache_key)
            if cached:
                return User(**cached)
        except Exception:
            # Cache read failed - continue to database
            pass

        # Cache miss - fetch from database via typed repository
        user = await self._user_repository.get_by_email(email)

        # Populate cache (gracefully handle cache failures)
        if user:
            try:
                await self._cache.set(cache_key, user, ttl=self._default_ttl)
            except Exception:
                # Cache write failed - operation still succeeds
                pass

        return user

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username with caching.

        Uses cache-aside pattern with username as lookup key.

        Args:
            username: Username

        Returns:
            User if found and active, None otherwise
        """
        # Try cache first (gracefully handle cache failures)
        cache_key = self._cache_key_by_username(username)
        try:
            cached = await self._cache.get(cache_key)
            if cached:
                return User(**cached)
        except Exception:
            # Cache read failed - continue to database
            pass

        # Cache miss - fetch from database via typed repository
        user = await self._user_repository.get_by_username(username)

        # Populate cache (gracefully handle cache failures)
        if user:
            try:
                await self._cache.set(cache_key, user, ttl=self._default_ttl)
            except Exception:
                # Cache write failed - operation still succeeds
                pass

        return user

    # Note: find() and count() are inherited from CachedBaseRepository
    # as pass-through methods (not cached)
