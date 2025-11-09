"""User domain model with multi-tenant support.

This module defines the User entity with email normalization,
username validation, and optional multi-tenancy capabilities.
"""

from uuid import UUID

from sqlalchemy import Boolean, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, validates

from src.domain.models.base import BaseEntity


class User(BaseEntity):
    """User entity representing system users with multi-tenant support.

    Attributes:
        id: UUIDv7 primary key (time-ordered for optimal database performance)
        email: Unique email address (automatically normalized to lowercase)
        username: Unique username (alphanumeric with underscores/hyphens)
        full_name: Optional display name
        is_active: Account activation status
        tenant_id: Optional tenant identifier for multi-tenancy isolation
        created_at: Entity creation timestamp
        updated_at: Last modification timestamp
        deleted_at: Soft delete timestamp (NULL if active)
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (normalized to lowercase for consistency)",
    )

    @validates("email")
    def normalize_email(self, _key: str, value: str) -> str:
        """Normalize email address to lowercase for case-insensitive uniqueness.

        This prevents duplicate accounts with different casing (e.g., User@example.com
        vs user@example.com) and ensures consistent lookups. Email addresses are
        case-insensitive per RFC 5321.

        Args:
            _key: Field name being validated (email)
            value: Raw email address value

        Returns:
            Lowercase normalized email address
        """
        return value.lower() if value else value

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique username identifier",
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User's full display name (optional)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Account activation status (False for suspended accounts)",
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Tenant identifier for multi-tenancy data isolation",
    )

    def __repr__(self) -> str:
        """Generate string representation showing user identification details."""
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
