"""User filtering using FilterSet."""

from datetime import datetime
from uuid import UUID

from src.domain.models.user import User
from src.infrastructure.filtering.filterset import (
    BooleanFilter,
    CharFilter,
    DateTimeFilter,
    FilterSet,
    UUIDFilter,
)


class UserFilterSet(FilterSet):
    """Declarative filters for User model.

    Example usage in endpoint:
        @router.get("/users/search")
        async def search_users(
            filters: UserFilterSet = Depends(),
            session: AsyncSession = Depends(get_session),
        ):
            query = select(User)
            query = filters.apply(query)
            result = await session.execute(query)
            return result.scalars().all()

    Example query:
        GET /users/search?username=john&is_active=true&created_after=2024-01-01T00:00:00Z
    """

    model = User

    # String filters with case-insensitive search
    email: str | None = CharFilter(
        lookup="icontains",
        description="Search by email (case-insensitive substring match)",
    )
    username: str | None = CharFilter(
        lookup="icontains",
        description="Search by username (case-insensitive substring match)",
    )
    full_name: str | None = CharFilter(
        lookup="icontains",
        description="Search by full name (case-insensitive substring match)",
    )

    # Exact match alternatives
    email_exact: str | None = CharFilter(
        field_name="email",
        lookup="exact",
        description="Filter by exact email",
    )
    username_exact: str | None = CharFilter(
        field_name="username",
        lookup="exact",
        description="Filter by exact username",
    )

    # Boolean filter
    is_active: bool | None = BooleanFilter(description="Filter by active status (true/false)")

    # UUID filter
    tenant_id: UUID | None = UUIDFilter(description="Filter by tenant ID")

    # DateTime range filters
    created_after: datetime | None = DateTimeFilter(
        field_name="created_at",
        lookup="gte",
        description="Show users created after this date (ISO 8601)",
    )
    created_before: datetime | None = DateTimeFilter(
        field_name="created_at",
        lookup="lte",
        description="Show users created before this date (ISO 8601)",
    )
    updated_after: datetime | None = DateTimeFilter(
        field_name="updated_at",
        lookup="gte",
        description="Show users updated after this date (ISO 8601)",
    )

    # Array filter examples (for models with array columns)
    # Uncomment these if User model has array fields like tags, roles, etc.
    #
    # tags_contain: list[str] | None = ArrayFilter(
    #     field_name="tags",
    #     lookup="array_contains",
    #     description="Filter users whose tags contain all specified values (PostgreSQL @>)"
    # )
    # tags_overlap: list[str] | None = ArrayFilter(
    #     field_name="tags",
    #     lookup="array_overlap",
    #     description="Filter users whose tags overlap with any specified values (PostgreSQL &&)"
    # )
    # roles_contain: list[str] | None = ArrayFilter(
    #     field_name="roles",
    #     lookup="array_contains",
    #     description="Filter users with all specified roles"
    # )
    # min_tags_count: int | None = ArrayFilter(
    #     field_name="tags",
    #     lookup="array_length_gte",
    #     description="Filter users with at least N tags"
    # )
