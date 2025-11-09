"""Generic cached repository base class for reusable caching functionality.

This module provides a generic abstract base class that implements the Decorator
Pattern to add caching functionality to any repository. It eliminates code
duplication across entity-specific cached repositories.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.domain.interfaces import IRepository
from src.domain.models.base import BaseEntity
from src.infrastructure.cache.redis_cache import RedisCache


if TYPE_CHECKING:
    from src.infrastructure.filtering.filterset import FilterSet
else:
    FilterSet = Any


class CachedBaseRepository[T: BaseEntity](IRepository[T], ABC):
    """Generic cached repository decorator providing caching for common operations.

    This abstract base class implements the Decorator Pattern to add caching
    functionality to any repository implementing IRepository[T]. Subclasses
    must implement cache key generation methods for their specific entity types.

    Design Pattern: Decorator Pattern
    - Wraps any IRepository[T] implementation
    - Adds caching behavior transparently
    - Delegates all database operations to wrapped repository

    Features:
    - Cache-aside pattern for read operations
    - Automatic cache invalidation on write operations
    - Configurable TTL per operation
    - Extensible for entity-specific caching logic
    - Type-safe with generic type parameter

    Cached Operations:
    - get_by_id: Cached with configurable TTL (default 300s)
    - create: Populates cache after creation
    - update: Invalidates all related cache entries
    - delete: Invalidates cache (soft delete)
    - restore: Invalidates cache
    - force_delete: Invalidates cache (hard delete)

    Not Cached (by default):
    - get_all: Complex to invalidate, frequently changing
    - get_deleted: Admin operation, infrequent
    - get_with_cursor: Cursor-based pagination complexity
    - list operations: Dynamic nature

    Cache Invalidation Strategy:
    - Write operations fetch entity first to get all related keys
    - All related keys are invalidated on modification
    - Ensures cache consistency after updates

    Type Parameters:
        T: Entity type extending BaseEntity

    Attributes:
        _repository: Wrapped repository for database operations
        _cache: Redis cache instance
        _default_ttl: Default TTL in seconds for cached entries
        _model_class: Entity model class for type-safe operations

    Example Usage:
        ```python
        class CachedUserRepository(CachedBaseRepository[User]):
            def _get_cache_key_by_id(self, id: UUID) -> str:
                return f"user:{id}"

            def _get_all_cache_keys(self, entity: User) -> list[str]:
                return [
                    self._get_cache_key_by_id(entity.id),
                    f"user:email:{entity.email.lower()}",
                    f"user:username:{entity.username.lower()}",
                ]

            # Add entity-specific cached methods
            async def get_by_email(self, email: str) -> User | None:
                cache_key = f"user:email:{email.lower()}"
                cached = await self._cache.get(cache_key)
                if cached:
                    return User(**cached)

                user = await self._repository.get_by_email(email)
                if user:
                    await self._cache.set(cache_key, user, ttl=self._default_ttl)
                return user
        ```
    """

    def __init__(
        self,
        repository: IRepository[T],
        cache: RedisCache,
        default_ttl: int = 300,
    ) -> None:
        """Initialize cached repository decorator.

        Args:
            repository: Base repository to wrap (must implement IRepository[T])
            cache: Redis cache instance for caching operations
            default_ttl: Default TTL in seconds for cached entries (default: 300s = 5 min)
        """
        self._repository = repository
        self._cache = cache
        self._default_ttl = default_ttl
        self._model_class = self._get_model_class()

    @abstractmethod
    def _get_cache_key_by_id(self, id: UUID) -> str:
        """Generate cache key for entity by ID.

        Must be implemented by subclasses to provide entity-specific key format.
        This is the primary cache key used for caching entities.

        Args:
            id: Entity UUID

        Returns:
            Cache key string (e.g., "user:{uuid}", "product:{uuid}")

        Example:
            ```python
            def _get_cache_key_by_id(self, id: UUID) -> str:
                return f"user:{id}"
            ```
        """
        ...

    @abstractmethod
    def _get_all_cache_keys(self, entity: T) -> list[str]:
        """Get all cache keys related to an entity for invalidation.

        Must be implemented by subclasses to return all cache keys that should
        be invalidated when the entity is modified. This includes primary key
        and any alternate keys (email, username, slug, etc.).

        Args:
            entity: Entity instance

        Returns:
            List of all cache keys associated with this entity

        Example:
            ```python
            def _get_all_cache_keys(self, entity: User) -> list[str]:
                return [
                    self._get_cache_key_by_id(entity.id),
                    f"user:email:{entity.email.lower()}",
                    f"user:username:{entity.username.lower()}",
                ]
            ```
        """
        ...

    def _get_model_class(self) -> type[T]:
        """Extract model class from wrapped repository for type safety.

        Returns:
            Entity model class

        Raises:
            NotImplementedError: If repository doesn't have _model attribute
        """
        # Try to get model from repository's _model attribute
        if hasattr(self._repository, "_model"):
            model = self._repository._model
            return model  # type: ignore[no-any-return]
        # Fallback error
        raise NotImplementedError(
            "Wrapped repository must have _model attribute or override this method"
        )

    # Cached CRUD operations

    async def get_by_id(self, id: UUID, include_deleted: bool = False) -> T | None:
        """Get entity by ID with caching.

        Cache-aside pattern:
        1. Check cache first
        2. If miss, fetch from database via wrapped repository
        3. Store result in cache with TTL

        Note: Only active (non-deleted) entities are cached to avoid stale data
        for deleted entities that may be restored.

        Args:
            id: Entity UUID
            include_deleted: If True, include soft-deleted entities (not cached)

        Returns:
            Entity if found, None otherwise
        """
        # Don't use cache for deleted entities
        if include_deleted:
            return await self._repository.get_by_id(id, include_deleted=True)

        # Try cache first (gracefully handle cache failures)
        cache_key = self._get_cache_key_by_id(id)
        try:
            cached = await self._cache.get(cache_key)
            if cached:
                return self._model_class(**cached)
        except Exception:
            # Cache read failed - continue to database
            pass

        # Cache miss - fetch from database
        entity = await self._repository.get_by_id(id, include_deleted=False)

        # Populate cache (gracefully handle cache failures)
        if entity:
            try:
                await self._cache.set(cache_key, entity, ttl=self._default_ttl)
            except Exception:
                # Cache write failed - operation still succeeds
                pass

        return entity

    async def create(self, entity: T) -> T:
        """Create entity and populate cache.

        Creates entity in database then caches it for subsequent reads.

        Args:
            entity: Entity to create

        Returns:
            Created entity with generated ID and timestamps
        """
        # Delegate to base repository
        created = await self._repository.create(entity)

        # Populate cache with new entity (gracefully handle cache failures)
        if created:
            cache_key = self._get_cache_key_by_id(created.id)
            try:
                await self._cache.set(cache_key, created, ttl=self._default_ttl)
            except Exception:
                # Cache write failed - operation still succeeds
                pass

        return created

    async def update(self, entity: T) -> T:
        """Update entity and invalidate all related cache entries.

        Invalidates all cache keys related to this entity to prevent serving
        stale data. This includes primary cache key and all alternate keys.

        Args:
            entity: Entity to update

        Returns:
            Updated entity
        """
        # Delegate to base repository
        updated = await self._repository.update(entity)

        # Invalidate all related cache entries (gracefully handle cache failures)
        if updated:
            cache_keys = self._get_all_cache_keys(updated)
            for key in cache_keys:
                try:
                    await self._cache.delete(key)
                except Exception:
                    # Cache delete failed - operation still succeeds
                    pass

        return updated

    async def delete(self, id: UUID) -> bool:
        """Soft delete entity and invalidate cache.

        Fetches entity first to determine all cache keys for invalidation,
        then performs soft delete and cache cleanup.

        Args:
            id: Entity UUID to soft delete

        Returns:
            True if deleted, False if not found
        """
        # Fetch entity first for cache key generation
        entity = await self._repository.get_by_id(id, include_deleted=False)

        # Delegate to base repository (soft delete)
        deleted = await self._repository.delete(id)

        # Invalidate cache if deletion succeeded (gracefully handle cache failures)
        if deleted and entity:
            cache_keys = self._get_all_cache_keys(entity)
            for key in cache_keys:
                try:
                    await self._cache.delete(key)
                except Exception:
                    # Cache delete failed - operation still succeeds
                    pass

        return deleted

    async def restore(self, id: UUID) -> bool:
        """Restore soft-deleted entity and invalidate cache.

        Invalidates cache to ensure subsequent reads fetch the restored entity.

        Args:
            id: Entity UUID to restore

        Returns:
            True if restored, False if not found or not deleted
        """
        # Fetch entity (including deleted) for cache key generation
        entity = await self._repository.get_by_id(id, include_deleted=True)

        # Delegate to base repository
        restored = await self._repository.restore(id)

        # Invalidate cache if restoration succeeded (gracefully handle cache failures)
        # This ensures subsequent reads get the fresh restored entity
        if restored and entity:
            cache_keys = self._get_all_cache_keys(entity)
            for key in cache_keys:
                try:
                    await self._cache.delete(key)
                except Exception:
                    # Cache delete failed - operation still succeeds
                    pass

        return restored

    async def force_delete(self, id: UUID) -> bool:
        """Permanently delete entity and invalidate cache.

        Fetches entity first for cache key generation, then performs hard
        delete and cache cleanup.

        Args:
            id: Entity UUID to permanently delete

        Returns:
            True if deleted, False if not found
        """
        # Fetch entity (including deleted) for cache key generation
        entity = await self._repository.get_by_id(id, include_deleted=True)

        # Delegate to base repository (hard delete)
        deleted = await self._repository.force_delete(id)

        # Invalidate cache if deletion succeeded (gracefully handle cache failures)
        if deleted and entity:
            cache_keys = self._get_all_cache_keys(entity)
            for key in cache_keys:
                try:
                    await self._cache.delete(key)
                except Exception:
                    # Cache delete failed - operation still succeeds
                    pass

        return deleted

    # Pass-through methods (not cached by default)

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> list[T]:
        """Get all entities with pagination (not cached by default).

        List operations are not cached due to:
        - Complexity of cache invalidation (any entity change affects the list)
        - Frequently changing nature of paginated results
        - Memory overhead of caching large lists

        Subclasses can override to add specific caching strategies if needed
        (e.g., short TTL for specific tenant queries).

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for multi-tenant filtering
            include_deleted: If True, include soft-deleted entities

        Returns:
            List of entities matching criteria
        """
        return await self._repository.get_all(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
            include_deleted=include_deleted,
        )

    async def get_deleted(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
    ) -> list[T]:
        """Get only soft-deleted entities (not cached).

        Admin/recovery operations typically don't need caching as they're
        infrequent and require fresh data.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for filtering

        Returns:
            List of soft-deleted entities
        """
        return await self._repository.get_deleted(
            skip=skip,
            limit=limit,
            tenant_id=tenant_id,
        )

    async def find(
        self,
        filterset: "FilterSet",
        skip: int = 0,
        limit: int = 100,
    ) -> list[T]:
        """Find entities with FilterSet (not cached by default).

        Filtering operations are not cached due to:
        - High cardinality of possible filter combinations
        - Dynamic nature of filter criteria
        - Memory overhead vs. benefit ratio

        Subclasses can override to add specific caching strategies if needed
        (e.g., caching popular filter combinations with short TTL).

        Args:
            filterset: FilterSet instance with filter criteria
            skip: Number of records to skip (offset for pagination)
            limit: Maximum number of records to return

        Returns:
            List of entities matching the filters
        """
        return await self._repository.find(
            filterset=filterset,
            skip=skip,
            limit=limit,
        )

    async def count(self, filterset: "FilterSet") -> int:
        """Count entities matching FilterSet criteria (not cached).

        Count operations are not cached as they can change frequently
        and are typically fast enough in the database with proper indexes.

        Args:
            filterset: FilterSet instance with filter criteria

        Returns:
            Total count of entities matching the filters
        """
        return await self._repository.count(filterset=filterset)
