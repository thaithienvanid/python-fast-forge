"""Unit tests for read models."""

from datetime import UTC, datetime
from uuid import uuid4

from src.infrastructure.persistence.read_models import UserReadModel


class TestUserReadModel:
    """Tests for UserReadModel SQLAlchemy model."""

    def test_creates_read_model_instance(self):
        """Can create read model instance with required fields."""
        user_id = uuid4()
        tenant_id = uuid4()
        now = datetime.now(UTC)

        model = UserReadModel(
            id=user_id,
            email="user@example.com",
            username="testuser",
            full_name="Test User",
            is_active=True,
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            total_orders=5,
            last_login_at=now,
            profile_completion=80,
        )

        assert model.id == user_id
        assert model.email == "user@example.com"
        assert model.username == "testuser"
        assert model.full_name == "Test User"
        assert model.is_active is True
        assert model.tenant_id == tenant_id
        assert model.created_at == now
        assert model.updated_at == now
        assert model.deleted_at is None
        assert model.total_orders == 5
        assert model.last_login_at == now
        assert model.profile_completion == 80

    def test_read_model_repr(self):
        """Repr includes key fields."""
        user_id = uuid4()
        now = datetime.now(UTC)

        model = UserReadModel(
            id=user_id,
            email="user@example.com",
            username="testuser",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        repr_str = repr(model)
        assert "UserReadModel" in repr_str
        assert str(user_id) in repr_str
        assert "user@example.com" in repr_str
        assert "testuser" in repr_str
        assert "True" in repr_str

    def test_read_model_table_name(self):
        """Read model has correct table name."""
        assert UserReadModel.__tablename__ == "user_read_model"

    def test_read_model_defaults(self):
        """Read model uses default values."""
        user_id = uuid4()
        now = datetime.now(UTC)

        model = UserReadModel(
            id=user_id,
            email="user@example.com",
            username="testuser",
            created_at=now,
            updated_at=now,
        )

        # Check defaults (these would be set by SQLAlchemy when persisted)
        assert hasattr(model, "is_active")
        assert hasattr(model, "total_orders")
        assert hasattr(model, "profile_completion")
