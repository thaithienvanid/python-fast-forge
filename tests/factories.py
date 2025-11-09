"""Test data factories for creating test objects.

Following the factory pattern instead of hardcoded test data provides:
- Flexibility: Easy to create variations
- Maintainability: Changes in one place
- Readability: Clear, expressive test data creation
- DRY: Avoid duplication across tests
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from uuid_extension import uuid7

from src.domain.models.user import User


def user_factory(
    id: UUID | None = None,
    email: str | None = None,
    username: str | None = None,
    full_name: str | None = None,
    is_active: bool = True,
    tenant_id: UUID | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    deleted_at: datetime | None = None,
    **kwargs: Any,
) -> User:
    """Factory function for creating User instances with sensible defaults.

    Args:
        id: User ID (generates UUIDv7 if not provided)
        email: User email (generates if not provided)
        username: Username (generates if not provided)
        full_name: Full name (None by default)
        is_active: Active status (True by default)
        tenant_id: Tenant ID (generates if not provided)
        created_at: Creation timestamp (now if not provided)
        updated_at: Update timestamp (now if not provided)
        deleted_at: Soft delete timestamp (None by default)
        **kwargs: Additional User model fields

    Returns:
        User instance with provided or default values

    Examples:
        >>> # Create user with defaults
        >>> user = user_factory()
        >>> assert user.is_active is True

        >>> # Create user with custom email
        >>> user = user_factory(email="alice@example.com")
        >>> assert user.email == "alice@example.com"

        >>> # Create inactive user
        >>> user = user_factory(is_active=False)
        >>> assert user.is_active is False
    """
    # Generate unique defaults
    unique_id = uuid7()

    # Build user data with defaults
    user_data = {
        "id": id or uuid7(),
        "email": email or f"user{str(unique_id)[:8]}@example.com",
        "username": username or f"user{str(unique_id)[:8]}",
        "full_name": full_name,
        "is_active": is_active,
        "tenant_id": tenant_id or uuid7(),
        "created_at": created_at or datetime.now(UTC),
        "updated_at": updated_at or datetime.now(UTC),
        "deleted_at": deleted_at,
        **kwargs,
    }

    return User(**user_data)


def user_factory_batch(count: int, **common_attrs: Any) -> list[User]:
    """Create multiple users with shared attributes.

    Args:
        count: Number of users to create
        **common_attrs: Attributes shared by all users

    Returns:
        List of User instances

    Examples:
        >>> # Create 5 users in same tenant
        >>> tenant_id = uuid7()
        >>> users = user_factory_batch(5, tenant_id=tenant_id)
        >>> assert all(u.tenant_id == tenant_id for u in users)

        >>> # Create 3 inactive users
        >>> users = user_factory_batch(3, is_active=False)
        >>> assert all(not u.is_active for u in users)
    """
    return [user_factory(**common_attrs) for _ in range(count)]


def deleted_user_factory(**kwargs: Any) -> User:
    """Factory for soft-deleted users.

    Args:
        **kwargs: User attributes (overrides defaults)

    Returns:
        User instance with deleted_at set

    Examples:
        >>> user = deleted_user_factory()
        >>> assert user.is_deleted is True
        >>> assert user.deleted_at is not None
    """
    kwargs.setdefault("deleted_at", datetime.now(UTC))
    return user_factory(**kwargs)


def admin_user_factory(**kwargs: Any) -> User:
    """Factory for admin users (if you have role field).

    This is a placeholder - adjust based on your User model.

    Args:
        **kwargs: User attributes (overrides defaults)

    Returns:
        User instance configured as admin
    """
    return user_factory(**kwargs)


def pagination_item_factory(
    id: UUID | None = None,
    name: str | None = None,
    created_at: datetime | None = None,
    **kwargs: Any,
):
    """Factory for creating pagination test items.

    This is a test-only model used for pagination tests.

    Args:
        id: Item ID (generates UUIDv7 if not provided)
        name: Item name (generates if not provided)
        created_at: Creation timestamp (now if not provided)
        **kwargs: Additional fields

    Returns:
        Dictionary with pagination item data

    Examples:
        >>> # Create item with defaults
        >>> item = pagination_item_factory()
        >>> assert item["id"] is not None

        >>> # Create item with custom name
        >>> item = pagination_item_factory(name="Test Item")
        >>> assert item["name"] == "Test Item"
    """
    unique_id = uuid7()

    return {
        "id": id or uuid7(),
        "name": name or f"Item {str(unique_id)[:8]}",
        "created_at": created_at or datetime.now(UTC),
        **kwargs,
    }


def pagination_item_batch_factory(count: int, **common_attrs: Any) -> list[dict[str, Any]]:
    """Create multiple pagination items with shared attributes.

    Args:
        count: Number of items to create
        **common_attrs: Attributes shared by all items

    Returns:
        List of pagination item dictionaries

    Examples:
        >>> # Create 10 items with increasing timestamps
        >>> base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        >>> items = pagination_item_batch_factory(10, created_at=base_time)
        >>> assert len(items) == 10
    """
    return [pagination_item_factory(**common_attrs) for _ in range(count)]


# Future factories for other models
# Add factories as you create more domain models:
# def organization_factory(**kwargs): ...  # noqa: ERA001
# def project_factory(**kwargs): ...  # noqa: ERA001
# def api_key_factory(**kwargs): ...  # noqa: ERA001
