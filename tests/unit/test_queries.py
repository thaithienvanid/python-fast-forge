"""Unit tests for CQRS query models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.app.queries import (
    UserDetailQuery,
    UserListQuery,
    UserQueryModel,
    UserSearchQuery,
    UserStatsQuery,
)


class TestUserQueryModel:
    """Tests for UserQueryModel (read model)."""

    def test_creates_model_with_all_required_fields(self):
        """Model creation succeeds with all required fields."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        model = UserQueryModel(
            id=user_id,
            email="user@example.com",
            username="testuser",
            full_name="Test User",
            is_active=True,
            tenant_id=uuid4(),
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
        assert model.total_orders == 5
        assert model.profile_completion == 80

    def test_creates_model_with_defaults(self):
        """Model uses default values for optional fields."""
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        model = UserQueryModel(
            id=user_id,
            email="user@example.com",
            username="testuser",
            created_at=now,
            updated_at=now,
        )

        assert model.full_name is None
        assert model.is_active is True  # default
        assert model.tenant_id is None
        assert model.deleted_at is None
        assert model.total_orders == 0  # default
        assert model.last_login_at is None
        assert model.profile_completion == 0  # default

    def test_rejects_invalid_email(self):
        """Rejects model with invalid email."""
        with pytest.raises(ValidationError) as exc_info:
            UserQueryModel(
                id=uuid4(),
                email="not-an-email",
                username="testuser",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        assert "email" in str(exc_info.value)

    def test_profile_completion_validates_range(self):
        """Profile completion must be between 0 and 100."""
        now = datetime.now(timezone.utc)

        # Test valid values
        for value in [0, 50, 100]:
            model = UserQueryModel(
                id=uuid4(),
                email="user@example.com",
                username="testuser",
                created_at=now,
                updated_at=now,
                profile_completion=value,
            )
            assert model.profile_completion == value

        # Test invalid values
        for value in [-1, 101, 150]:
            with pytest.raises(ValidationError) as exc_info:
                UserQueryModel(
                    id=uuid4(),
                    email="user@example.com",
                    username="testuser",
                    created_at=now,
                    updated_at=now,
                    profile_completion=value,
                )
            assert "profile_completion" in str(exc_info.value)

    def test_supports_from_attributes(self):
        """Model can be created from SQLAlchemy objects (from_attributes=True)."""
        # This is enabled by Config.from_attributes = True
        model = UserQueryModel.model_config
        assert "from_attributes" in model
        assert model["from_attributes"] is True


class TestUserListQuery:
    """Tests for UserListQuery."""

    def test_creates_query_with_all_filters(self):
        """Query creation succeeds with all filters."""
        tenant_id = uuid4()
        now = datetime.now(timezone.utc)

        query = UserListQuery(
            tenant_id=tenant_id,
            is_active=True,
            email_contains="@example.com",
            username_contains="test",
            created_after=now,
            created_before=now,
            skip=10,
            limit=25,
            order_by="email",
            order_direction="asc",
        )

        assert query.tenant_id == tenant_id
        assert query.is_active is True
        assert query.email_contains == "@example.com"
        assert query.username_contains == "test"
        assert query.skip == 10
        assert query.limit == 25
        assert query.order_by == "email"
        assert query.order_direction == "asc"

    def test_creates_query_with_defaults(self):
        """Query uses default values when not specified."""
        query = UserListQuery()

        assert query.tenant_id is None
        assert query.is_active is None
        assert query.email_contains is None
        assert query.username_contains is None
        assert query.skip == 0  # default
        assert query.limit == 50  # default
        assert query.order_by == "created_at"  # default
        assert query.order_direction == "desc"  # default

    def test_validates_skip_non_negative(self):
        """Skip must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            UserListQuery(skip=-1)

        assert "skip" in str(exc_info.value)

    def test_validates_limit_range(self):
        """Limit must be between 1 and 100."""
        # Valid limits
        for limit in [1, 50, 100]:
            query = UserListQuery(limit=limit)
            assert query.limit == limit

        # Invalid limits
        for limit in [0, 101, 1000]:
            with pytest.raises(ValidationError) as exc_info:
                UserListQuery(limit=limit)
            assert "limit" in str(exc_info.value)

    def test_query_is_immutable(self):
        """Query cannot be modified after creation."""
        query = UserListQuery(skip=10, limit=25)

        with pytest.raises((ValidationError, AttributeError)):
            query.skip = 20


class TestUserDetailQuery:
    """Tests for UserDetailQuery."""

    def test_creates_query_successfully(self):
        """Query creation succeeds with required fields."""
        user_id = uuid4()
        query = UserDetailQuery(user_id=user_id, include_deleted=True)

        assert query.user_id == user_id
        assert query.include_deleted is True

    def test_defaults_to_exclude_deleted(self):
        """Query defaults to include_deleted=False."""
        user_id = uuid4()
        query = UserDetailQuery(user_id=user_id)

        assert query.user_id == user_id
        assert query.include_deleted is False

    def test_requires_user_id(self):
        """Query requires user_id field."""
        with pytest.raises(ValidationError) as exc_info:
            UserDetailQuery()

        assert "user_id" in str(exc_info.value)

    def test_query_is_immutable(self):
        """Query cannot be modified after creation."""
        query = UserDetailQuery(user_id=uuid4())

        with pytest.raises((ValidationError, AttributeError)):
            query.include_deleted = True


class TestUserSearchQuery:
    """Tests for UserSearchQuery."""

    def test_creates_query_with_all_fields(self):
        """Query creation succeeds with all fields."""
        tenant_id = uuid4()
        query = UserSearchQuery(
            search_term="john",
            tenant_id=tenant_id,
            limit=30,
        )

        assert query.search_term == "john"
        assert query.tenant_id == tenant_id
        assert query.limit == 30

    def test_creates_query_with_defaults(self):
        """Query uses default values for optional fields."""
        query = UserSearchQuery(search_term="john")

        assert query.search_term == "john"
        assert query.tenant_id is None
        assert query.limit == 20  # default

    def test_requires_search_term(self):
        """Query requires search_term field."""
        with pytest.raises(ValidationError) as exc_info:
            UserSearchQuery()

        assert "search_term" in str(exc_info.value)

    def test_validates_search_term_min_length(self):
        """Search term must be at least 2 characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserSearchQuery(search_term="a")

        assert "search_term" in str(exc_info.value)

    def test_validates_limit_range(self):
        """Limit must be between 1 and 100."""
        # Valid limits
        for limit in [1, 20, 100]:
            query = UserSearchQuery(search_term="test", limit=limit)
            assert query.limit == limit

        # Invalid limits
        for limit in [0, 101]:
            with pytest.raises(ValidationError) as exc_info:
                UserSearchQuery(search_term="test", limit=limit)
            assert "limit" in str(exc_info.value)

    def test_query_is_immutable(self):
        """Query cannot be modified after creation."""
        query = UserSearchQuery(search_term="john")

        with pytest.raises((ValidationError, AttributeError)):
            query.search_term = "jane"


class TestUserStatsQuery:
    """Tests for UserStatsQuery."""

    def test_creates_query_with_all_fields(self):
        """Query creation succeeds with all fields."""
        tenant_id = uuid4()
        query = UserStatsQuery(
            tenant_id=tenant_id,
            time_period="last_30_days",
        )

        assert query.tenant_id == tenant_id
        assert query.time_period == "last_30_days"

    def test_creates_query_with_defaults(self):
        """Query uses default values for optional fields."""
        query = UserStatsQuery()

        assert query.tenant_id is None
        assert query.time_period == "all_time"  # default

    def test_accepts_various_time_periods(self):
        """Query accepts different time period values."""
        time_periods = [
            "all_time",
            "last_7_days",
            "last_30_days",
            "last_90_days",
            "last_year",
        ]

        for period in time_periods:
            query = UserStatsQuery(time_period=period)
            assert query.time_period == period

    def test_query_is_immutable(self):
        """Query cannot be modified after creation."""
        query = UserStatsQuery(time_period="last_30_days")

        with pytest.raises((ValidationError, AttributeError)):
            query.time_period = "last_7_days"


class TestQueryImmutability:
    """Tests for query immutability (frozen=True)."""

    def test_all_queries_are_frozen(self):
        """All query models should be immutable."""
        queries = [
            UserListQuery(),
            UserDetailQuery(user_id=uuid4()),
            UserSearchQuery(search_term="test"),
            UserStatsQuery(),
        ]

        for query in queries:
            # Verify frozen config
            assert query.model_config.get("frozen") is True

            # Attempt to modify should raise error
            with pytest.raises((ValidationError, AttributeError)):
                # Try to set an arbitrary attribute
                setattr(query, "new_field", "value")
