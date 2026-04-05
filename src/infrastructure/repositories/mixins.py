"""Repository mixins for reusable query logic.

This module provides mixins for common repository patterns like soft delete
filtering, pagination, and ordering, following the DRY (Don't Repeat Yourself)
principle.
"""

from typing import Any, TypeVar

from sqlalchemy import Select, asc, desc
from sqlalchemy.orm import InstrumentedAttribute

from src.domain.models.base import BaseEntity


T = TypeVar("T", bound=BaseEntity)


class SoftDeleteQueryMixin:
    """Mixin providing reusable soft delete query filtering logic.

    This mixin eliminates code duplication across repositories that need to
    filter deleted records. It provides standardized methods for filtering
    active (non-deleted) and deleted records.

    Example:
        ```python
        class BaseRepository[T: BaseEntity](IRepository[T], SoftDeleteQueryMixin):
            async def get_all(self, include_deleted: bool = False) -> list[T]:
                query = select(self._model)
                if not include_deleted:
                    query = self.filter_active(query, self._model)
                result = await self._session.execute(query)
                return list(result.scalars().all())
        ```

    Design Pattern:
        Mixin pattern for behavior composition without inheritance chain complexity.

    SOLID Principles:
        - Single Responsibility: Handles only soft delete filtering logic
        - Open/Closed: Closed for modification, open for extension via composition
        - Interface Segregation: Small, focused interface
    """

    @staticmethod
    def filter_active(query: Select[tuple[T, ...]], model: type[T]) -> Select[tuple[T, ...]]:
        """Filter query to include only non-deleted (active) records.

        Args:
            query: SQLAlchemy Select query to filter
            model: Entity model class with deleted_at column

        Returns:
            Filtered query excluding soft-deleted records

        Example:
            ```python
            query = select(User)
            query = SoftDeleteQueryMixin.filter_active(query, User)
            # WHERE deleted_at IS NULL
            ```
        """
        return query.where(model.deleted_at.is_(None))

    @staticmethod
    def filter_deleted(query: Select[tuple[T, ...]], model: type[T]) -> Select[tuple[T, ...]]:
        """Filter query to include only soft-deleted records.

        Args:
            query: SQLAlchemy Select query to filter
            model: Entity model class with deleted_at column

        Returns:
            Filtered query including only soft-deleted records

        Example:
            ```python
            query = select(User)
            query = SoftDeleteQueryMixin.filter_deleted(query, User)
            # WHERE deleted_at IS NOT NULL
            ```
        """
        return query.where(model.deleted_at.isnot(None))

    @staticmethod
    def apply_soft_delete_filter(
        query: Select[tuple[T, ...]],
        model: type[T],
        include_deleted: bool = False,
    ) -> Select[tuple[T, ...]]:
        """Apply soft delete filtering based on include_deleted flag.

        Convenience method that chooses the appropriate filter based on the
        include_deleted parameter.

        Args:
            query: SQLAlchemy Select query to filter
            model: Entity model class with deleted_at column
            include_deleted: If True, include deleted records; if False, exclude them

        Returns:
            Filtered query

        Example:
            ```python
            query = select(User)
            query = SoftDeleteQueryMixin.apply_soft_delete_filter(
                query, User, include_deleted=False
            )
            ```
        """
        if not include_deleted:
            return SoftDeleteQueryMixin.filter_active(query, model)
        return query


class PaginationQueryMixin:
    """Mixin providing standardized pagination query logic.

    Provides reusable methods for applying LIMIT and OFFSET to queries,
    ensuring consistent pagination behavior across repositories.

    Example:
        ```python
        class UserRepository(BaseRepository[User], PaginationQueryMixin):
            async def search(self, skip: int, limit: int) -> list[User]:
                query = select(User)
                query = self.apply_pagination(query, skip, limit)
                # ...
        ```

    Design Pattern:
        Mixin pattern for pagination behavior composition.
    """

    @staticmethod
    def apply_pagination(
        query: Select[tuple[T, ...]], skip: int, limit: int
    ) -> Select[tuple[T, ...]]:
        """Apply pagination (LIMIT/OFFSET) to query.

        Args:
            query: SQLAlchemy Select query
            skip: Number of records to skip (OFFSET)
            limit: Maximum number of records to return (LIMIT)

        Returns:
            Query with pagination applied

        Example:
            ```python
            query = select(User)
            query = PaginationQueryMixin.apply_pagination(query, skip=10, limit=20)
            # LIMIT 20 OFFSET 10
            ```

        Note:
            Validates that skip >= 0 and limit > 0 to prevent invalid queries.
        """
        if skip < 0:
            raise ValueError("skip must be >= 0")
        if limit <= 0:
            raise ValueError("limit must be > 0")

        return query.offset(skip).limit(limit)


class OrderingQueryMixin:
    """Mixin providing standardized query ordering logic.

    Provides methods for applying consistent ordering to queries with
    support for ascending/descending order.

    Example:
        ```python
        class UserRepository(BaseRepository[User], OrderingQueryMixin):
            async def get_all_ordered(self) -> list[User]:
                query = select(User)
                query = self.apply_ordering(query, User.created_at, ascending=False)
                # ORDER BY created_at DESC
        ```

    Design Pattern:
        Mixin pattern for ordering behavior composition.
    """

    @staticmethod
    def apply_ordering(
        query: Select[tuple[T, ...]],
        order_by: InstrumentedAttribute[Any],
        ascending: bool = True,
    ) -> Select[tuple[T, ...]]:
        """Apply ordering to query.

        Args:
            query: SQLAlchemy Select query
            order_by: Column to order by (e.g., User.created_at)
            ascending: True for ASC, False for DESC

        Returns:
            Query with ordering applied

        Example:
            ```python
            query = select(User)
            # Ascending order
            query = OrderingQueryMixin.apply_ordering(query, User.username)
            # Descending order
            query = OrderingQueryMixin.apply_ordering(query, User.created_at, ascending=False)
            ```
        """
        if ascending:
            return query.order_by(asc(order_by))
        return query.order_by(desc(order_by))


class CombinedRepositoryMixin(
    SoftDeleteQueryMixin,
    PaginationQueryMixin,
    OrderingQueryMixin,
):
    """Combined mixin providing all common repository query patterns.

    Combines soft delete filtering, pagination, and ordering in a single
    mixin for convenience. Repositories can inherit from this to get all
    common query utilities.

    Example:
        ```python
        class BaseRepository[T: BaseEntity](IRepository[T], CombinedRepositoryMixin):
            # Has access to all mixin methods
            async def get_all(
                self, skip: int = 0, limit: int = 10, include_deleted: bool = False
            ) -> list[T]:
                query = select(self._model)
                query = self.apply_soft_delete_filter(query, self._model, include_deleted)
                query = self.apply_ordering(query, self._model.created_at, ascending=False)
                query = self.apply_pagination(query, skip, limit)
                # ...
        ```

    Design Pattern:
        Composition of multiple mixins following the Single Responsibility Principle.

    Benefits:
        - DRY: Eliminates code duplication across repositories
        - Consistency: Ensures uniform behavior across all repositories
        - Maintainability: Centralized logic easier to update
        - Testability: Mixins can be tested independently
    """
