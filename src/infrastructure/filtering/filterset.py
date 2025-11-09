"""Declarative filtering system inspired by sqlalchemy_filterset and Django REST framework.

This module provides a simple, declarative way to define filters for SQLAlchemy models.

Example:
    class UserFilterSet(FilterSet):
        model = User

        email: str | None = CharFilter(lookup='icontains')
        username: str | None = CharFilter(lookup='exact')
        is_active: bool | None = BooleanFilter()
        created_after: datetime | None = DateTimeFilter(field_name='created_at', lookup='gte')

    # Usage in endpoint
    @router.get("/users")
    async def list_users(
        filters: UserFilterSet = Depends(),
        session: AsyncSession = Depends(get_session),
    ):
        query = filters.apply(select(User))
        result = await session.execute(query)
        return result.scalars().all()
"""

from typing import Any, ClassVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, and_, func, select


# ============================================================================
# Filter Descriptor
# ============================================================================


class FilterDescriptor:
    """Descriptor that stores filter metadata."""

    def __init__(
        self,
        *,
        field_name: str | None = None,
        lookup: str = "exact",
        description: str | None = None,
    ):
        self.field_name = field_name
        self.lookup = lookup
        self.description = description

    def __set_name__(self, owner: type, name: str) -> None:
        self.attr_name = name
        if self.field_name is None:
            self.field_name = name

    def get_filter_expression(self, column: Any, value: Any) -> Any:  # type: ignore
        """Build SQLAlchemy filter expression."""
        if value is None:
            return None

        # Map lookup types to SQLAlchemy operations
        if self.lookup == "exact":
            return column == value
        if self.lookup == "iexact":
            return func.lower(column) == func.lower(value)
        if self.lookup == "contains":
            return column.contains(value)
        if self.lookup == "icontains":
            return column.ilike(f"%{value}%")
        if self.lookup == "startswith":
            return column.startswith(value)
        if self.lookup == "istartswith":
            return column.ilike(f"{value}%")
        if self.lookup == "endswith":
            return column.endswith(value)
        if self.lookup == "iendswith":
            return column.ilike(f"%{value}")
        if self.lookup == "gt":
            return column > value
        if self.lookup == "gte":
            return column >= value
        if self.lookup == "lt":
            return column < value
        if self.lookup == "lte":
            return column <= value
        if self.lookup == "in":
            return column.in_(value)
        if self.lookup == "notin":
            return column.notin_(value)
        if self.lookup == "isnull":
            return column.is_(None) if value else column.is_not(None)
        # PostgreSQL array operators
        if self.lookup == "array_contains":
            # PostgreSQL @> operator: array contains elements
            # Example: tags @> ['python', 'fastapi']
            return column.contains(value)
        if self.lookup == "array_contained_by":
            # PostgreSQL <@ operator: array is contained by
            # Example: tags <@ ['python', 'fastapi', 'django']
            return column.contained_by(value)
        if self.lookup == "array_overlap":
            # PostgreSQL && operator: arrays have common elements
            # Example: tags && ['python', 'rust']
            return column.overlap(value)
        if self.lookup == "array_length":
            # Check array length
            # Example: array_length(tags, 1) = 3
            return func.array_length(column, 1) == value
        if self.lookup == "array_length_gte":
            # Check array length greater than or equal
            return func.array_length(column, 1) >= value
        if self.lookup == "array_length_lte":
            # Check array length less than or equal
            return func.array_length(column, 1) <= value
        raise ValueError(f"Unknown lookup type: {self.lookup}")


# ============================================================================
# Filter Functions (syntactic sugar)
# ============================================================================


def CharFilter(
    *,
    field_name: str | None = None,
    lookup: str = "exact",
    description: str | None = None,
) -> Any:
    """Create a character/string filter.

    Args:
        field_name: Model field name (defaults to filter attribute name)
        lookup: Lookup type (exact, icontains, startswith, etc.)
        description: Field description for OpenAPI docs

    Returns:
        Field with filter metadata
    """
    return Field(
        default=None,
        description=description,
        json_schema_extra={
            "_filter": FilterDescriptor(
                field_name=field_name, lookup=lookup, description=description
            )
        },
    )


def IntegerFilter(
    *,
    field_name: str | None = None,
    lookup: str = "exact",
    description: str | None = None,
) -> Any:
    """Create an integer filter."""
    return Field(
        default=None,
        description=description,
        json_schema_extra={
            "_filter": FilterDescriptor(
                field_name=field_name, lookup=lookup, description=description
            )
        },
    )


def BooleanFilter(
    *,
    field_name: str | None = None,
    description: str | None = None,
) -> Any:
    """Create a boolean filter."""
    return Field(
        default=None,
        description=description,
        json_schema_extra={
            "_filter": FilterDescriptor(
                field_name=field_name, lookup="exact", description=description
            )
        },
    )


