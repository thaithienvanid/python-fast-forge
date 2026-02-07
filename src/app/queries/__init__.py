"""CQRS Query models for the read side.

Queries represent requests for data without changing system state.
They read from optimized, denormalized read models for fast performance.

Query vs Command:
- Query: "Show me user details" (read-only, always succeeds)
- Command: "Create a user" (write, can fail)

Read Model Characteristics:
- Denormalized (no joins needed)
- Optimized for specific queries
- Eventually consistent with write side
- Can have multiple read models for same aggregate

Features:
- Fast reads (no complex joins)
- Cacheable results
- Separation from write model
- Can read from replicas or separate database
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserQueryModel(BaseModel):
    """Denormalized user model optimized for reads.

    This is the "read side" of CQRS. It's kept in sync with events
    via projection workers, and optimized for fast queries.

    Denormalization Examples:
    - total_orders: Calculated from OrderCreatedEvent projections
    - last_login_at: Updated from UserLoggedInEvent
    - profile_completion: Calculated field based on filled data

    Attributes:
        id: User identifier
        email: Email address
        username: Username
        full_name: Full name (optional)
        is_active: Active status
        tenant_id: Tenant identifier (multi-tenancy)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        deleted_at: Soft delete timestamp (None if active)
        total_orders: Count of orders (denormalized from Order aggregate)
        last_login_at: Last login timestamp (denormalized from auth events)
        profile_completion: Profile completion percentage (calculated)

    Example:
        >>> user = UserQueryModel(
        ...     id=user_id,
        ...     email="user@example.com",
        ...     username="john",
        ...     is_active=True,
        ...     created_at=datetime.now(UTC),
        ...     updated_at=datetime.now(UTC),
        ...     total_orders=5,
        ...     profile_completion=80,
        ... )
    """

    # Core fields (from User aggregate)
    id: UUID = Field(..., description="User identifier")
    email: EmailStr = Field(..., description="Email address")
    username: str = Field(..., description="Username")
    full_name: str | None = Field(None, description="Full name")
    is_active: bool = Field(True, description="Active status")
    tenant_id: UUID | None = Field(None, description="Tenant identifier")

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deleted_at: datetime | None = Field(None, description="Soft delete timestamp")

    # Denormalized fields (from other aggregates/events)
    total_orders: int = Field(0, description="Total orders count (denormalized)")
    last_login_at: datetime | None = Field(None, description="Last login timestamp")
    profile_completion: int = Field(0, ge=0, le=100, description="Profile completion %")

    class Config:
        """Pydantic configuration."""

        from_attributes = True  # Allow SQLAlchemy model conversion


class UserListQuery(BaseModel):
    """Query for listing users with filters and pagination.

    This query model represents a request to list users.
    The query handler will execute this against the read model.

    Attributes:
        tenant_id: Filter by tenant (multi-tenancy)
        is_active: Filter by active status
        email_contains: Filter by email substring
        username_contains: Filter by username substring
        skip: Number of records to skip (offset pagination)
        limit: Maximum number of records to return

    Example:
        >>> query = UserListQuery(
        ...     tenant_id=tenant_id,
        ...     is_active=True,
        ...     email_contains="@example.com",
        ...     skip=0,
        ...     limit=50,
        ... )
        >>> users = await query_handler.handle_list_users(query)
    """

    # Filters
    tenant_id: UUID | None = Field(None, description="Filter by tenant")
    is_active: bool | None = Field(None, description="Filter by active status")
    email_contains: str | None = Field(None, description="Email substring filter")
    username_contains: str | None = Field(None, description="Username substring filter")
    created_after: datetime | None = Field(None, description="Filter by creation date")
    created_before: datetime | None = Field(None, description="Filter by creation date")

    # Pagination
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(50, ge=1, le=100, description="Maximum records to return")

    # Sorting
    order_by: str = Field("created_at", description="Field to sort by")
    order_direction: str = Field("desc", description="Sort direction (asc/desc)")

    class Config:
        """Pydantic configuration."""

        frozen = True


class UserDetailQuery(BaseModel):
    """Query for getting detailed user information.

    This retrieves full user details including denormalized fields.

    Attributes:
        user_id: User to retrieve
        include_deleted: Whether to include soft-deleted users

    Example:
        >>> query = UserDetailQuery(user_id=user_id, include_deleted=False)
        >>> user = await query_handler.handle_user_detail(query)
    """

    user_id: UUID = Field(..., description="User to retrieve")
    include_deleted: bool = Field(False, description="Include soft-deleted users")

    class Config:
        """Pydantic configuration."""

        frozen = True


class UserSearchQuery(BaseModel):
    """Query for full-text search across users.

    This uses search indexes for fast lookups.

    Attributes:
        search_term: Search term (searches email, username, full_name)
        tenant_id: Filter by tenant
        limit: Maximum results

    Example:
        >>> query = UserSearchQuery(
        ...     search_term="john",
        ...     tenant_id=tenant_id,
        ...     limit=20,
        ... )
        >>> users = await query_handler.handle_search_users(query)
    """

    search_term: str = Field(..., min_length=2, description="Search term")
    tenant_id: UUID | None = Field(None, description="Filter by tenant")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")

    class Config:
        """Pydantic configuration."""

        frozen = True


class UserStatsQuery(BaseModel):
    """Query for user statistics and aggregations.

    This returns aggregate statistics about users.

    Attributes:
        tenant_id: Filter by tenant
        time_period: Time period for stats (e.g., "last_30_days")

    Example:
        >>> query = UserStatsQuery(tenant_id=tenant_id, time_period="last_30_days")
        >>> stats = await query_handler.handle_user_stats(query)
        >>> print(f"Total: {stats['total']}, Active: {stats['active']}")
    """

    tenant_id: UUID | None = Field(None, description="Filter by tenant")
    time_period: str = Field("all_time", description="Time period for stats")

    class Config:
        """Pydantic configuration."""

        frozen = True


__all__ = [
    "UserDetailQuery",
    "UserListQuery",
    "UserQueryModel",
    "UserSearchQuery",
    "UserStatsQuery",
]
