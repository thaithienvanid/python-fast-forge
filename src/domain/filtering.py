"""Domain-layer filtering protocol.

This module defines abstract filtering interfaces that the domain layer can
depend on without creating circular dependencies with the infrastructure layer.

The concrete FilterSet implementation lives in infrastructure, while the domain
layer only depends on this protocol, following the Dependency Inversion Principle.
"""

from typing import ClassVar, Protocol

from sqlalchemy import Select


class IFilterSet(Protocol):
    """Protocol for declarative filtering on SQLAlchemy queries.

    This protocol defines the interface that FilterSet implementations must follow.
    The domain layer depends on this protocol, while the infrastructure layer
    provides the concrete implementation.

    This design eliminates circular dependencies:
    - Domain (interfaces.py) imports IFilterSet from domain.filtering
    - Infrastructure (filterset.py) implements FilterSet conforming to IFilterSet
    - No direct dependency between domain and infrastructure

    Example:
        ```python
        # Domain layer (interfaces.py)
        async def find(self, filterset: IFilterSet, skip: int, limit: int) -> list[T]: ...


        # Infrastructure layer (filterset.py)
        class FilterSet(BaseModel):  # Conforms to IFilterSet protocol
            def apply(self, query: Select) -> Select: ...


        # Usage
        class UserFilterSet(FilterSet):
            model = User
            email: str | None = CharFilter(lookup="icontains")
        ```
    """

    model: ClassVar[type]
    """The SQLAlchemy model class this filterset operates on."""

    def apply(self, query: Select, *, exclude_deleted: bool = True) -> Select:  # type: ignore
        """Apply filter conditions to a SQLAlchemy query.

        Args:
            query: Base SQLAlchemy select query to apply filters to
            exclude_deleted: If True, automatically exclude soft-deleted records

        Returns:
            Modified query with filter conditions applied

        Example:
            ```python
            filters = UserFilterSet(email__icontains="@example.com", is_active=True)
            query = select(User)
            filtered_query = filters.apply(query)
            # SELECT * FROM users WHERE email ILIKE '%@example.com%' AND is_active = true
            ```
        """
        ...

    def get_count_query(self, *, exclude_deleted: bool = True) -> Select:  # type: ignore
        """Build a count query with filters applied.

        Args:
            exclude_deleted: If True, exclude soft-deleted records from count

        Returns:
            Count query with filters applied

        Example:
            ```python
            filters = UserFilterSet(is_active=True)
            count_query = filters.get_count_query()
            # SELECT COUNT(*) FROM users WHERE is_active = true
            ```
        """
        ...

    def is_valid(self) -> bool:
        """Check if any filters are actively applied.

        Returns:
            True if at least one filter has a non-None value

        Example:
            ```python
            filters = UserFilterSet()
            assert not filters.is_valid()  # No filters set

            filters = UserFilterSet(email="test@example.com")
            assert filters.is_valid()  # Has active filter
            ```
        """
        ...


# Type alias for backward compatibility
FilterSetProtocol = IFilterSet

__all__ = ["FilterSetProtocol", "IFilterSet"]
