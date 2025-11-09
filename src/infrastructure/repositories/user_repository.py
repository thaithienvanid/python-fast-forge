"""User repository for database operations.

This module implements user-specific database queries, focusing solely on
data access without caching logic. For cached operations, use the
CachedUserRepository decorator.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces import IUserRepository
from src.domain.models.user import User
from src.infrastructure.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User], IUserRepository[User]):
    """User-specific repository implementing IUserRepository interface.

    Provides database operations for User entities following the Single
    Responsibility Principle. This repository handles only persistence
    logic without caching concerns.

    Filtering support (search_with_filters, count_with_filters) is inherited
    from BaseRepository, which provides generic filtering for any entity.

    For caching support, wrap this repository with CachedUserRepository:
        ```python
        base_repo = UserRepository(session)
        cached_repo = CachedUserRepository(base_repo, cache)
        ```
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user repository with database session.

        Args:
            session: Active async SQLAlchemy session
        """
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve user by email address (excludes soft-deleted users).

        Args:
            email: User's email address

        Returns:
            User instance if found and active, None otherwise
        """
        result = await self._session.execute(
            select(User).where(User.email == email).where(User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username (excludes soft-deleted users).

        Args:
            username: Username

        Returns:
            User if found and active, None otherwise
        """
        result = await self._session.execute(
            select(User).where(User.username == username).where(User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
