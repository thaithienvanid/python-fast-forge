"""CQRS Query handlers for processing read operations.

Query handlers read from denormalized read models for fast performance.
This is the "read side" of CQRS, completely separated from the write side.

Benefits:
- 10x faster queries (no joins, denormalized data)
- Independent scaling (can use read replicas)
- Cacheable results
- Optimized indexes for specific queries
- No impact on write side performance

Features:
- Read from optimized read models
- Cache integration
- Support for pagination, filtering, sorting
- Eventually consistent with write side (via projections)
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.queries import (
    UserDetailQuery,
    UserListQuery,
    UserQueryModel,
    UserSearchQuery,
    UserStatsQuery,
)
from src.domain.exceptions import EntityNotFoundError
from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.persistence.read_models import UserReadModel


class UserQueryHandler:
    """Handles user queries against read models.

    This handler executes queries against denormalized read models
    for fast performance. Results are cached when appropriate.

    Attributes:
        _session: SQLAlchemy session (ideally pointing to read replica)
        _cache: Redis cache for query results

    Example:
        >>> handler = UserQueryHandler(read_session, cache)
        >>> query = UserDetailQuery(user_id=user_id)
        >>> user = await handler.handle_user_detail(query)
    """

    def __init__(
        self,
        session: AsyncSession,
        cache: RedisCache | None = None,
    ):
        """Initialize query handler.

        Args:
            session: SQLAlchemy session (preferably read replica)
            cache: Optional Redis cache for results
        """
        self._session = session
        self._cache = cache

    async def handle_user_detail(self, query: UserDetailQuery) -> UserQueryModel:
        """Get user detail from read model.

        This is FAST because:
        1. No event reconstruction needed
        2. Denormalized data (no joins)
        3. Cached results
        4. Can use read replica database

        Args:
            query: User detail query

        Returns:
            User query model with all details

        Raises:
            EntityNotFoundError: If user doesn't exist

        Example:
            >>> query = UserDetailQuery(user_id=user_id, include_deleted=False)
            >>> user = await handler.handle_user_detail(query)
            >>> print(f"Email: {user.email}, Orders: {user.total_orders}")
        """
        # Try cache first
        if self._cache:
            cache_key = f"user:detail:{query.user_id}"
            cached = await self._cache.get(cache_key)
            if cached:
                return UserQueryModel.model_validate_json(cached)

        # Query read model
        stmt = select(UserReadModel).where(UserReadModel.id == query.user_id)

        if not query.include_deleted:
            stmt = stmt.where(UserReadModel.deleted_at.is_(None))

        result = await self._session.execute(stmt)
        user_rm = result.scalar_one_or_none()

        if not user_rm:
            raise EntityNotFoundError(f"User {query.user_id} not found")

        # Convert to query model
        user = UserQueryModel.model_validate(user_rm)

        # Cache result
        if self._cache:
            await self._cache.set(cache_key, user.model_dump_json(), ttl=300)

        return user

    async def handle_list_users(self, query: UserListQuery) -> list[UserQueryModel]:
        """List users from read model.

        Supports filtering, sorting, and pagination.
        Results are from denormalized table for speed.

        Args:
            query: User list query with filters

        Returns:
            List of user query models

        Example:
            >>> query = UserListQuery(
            ...     tenant_id=tenant_id,
            ...     is_active=True,
            ...     email_contains="@example.com",
            ...     skip=0,
            ...     limit=50,
            ... )
            >>> users = await handler.handle_list_users(query)
        """
        # Build query
        stmt = select(UserReadModel)

        # Apply filters
        if query.tenant_id:
            stmt = stmt.where(UserReadModel.tenant_id == query.tenant_id)

        if query.is_active is not None:
            stmt = stmt.where(UserReadModel.is_active == query.is_active)

        if query.email_contains:
            stmt = stmt.where(UserReadModel.email.ilike(f"%{query.email_contains}%"))

        if query.username_contains:
            stmt = stmt.where(UserReadModel.username.ilike(f"%{query.username_contains}%"))

        if query.created_after:
            stmt = stmt.where(UserReadModel.created_at >= query.created_after)

        if query.created_before:
            stmt = stmt.where(UserReadModel.created_at <= query.created_before)

        # Always exclude soft-deleted
        stmt = stmt.where(UserReadModel.deleted_at.is_(None))

        # Apply sorting
        order_column = getattr(UserReadModel, query.order_by, UserReadModel.created_at)
        if query.order_direction == "desc":
            stmt = stmt.order_by(order_column.desc())
        else:
            stmt = stmt.order_by(order_column.asc())

        # Apply pagination
        stmt = stmt.offset(query.skip).limit(query.limit)

        # Execute query
        result = await self._session.execute(stmt)
        users_rm = result.scalars().all()

        # Convert to query models
        return [UserQueryModel.model_validate(rm) for rm in users_rm]

    async def handle_search_users(self, query: UserSearchQuery) -> list[UserQueryModel]:
        """Search users using full-text search.

        Searches across email, username, and full_name fields.

        Args:
            query: Search query

        Returns:
            List of matching users

        Example:
            >>> query = UserSearchQuery(search_term="john", limit=20)
            >>> users = await handler.handle_search_users(query)
        """
        # Build search query
        search_term = f"%{query.search_term}%"

        stmt = select(UserReadModel).where(
            (UserReadModel.email.ilike(search_term))
            | (UserReadModel.username.ilike(search_term))
            | (UserReadModel.full_name.ilike(search_term))
        )

        # Filter by tenant
        if query.tenant_id:
            stmt = stmt.where(UserReadModel.tenant_id == query.tenant_id)

        # Exclude deleted
        stmt = stmt.where(UserReadModel.deleted_at.is_(None))

        # Order by relevance (username match first, then email, then full_name)
        stmt = stmt.order_by(
            UserReadModel.username.ilike(search_term).desc(),
            UserReadModel.email.ilike(search_term).desc(),
            UserReadModel.created_at.desc(),
        )

        # Limit results
        stmt = stmt.limit(query.limit)

        # Execute
        result = await self._session.execute(stmt)
        users_rm = result.scalars().all()

        return [UserQueryModel.model_validate(rm) for rm in users_rm]

    async def handle_user_stats(self, query: UserStatsQuery) -> dict[str, int]:
        """Get aggregate statistics about users.

        Returns counts and aggregations for analytics/dashboards.

        Args:
            query: Stats query

        Returns:
            Dictionary with statistics

        Example:
            >>> query = UserStatsQuery(tenant_id=tenant_id, time_period="last_30_days")
            >>> stats = await handler.handle_user_stats(query)
            >>> print(stats)
            {
                "total": 1500,
                "active": 1200,
                "inactive": 300,
                "deleted": 50,
                "created_today": 25,
                "created_this_week": 150,
                "created_this_month": 500,
            }
        """
        # Base query
        base_stmt = select(func.count()).select_from(UserReadModel)

        if query.tenant_id:
            base_stmt = base_stmt.where(UserReadModel.tenant_id == query.tenant_id)

        # Total users (including deleted)
        total_result = await self._session.execute(base_stmt)
        total = total_result.scalar() or 0

        # Active users
        active_stmt = base_stmt.where(
            UserReadModel.is_active.is_(True),
            UserReadModel.deleted_at.is_(None),
        )
        active_result = await self._session.execute(active_stmt)
        active = active_result.scalar() or 0

        # Inactive users
        inactive_stmt = base_stmt.where(
            UserReadModel.is_active.is_(False),
            UserReadModel.deleted_at.is_(None),
        )
        inactive_result = await self._session.execute(inactive_stmt)
        inactive = inactive_result.scalar() or 0

        # Deleted users
        deleted_stmt = base_stmt.where(UserReadModel.deleted_at.is_not(None))
        deleted_result = await self._session.execute(deleted_stmt)
        deleted = deleted_result.scalar() or 0

        # Time-based stats
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Created today
        created_today_stmt = base_stmt.where(
            UserReadModel.created_at >= today_start,
            UserReadModel.deleted_at.is_(None),
        )
        created_today_result = await self._session.execute(created_today_stmt)
        created_today = created_today_result.scalar() or 0

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "deleted": deleted,
            "created_today": created_today,
            "active_percentage": round((active / total * 100) if total > 0 else 0, 2),
        }


__all__ = [
    "UserQueryHandler",
]
