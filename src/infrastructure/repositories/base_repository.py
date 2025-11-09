"""Base repository implementation for common entity operations.

This module provides a generic repository base class implementing standard
CRUD operations with soft delete support, eliminating boilerplate code across
entity-specific repositories.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces import IRepository
from src.domain.models.base import BaseEntity
from src.domain.pagination import Cursor, CursorPage, create_cursor_page


if TYPE_CHECKING:
    from src.infrastructure.filtering.filterset import FilterSet
else:
    FilterSet = Any


class BaseRepository[T: BaseEntity](IRepository[T]):
    """Generic repository providing CRUD operations with soft delete support.

    Implements the repository pattern with reusable database operations for
    any entity type. All queries automatically exclude soft-deleted records
    unless explicitly requested.

    Type Parameters:
        T: Entity type extending BaseEntity

    Attributes:
        _session: SQLAlchemy async session for database operations
        _model: Entity model class for type-safe queries
    """

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        """Initialize repository with session and model type.

        Args:
            session: Active async database session
            model: SQLAlchemy model class for entity type
        """
        self._session = session
        self._model = model

    async def get_by_id(self, id: UUID, include_deleted: bool = False) -> T | None:
        """Retrieve entity by unique identifier.

        Args:
            id: Entity's unique identifier (UUID)
            include_deleted: Whether to include soft-deleted entities

        Returns:
            Entity instance if found, None otherwise
        """
        query = select(self._model).where(self._model.id == id)

        if not include_deleted:
            query = query.where(self._model.deleted_at.is_(None))

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> list[T]:
        """Retrieve all entities with pagination and optional filtering.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum records to return
            tenant_id: Optional tenant ID for multi-tenant isolation
            include_deleted: Whether to include soft-deleted entities

        Returns:
            List of entity instances matching criteria
        """
        query = select(self._model)

        if not include_deleted:
            query = query.where(self._model.deleted_at.is_(None))

        if tenant_id and hasattr(self._model, "tenant_id"):
            model_cls: Any = self._model
            query = query.where(model_cls.tenant_id == tenant_id)

        query = query.offset(skip).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with generated UUID
        """
        self._session.add(entity)
        # Ensure DB state is synchronized so generated fields are available
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update existing entity.

        Args:
            entity: Entity with updated values

        Returns:
            Updated entity
        """
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, id: UUID) -> bool:
        """Soft delete entity by UUID (sets deleted_at timestamp).

        This performs a soft delete by setting the deleted_at timestamp.
        The entity remains in the database but is excluded from normal queries.

        Args:
            id: Entity UUID

        Returns:
            True if soft-deleted, False if not found
        """
        entity = await self.get_by_id(id, include_deleted=False)
        if not entity:
            return False

        entity.soft_delete()
        await self._session.flush()
        await self._session.refresh(entity)
        return True

    async def restore(self, id: UUID) -> bool:
        """Restore soft-deleted entity by clearing deleted_at timestamp.

        This restores a previously soft-deleted entity by clearing the
        deleted_at timestamp, making it visible in normal queries again.

        Args:
            id: Entity UUID

        Returns:
            True if restored, False if not found or not deleted
        """
        # Only get deleted entities
        entity = await self.get_by_id(id, include_deleted=True)
        if not entity or not entity.is_deleted:
            return False

        entity.restore()
        await self._session.flush()
        await self._session.refresh(entity)
        return True

    async def force_delete(self, id: UUID) -> bool:
        """Permanently delete entity from database (hard delete).

        This performs a hard delete, permanently removing the entity from
        the database. This operation cannot be undone.

        Args:
            id: Entity UUID

        Returns:
            True if deleted, False if not found
        """
        # Include deleted entities for force delete
        entity = await self.get_by_id(id, include_deleted=True)
        if not entity:
            return False

        self._session.delete(entity)  # type: ignore[unused-coroutine]  # delete() is synchronous in SQLAlchemy 2.0
        await self._session.flush()
        return True

    async def get_deleted(
        self,
        skip: int = 0,
        limit: int = 100,
        tenant_id: UUID | None = None,
    ) -> list[T]:
        """Get only soft-deleted entities.

        Returns only entities that have been soft-deleted (deleted_at is not NULL).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            tenant_id: Optional tenant ID for filtering

        Returns:
            List of soft-deleted entities
        """
        query = select(self._model)

        # Only get soft-deleted records
        query = query.where(self._model.deleted_at.is_not(None))

        # Add tenant filtering if tenant_id provided and model has tenant_id
        if tenant_id and hasattr(self._model, "tenant_id"):
            model_cls: Any = self._model
            query = query.where(model_cls.tenant_id == tenant_id)

        query = query.offset(skip).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_with_cursor(
        self,
        cursor: Cursor | None = None,
        limit: int = 50,
        tenant_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> CursorPage[T]:
        """Get entities with cursor-based pagination.

        This method provides unlimited pagination using cursor-based approach,
        which is more efficient than offset-based pagination for large datasets.
        By default, excludes soft-deleted entities.

        Args:
            cursor: Cursor for pagination (None for first page)
            limit: Maximum number of items to return (default: 50)
            tenant_id: Optional tenant ID for filtering
            include_deleted: If True, include soft-deleted entities

        Returns:
            CursorPage with items and next cursor

        Example:
            # First page
            page1 = await repo.get_with_cursor(limit=50)

            # Next page
            page2 = await repo.get_with_cursor(
                cursor=Cursor.decode(page1.next_cursor),
                limit=50
            )
        """
        query = select(self._model)

        # Filter out soft-deleted records by default
        if not include_deleted:
            query = query.where(self._model.deleted_at.is_(None))

        # Add tenant filtering if tenant_id provided and model has tenant_id
        if tenant_id and hasattr(self._model, "tenant_id"):
            model_cls: Any = self._model
            query = query.where(model_cls.tenant_id == tenant_id)

        # Apply cursor filtering
        # Assumes entities have created_at and id columns for ordering
        if cursor:
            if hasattr(self._model, "created_at") and cursor.sort_value:
                # Composite cursor (created_at, id) for stable ordering
                model_cls = self._model

                # Parse sort_value back to datetime if it's a string
                # (happens after cursor encode → decode round-trip)
                sort_time = cursor.sort_value
                if isinstance(sort_time, str):
                    sort_time = datetime.fromisoformat(sort_time.replace("Z", "+00:00"))

                query = query.where(
                    (model_cls.created_at < sort_time)
                    | (
                        (model_cls.created_at == sort_time)
                        & (model_cls.id < UUID(str(cursor.value)))
                    )
                )
            else:
                # Simple cursor (id only)
                model_cls = self._model
                query = query.where(model_cls.id < UUID(str(cursor.value)))

        # Order by created_at (if available) then id for consistent pagination
        if hasattr(self._model, "created_at"):
            model_cls = self._model
            query = query.order_by(model_cls.created_at.desc(), model_cls.id.desc())
        else:
            model_cls = self._model
            query = query.order_by(model_cls.id.desc())

        # Fetch limit + 1 to detect if there's a next page
        query = query.limit(limit + 1)

        result = await self._session.execute(query)
        items = list(result.scalars().all())

        # Create cursor from item
        def cursor_fn(item: T) -> Cursor:
            """Generate cursor for pagination from an item.

            Args:
                item: Entity item to create cursor from

            Returns:
                Cursor with item ID and optional sort value
            """
            if hasattr(item, "created_at"):
                return Cursor(value=item.id, sort_value=item.created_at)
            return Cursor(value=item.id)

        return create_cursor_page(items, limit, cursor_fn)

    async def find(
        self,
        filterset: "FilterSet",
        skip: int = 0,
        limit: int = 100,
    ) -> list[T]:
        """Find entities with FilterSet (generic filtering support).

        Uses FilterSet to build dynamic queries based on provided filter criteria.
        This method is generic and works with any entity type that has a corresponding
        FilterSet implementation. Follows idiomatic repository patterns.

        Args:
            filterset: FilterSet instance with filter criteria
            skip: Number of records to skip (offset for pagination)
            limit: Maximum number of records to return

        Returns:
            List of entities matching the filters (excludes soft-deleted by default)

        Example:
            ```python
            # Define a FilterSet for your entity
            class ProductFilterSet(FilterSet):
                model = Product
                name: str | None = CharFilter(lookup="icontains")
                price_min: float | None = NumberFilter(field_name="price", lookup="gte")


            # Use in repository
            filters = ProductFilterSet(name="laptop", price_min=500.0)
            products = await repo.find(filters, skip=0, limit=20)
            ```
        """
        # Build base query
        query = select(self._model)

        # Apply filters from FilterSet (exclude_deleted=True by default)
        query = filterset.apply(query, exclude_deleted=True)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Execute
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count(self, filterset: "FilterSet") -> int:
        """Count entities matching FilterSet criteria (generic counting support).

        Useful for implementing pagination UI that shows total count. Works with
        any entity type that has a corresponding FilterSet implementation.

        Args:
            filterset: FilterSet instance with filter criteria

        Returns:
            Number of entities matching the filters (excludes soft-deleted by default)

        Example:
            ```python
            filters = ProductFilterSet(category="electronics", price_min=100.0)
            total = await repo.count(filters)
            # Use total for pagination: total_pages = ceil(total / page_size)
            ```
        """
        # Build count query
        count_query = select(func.count()).select_from(self._model)

        # Apply filters from FilterSet (exclude_deleted=True by default)
        count_query = filterset.apply(count_query, exclude_deleted=True)

        # Execute
        result = await self._session.execute(count_query)
        return result.scalar_one()
