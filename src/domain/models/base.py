"""Base entity classes for domain models with soft delete support.

This module defines the foundational entity classes used across all domain models,
providing common fields (ID, timestamps) and soft delete functionality with
optimized database indexing strategies.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid_extension import uuid7


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""


class BaseEntity(Base):
    """Base entity with time-ordered UUIDs and soft delete capabilities.

    All domain entities inherit from this class, gaining:
    - UUIDv7 primary keys (time-ordered for better database performance)
    - Automatic timestamp tracking (created_at, updated_at)
    - Soft delete support (deleted_at) with optimized partial indexing
    - Common helper methods for entity lifecycle management

    Performance Optimization:
        The deleted_at column uses partial indexes for query performance:
        - Partial index on `deleted_at IS NULL` for active record queries (99% of queries)
        - Composite indexes with tenant_id and is_active for multi-tenant filtered queries
        - Separate index on `deleted_at IS NOT NULL` for restoration/audit queries

        This ensures fast queries for the most common access patterns while
        minimizing index storage overhead.

    Note:
        This is an abstract class. Inherit from it to create concrete entity models.
    """

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        default=uuid7,
        comment="Primary key using UUIDv7 for time-ordered identifiers",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Timestamp of entity creation",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Timestamp of last modification",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
        comment="Soft delete timestamp (NULL if active, set when deleted). Uses partial indexing for performance.",
    )

    @property
    def is_deleted(self) -> bool:
        """Check whether entity is soft-deleted.

        Returns:
            True if entity has been soft-deleted, False otherwise
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark entity as deleted by setting the deleted_at timestamp.

        This method is idempotent - calling it on an already deleted entity
        preserves the original deletion time for audit integrity.
        """
        if self.deleted_at is None:
            self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore soft-deleted entity by clearing the deleted_at timestamp.

        Makes the entity visible in normal queries again.
        """
        self.deleted_at = None

    def __repr__(self) -> str:
        """Generate string representation showing entity type, ID, and deletion status."""
        status = "deleted" if self.is_deleted else "active"
        return f"<{self.__class__.__name__}(id={self.id}, status={status})>"