def DateTimeFilter(
    *,
    field_name: str | None = None,
    lookup: str = "exact",
    description: str | None = None,
) -> Any:
    """Create a datetime filter."""
    return Field(
        default=None,
        description=description,
        json_schema_extra={
            "_filter": FilterDescriptor(
                field_name=field_name, lookup=lookup, description=description
            )
        },
    )


def UUIDFilter(
    *,
    field_name: str | None = None,
    lookup: str = "exact",
    description: str | None = None,
) -> Any:
    """Create a UUID filter."""
    return Field(
        default=None,
        description=description,
        json_schema_extra={
            "_filter": FilterDescriptor(
                field_name=field_name, lookup=lookup, description=description
            )
        },
    )


def ArrayFilter(
    *,
    field_name: str | None = None,
    lookup: str = "array_contains",
    description: str | None = None,
) -> Any:
    """Create an array filter for PostgreSQL array columns.

    Supports PostgreSQL array operators:
    - array_contains: Array contains all specified elements (@>)
    - array_contained_by: Array is contained by specified array (<@)
    - array_overlap: Arrays have any elements in common (&&)
    - array_length: Array has exact length
    - array_length_gte: Array length >= specified value
    - array_length_lte: Array length <= specified value
    - exact: Exact array match (=)
    - in: Array value is in list of arrays

    Args:
        field_name: Model field name (defaults to filter attribute name)
        lookup: Lookup type (array_contains, array_overlap, etc.)
        description: Field description for OpenAPI docs

    Returns:
        Field with filter metadata

    Examples:
        # Check if tags array contains ['python', 'fastapi']
        tags_contain = ArrayFilter(lookup='array_contains')

        # Check if tags array overlaps with search terms
        tags_overlap = ArrayFilter(lookup='array_overlap')

        # Check if roles array has at least 2 elements
        min_roles = ArrayFilter(field_name='roles', lookup='array_length_gte')
    """
    return Field(
        default=None,
        description=description,
        json_schema_extra={
            "_filter": FilterDescriptor(
                field_name=field_name, lookup=lookup, description=description
            )
        },
    )


# ============================================================================
# FilterSet Base Class
# ============================================================================


class FilterSet(BaseModel):
    """Base class for declarative filtersets.

    Simply inherit from this class and define your filters as class attributes.

    Example:
        class UserFilterSet(FilterSet):
            model = User

            email: str | None = CharFilter(lookup='icontains')
            username: str | None = CharFilter(lookup='exact')
            is_active: bool | None = BooleanFilter()

        # In endpoint
        @router.get("/users")
        async def list_users(
            filters: UserFilterSet = Depends(),
            session: AsyncSession = Depends(get_session),
        ):
            query = filters.apply(select(User))
            result = await session.execute(query)
            return result.scalars().all()
    """

    model: ClassVar[type] = None  # Override in subclass

    def apply(self, query: Select, *, exclude_deleted: bool = True) -> Select:  # type: ignore
        """Apply filters to SQLAlchemy query.

        Args:
            query: Base SQLAlchemy select query
            exclude_deleted: If True, automatically exclude soft-deleted records

        Returns:
            Filtered query
        """
        if self.model is None:
            raise ValueError("model class variable must be set")

        expressions = []

        # Iterate through all fields and apply filters
        for field_name, field_info in self.__class__.model_fields.items():
            # Get filter metadata from json_schema_extra
            json_extra = field_info.json_schema_extra or {}
            filter_descriptor = json_extra.get("_filter") if isinstance(json_extra, dict) else None

            if filter_descriptor:
                # Set field_name if not explicitly set
                if filter_descriptor.field_name is None:
                    filter_descriptor.field_name = field_name

                # Get filter value
                value = getattr(self, field_name, None)
                if value is not None:
                    # Get model column
                    column = getattr(self.model, filter_descriptor.field_name)
                    # Build expression
                    expr = filter_descriptor.get_filter_expression(column, value)
                    if expr is not None:
                        expressions.append(expr)

        # Add soft delete filter if model has deleted_at
        if exclude_deleted and hasattr(self.model, "deleted_at"):
            expressions.append(self.model.deleted_at.is_(None))  # type: ignore

        # Apply all expressions
        if expressions:
            query = query.where(and_(*expressions))

        return query

    def get_count_query(self, *, exclude_deleted: bool = True) -> Select:  # type: ignore
        """Get count query with filters applied.

        Args:
            exclude_deleted: If True, exclude soft-deleted records

        Returns:
            Count query
        """
        if self.model is None:
            raise ValueError("model class variable must be set")

        query = select(func.count()).select_from(self.model)  # type: ignore
        return self.apply(query, exclude_deleted=exclude_deleted)

    def is_valid(self) -> bool:
        """Check if filterset has any active filters.

        Returns:
            True if any filters are applied
        """
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name, None)
            if value is not None:
                return True
        return False
