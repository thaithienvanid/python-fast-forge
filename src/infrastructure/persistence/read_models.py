"""Read models for CQRS query side.

Read models are denormalized, optimized tables for fast queries.
They are kept in sync with the event store via projection workers.

Read Model Characteristics:
- Denormalized (no joins needed)
- Optimized indexes for common queries
- Eventually consistent with write side
- Can be rebuilt from event store
- Separate from write models (User entity)

Benefits:
- 10x faster queries (no joins)
- Independent scaling (read replicas)
- Multiple views of same data
- Optimized for specific use cases
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from src.domain.models.base import Base


class UserReadModel(Base):
    """Denormalized user read model for fast queries.

    This table is optimized for reads and kept in sync with events
    via projection workers. It includes denormalized data from multiple
    aggregates for performance.

    Indexes:
        - Primary key on id
        - Index on email (unique)
        - Index on username (unique)
        - Index on (tenant_id, is_active) for tenant queries
        - Index on created_at for time-based queries
        - Index on deleted_at for filtering soft-deleted records

    Denormalized Fields:
        - total_orders: Count from Order aggregate
        - last_login_at: From authentication events
        - profile_completion: Calculated from filled fields

    Example:
        >>> read_model = UserReadModel(
        ...     id=user_id,
        ...     email="user@example.com",
        ...     username="john",
        ...     is_active=True,
        ...     created_at=datetime.now(UTC),
        ...     updated_at=datetime.now(UTC),
        ...     total_orders=5,
        ...     profile_completion=80,
        ... )
        >>> session.add(read_model)
        >>> await session.commit()
    """

    __tablename__ = "user_read_model"

    # Primary key
    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        comment="User identifier",
    )

    # Core user fields
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Email address",
    )
    username = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Username",
    )
    full_name = Column(
        String(255),
        nullable=True,
        comment="Full name",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Active status",
    )
    tenant_id = Column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Tenant identifier",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Last update timestamp",
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Soft delete timestamp",
    )

    # Denormalized fields (computed from events)
    total_orders = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Total orders count (denormalized from Order aggregate)",
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp (from auth events)",
    )
    profile_completion = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Profile completion percentage (0-100)",
    )

    # Indexes for common queries
    __table_args__ = (
        # Composite index for tenant-filtered queries
        Index(
            "ix_user_read_model_tenant_active",
            "tenant_id",
            "is_active",
        ),
        # Index for time-based queries
        Index(
            "ix_user_read_model_created_at",
            "created_at",
        ),
        # Partial index for active users (most common query - deleted_at IS NULL)
        Index(
            "ix_user_read_model_active_users",
            "id",
            postgresql_where=(deleted_at.is_(None)),
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"UserReadModel("
            f"id={self.id}, "
            f"email={self.email}, "
            f"username={self.username}, "
            f"is_active={self.is_active})"
        )


__all__ = [
    "UserReadModel",
]
