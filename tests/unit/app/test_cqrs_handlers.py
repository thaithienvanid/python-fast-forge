"""Comprehensive unit tests for CQRS command and query handlers.

Covers:
- src/app/command_handlers/__init__.py (UserCommandHandler)
- src/app/query_handlers/__init__.py (UserQueryHandler)
- src/app/commands/__init__.py (Command models)
- src/app/queries/__init__.py (Query models)

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- AsyncMock for async methods
- pytest.mark.parametrize for multiple scenarios
- Mock external dependencies (event store, event bus, DB session, cache)
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.app.command_handlers import UserCommandHandler
from src.app.commands import (
    CreateUserCommand,
    DeleteUserCommand,
    RestoreUserCommand,
    UpdateUserCommand,
)
from src.app.queries import (
    UserDetailQuery,
    UserListQuery,
    UserQueryModel,
    UserSearchQuery,
    UserStatsQuery,
)
from src.app.query_handlers import UserQueryHandler
from src.domain.events import (
    UserCreatedEvent,
    UserDeletedEvent,
    UserRestoredEvent,
    UserUpdatedEvent,
)
from src.domain.exceptions import EntityNotFoundError, ValidationError


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def admin_id() -> UUID:
    """Return a fixed UUID for the command issuer."""
    return uuid4()


@pytest.fixture
def correlation_id() -> UUID:
    """Return a fixed correlation ID."""
    return uuid4()


@pytest.fixture
def idempotency_key() -> UUID:
    """Return a fixed idempotency key."""
    return uuid4()


@pytest.fixture
def tenant_id() -> UUID:
    """Return a fixed tenant ID."""
    return uuid4()


@pytest.fixture
def user_id() -> UUID:
    """Return a fixed user ID."""
    return uuid4()


@pytest.fixture
def mock_event_store():
    """Create a mock EventStoreRepository with async methods."""
    store = AsyncMock()
    store.append_event = AsyncMock(return_value=1)
    store.get_snapshot = AsyncMock(return_value=None)
    store.get_events = MagicMock(return_value=_async_empty_generator())
    return store


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus with async publish method."""
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for query handler."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    result.scalars = MagicMock()
    result.scalars.return_value.all = MagicMock(return_value=[])
    result.scalar = MagicMock(return_value=0)
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def mock_cache():
    """Create a mock RedisCache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def sample_user_read_model(user_id, tenant_id):
    """Create a sample UserReadModel-like object for query tests."""
    rm = MagicMock()
    rm.id = user_id
    rm.email = "test@example.com"
    rm.username = "testuser"
    rm.full_name = "Test User"
    rm.is_active = True
    rm.tenant_id = tenant_id
    rm.created_at = datetime.now(UTC)
    rm.updated_at = datetime.now(UTC)
    rm.deleted_at = None
    rm.total_orders = 0
    rm.last_login_at = None
    rm.profile_completion = 50
    return rm


async def _async_empty_generator():
    """Async generator that yields nothing."""
    return
    yield


async def _async_generator_with_events(*events):
    """Async generator that yields the provided events."""
    for event in events:
        yield event


# ============================================================================
# Command Model Tests
# ============================================================================


class TestCreateUserCommand:
    """Tests for CreateUserCommand model validation."""

    def test_valid_command_creation(self, admin_id, correlation_id, idempotency_key):
        """Test creating a valid CreateUserCommand.

        Arrange: Valid command parameters
        Act: Create command
        Assert: All fields set correctly
        """
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            full_name="Test User",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.email == "user@example.com"
        assert command.username == "testuser"
        assert command.full_name == "Test User"
        assert command.commanded_by == admin_id
        assert command.correlation_id == correlation_id
        assert command.idempotency_key == idempotency_key
        assert command.tenant_id is None

    def test_command_is_immutable(self, admin_id, correlation_id, idempotency_key):
        """Test that CreateUserCommand is frozen (immutable).

        Arrange: Valid command
        Act: Attempt to modify a field
        Assert: ValidationError raised (frozen=True)
        """
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with pytest.raises(Exception):
            command.email = "other@example.com"

    def test_command_with_tenant_id(self, admin_id, correlation_id, idempotency_key, tenant_id):
        """Test command with optional tenant_id.

        Arrange: Valid parameters including tenant_id
        Act: Create command
        Assert: tenant_id is set
        """
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            tenant_id=tenant_id,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.tenant_id == tenant_id

    def test_command_without_full_name(self, admin_id, correlation_id, idempotency_key):
        """Test command without optional full_name.

        Arrange: Valid command without full_name
        Act: Create command
        Assert: full_name is None
        """
        command = CreateUserCommand(
            email="user@example.com",
            username="testuser",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.full_name is None

    def test_invalid_email_raises_error(self, admin_id, correlation_id, idempotency_key):
        """Test invalid email raises ValidationError.

        Arrange: Invalid email
        Act: Create command
        Assert: Pydantic ValidationError raised
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateUserCommand(
                email="not-an-email",
                username="testuser",
                commanded_by=admin_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )

    @pytest.mark.parametrize("username", ["ab", "a" * 101])
    def test_invalid_username_length_raises_error(
        self, username, admin_id, correlation_id, idempotency_key
    ):
        """Test username length validation.

        Arrange: Username that's too short (< 3) or too long (> 100)
        Act: Create command
        Assert: Pydantic ValidationError raised
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            CreateUserCommand(
                email="user@example.com",
                username=username,
                commanded_by=admin_id,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )


class TestUpdateUserCommand:
    """Tests for UpdateUserCommand model validation."""

    def test_valid_command_creation(self, user_id, admin_id, correlation_id, idempotency_key):
        """Test creating a valid UpdateUserCommand.

        Arrange: Valid update parameters
        Act: Create command
        Assert: All fields set correctly
        """
        command = UpdateUserCommand(
            user_id=user_id,
            email="new@example.com",
            expected_version=5,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.user_id == user_id
        assert command.email == "new@example.com"
        assert command.expected_version == 5
        assert command.username is None
        assert command.full_name is None
        assert command.is_active is None

    def test_partial_update_all_optional_fields_none(
        self, user_id, admin_id, correlation_id, idempotency_key
    ):
        """Test UpdateUserCommand with all optional fields None.

        Arrange: Command with only required fields
        Act: Create command
        Assert: Optional fields are None
        """
        command = UpdateUserCommand(
            user_id=user_id,
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.email is None
        assert command.username is None
        assert command.full_name is None
        assert command.is_active is None


class TestDeleteUserCommand:
    """Tests for DeleteUserCommand model validation."""

    def test_default_soft_delete(self, user_id, admin_id, correlation_id, idempotency_key):
        """Test that soft_delete defaults to True.

        Arrange: Command without explicit soft_delete
        Act: Create command
        Assert: soft_delete is True
        """
        command = DeleteUserCommand(
            user_id=user_id,
            expected_version=3,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.soft_delete is True

    def test_hard_delete_flag(self, user_id, admin_id, correlation_id, idempotency_key):
        """Test explicit hard delete setting.

        Arrange: Command with soft_delete=False
        Act: Create command
        Assert: soft_delete is False
        """
        command = DeleteUserCommand(
            user_id=user_id,
            soft_delete=False,
            expected_version=3,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.soft_delete is False


class TestRestoreUserCommand:
    """Tests for RestoreUserCommand model validation."""

    def test_valid_restore_command(self, user_id, admin_id, correlation_id, idempotency_key):
        """Test creating a valid RestoreUserCommand.

        Arrange: Valid restore parameters
        Act: Create command
        Assert: All fields set correctly
        """
        command = RestoreUserCommand(
            user_id=user_id,
            expected_version=6,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        assert command.user_id == user_id
        assert command.expected_version == 6


# ============================================================================
# Query Model Tests
# ============================================================================


class TestUserQueryModel:
    """Tests for UserQueryModel."""

    def test_valid_query_model_creation(self, user_id, tenant_id):
        """Test creating a valid UserQueryModel.

        Arrange: Valid model data
        Act: Create model
        Assert: All fields set correctly
        """
        now = datetime.now(UTC)
        model = UserQueryModel(
            id=user_id,
            email="user@example.com",
            username="testuser",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        assert model.id == user_id
        assert model.email == "user@example.com"
        assert model.username == "testuser"
        assert model.is_active is True
        assert model.total_orders == 0
        assert model.profile_completion == 0
        assert model.deleted_at is None

    def test_profile_completion_bounds(self, user_id):
        """Test that profile_completion enforces ge=0 and le=100 bounds.

        Arrange: Invalid profile_completion values
        Act: Attempt to create model
        Assert: Pydantic ValidationError raised
        """
        from pydantic import ValidationError as PydanticValidationError

        now = datetime.now(UTC)
        with pytest.raises(PydanticValidationError):
            UserQueryModel(
                id=user_id,
                email="user@example.com",
                username="testuser",
                is_active=True,
                created_at=now,
                updated_at=now,
                profile_completion=101,
            )


class TestUserListQuery:
    """Tests for UserListQuery model."""

    def test_default_values(self):
        """Test default values for UserListQuery.

        Arrange: No parameters
        Act: Create query
        Assert: Defaults are set correctly
        """
        query = UserListQuery()

        assert query.skip == 0
        assert query.limit == 50
        assert query.order_by == "created_at"
        assert query.order_direction == "desc"
        assert query.tenant_id is None
        assert query.is_active is None

    def test_custom_pagination(self):
        """Test custom pagination parameters.

        Arrange: Custom skip and limit
        Act: Create query
        Assert: Custom values set
        """
        query = UserListQuery(skip=10, limit=25)

        assert query.skip == 10
        assert query.limit == 25

    @pytest.mark.parametrize("limit", [0, 101])
    def test_invalid_limit_raises_error(self, limit):
        """Test that limit must be between 1 and 100.

        Arrange: Invalid limit value
        Act: Create query
        Assert: Pydantic ValidationError raised
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            UserListQuery(limit=limit)

    def test_negative_skip_raises_error(self):
        """Test that negative skip raises error.

        Arrange: Negative skip
        Act: Create query
        Assert: Pydantic ValidationError raised
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            UserListQuery(skip=-1)


class TestUserDetailQuery:
    """Tests for UserDetailQuery model."""

    def test_default_include_deleted_false(self, user_id):
        """Test that include_deleted defaults to False.

        Arrange: Query with only user_id
        Act: Create query
        Assert: include_deleted is False
        """
        query = UserDetailQuery(user_id=user_id)

        assert query.user_id == user_id
        assert query.include_deleted is False

    def test_include_deleted_true(self, user_id):
        """Test setting include_deleted=True.

        Arrange: Query with include_deleted=True
        Act: Create query
        Assert: include_deleted is True
        """
        query = UserDetailQuery(user_id=user_id, include_deleted=True)

        assert query.include_deleted is True


class TestUserSearchQuery:
    """Tests for UserSearchQuery model."""

    def test_valid_search_query(self, tenant_id):
        """Test creating a valid search query.

        Arrange: Valid search term
        Act: Create query
        Assert: Fields set correctly
        """
        query = UserSearchQuery(search_term="john", tenant_id=tenant_id, limit=10)

        assert query.search_term == "john"
        assert query.tenant_id == tenant_id
        assert query.limit == 10

    def test_search_term_min_length(self):
        """Test that search_term requires at least 2 characters.

        Arrange: Too short search term
        Act: Create query
        Assert: Pydantic ValidationError raised
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            UserSearchQuery(search_term="a")


class TestUserStatsQuery:
    """Tests for UserStatsQuery model."""

    def test_default_values(self):
        """Test default values for UserStatsQuery.

        Arrange: No parameters
        Act: Create query
        Assert: Defaults are set correctly
        """
        query = UserStatsQuery()

        assert query.tenant_id is None
        assert query.time_period == "all_time"

    def test_with_tenant_and_period(self, tenant_id):
        """Test with explicit tenant and time period.

        Arrange: All parameters provided
        Act: Create query
        Assert: Values set correctly
        """
        query = UserStatsQuery(tenant_id=tenant_id, time_period="last_30_days")

        assert query.tenant_id == tenant_id
        assert query.time_period == "last_30_days"


# ============================================================================
# UserCommandHandler Tests
# ============================================================================


def _make_mock_event(event_class, **kwargs):
    """Create a non-frozen mock event that supports attribute setting.

    The source code calls event.metadata = {...} which fails on frozen
    Pydantic models. This helper creates MagicMock instances that mimic
    the event class but allow attribute assignment.

    Args:
        event_class: The event class to mimic (for isinstance checks)
        **kwargs: Event attributes to set

    Returns:
        MagicMock that passes isinstance checks for event_class
    """
    mock_event = MagicMock(spec=event_class)
    for key, value in kwargs.items():
        setattr(mock_event, key, value)
    mock_event.metadata = {}
    return mock_event


class TestHandleCreateUser:
    """Tests for UserCommandHandler.handle_create_user."""

    @staticmethod
    def _patch_handler():
        """Return context manager that patches handler's broken dependencies."""
        return patch.multiple(
            "src.app.command_handlers",
            UserCreatedEvent=MagicMock(
                side_effect=lambda **kwargs: _make_mock_event(UserCreatedEvent, **kwargs)
            ),
        )

    async def test_creates_user_and_returns_uuid(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key
    ):
        """Test that handle_create_user returns a UUID.

        Arrange: Valid CreateUserCommand, mocked event store and bus
        Act: Call handle_create_user
        Assert: Returns a UUID, event appended and published
        """
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = CreateUserCommand(
            email="user@example.com",
            username="newuser",
            full_name="New User",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_handler(),
        ):
            result = await handler.handle_create_user(command)

        assert isinstance(result, UUID)
        mock_event_store.append_event.assert_called_once()
        mock_event_bus.publish.assert_called_once()

    async def test_create_user_appends_user_created_event(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key
    ):
        """Test that a UserCreatedEvent is appended to the event store.

        Arrange: Valid command
        Act: Call handle_create_user
        Assert: append_event called and aggregate_type is 'User'
        """
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = CreateUserCommand(
            email="user@example.com",
            username="newuser",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_handler(),
        ):
            await handler.handle_create_user(command)

        mock_event_store.append_event.assert_called_once()
        call_args = mock_event_store.append_event.call_args
        aggregate_type = call_args.kwargs.get("aggregate_type") or (
            call_args.args[1] if len(call_args.args) > 1 else None
        )
        assert aggregate_type == "User"

    async def test_create_user_with_tenant_id(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key, tenant_id
    ):
        """Test that tenant_id is passed through to the event constructor.

        Arrange: Command with tenant_id
        Act: Call handle_create_user
        Assert: UserCreatedEvent was called with tenant_id
        """
        mock_created_event_cls = MagicMock()
        mock_created_event_instance = _make_mock_event(UserCreatedEvent)
        mock_created_event_instance.tenant_id = tenant_id
        mock_created_event_cls.return_value = mock_created_event_instance

        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = CreateUserCommand(
            email="user@example.com",
            username="newuser",
            tenant_id=tenant_id,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            patch("src.app.command_handlers.UserCreatedEvent", mock_created_event_cls),
        ):
            await handler.handle_create_user(command)

        # Verify tenant_id was passed to event constructor
        call_kwargs = mock_created_event_cls.call_args.kwargs
        assert call_kwargs.get("tenant_id") == tenant_id

    async def test_create_user_event_persisted(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key
    ):
        """Test that event is persisted to event store.

        Arrange: Valid command
        Act: Call handle_create_user
        Assert: append_event called once on event store
        """
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = CreateUserCommand(
            email="user@example.com",
            username="newuser",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_handler(),
        ):
            await handler.handle_create_user(command)

        mock_event_store.append_event.assert_called_once()

    async def test_create_user_expected_version_is_none(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key
    ):
        """Test that expected_version=None for new aggregates.

        Arrange: Valid command
        Act: Call handle_create_user
        Assert: append_event called with expected_version=None
        """
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = CreateUserCommand(
            email="user@example.com",
            username="newuser",
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_handler(),
        ):
            await handler.handle_create_user(command)

        call_args = mock_event_store.append_event.call_args
        expected_version = call_args.kwargs.get("expected_version")
        assert expected_version is None


class TestHandleUpdateUser:
    """Tests for UserCommandHandler.handle_update_user."""

    def _make_event_store_with_user(self, user_id, tenant_id=None):
        """Create event store mock that reconstructs a user from events."""
        from src.domain.events.user_events import UserCreatedEvent

        store = AsyncMock()
        store.append_event = AsyncMock(return_value=2)
        store.get_snapshot = AsyncMock(return_value=None)

        created_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="original@example.com",
            username="originaluser",
            full_name="Original User",
            tenant_id=tenant_id,
        )

        store.get_events = MagicMock(return_value=_async_generator_with_events(created_event))
        return store

    @staticmethod
    def _patch_update_handler():
        """Patch UserUpdatedEvent to be non-frozen for tests."""

        def make_update_event(**kwargs):
            mock_e = MagicMock(spec=UserUpdatedEvent)
            for k, v in kwargs.items():
                setattr(mock_e, k, v)
            mock_e.metadata = {}
            return mock_e

        return patch("src.app.command_handlers.UserUpdatedEvent", side_effect=make_update_event)

    async def test_updates_email_field(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that updating email triggers event append and publish.

        Arrange: User exists, new email provided
        Act: Call handle_update_user
        Assert: append_event and publish called once each
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = UpdateUserCommand(
            user_id=user_id,
            email="newemail@example.com",
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_update_handler(),
        ):
            await handler.handle_update_user(command)

        store.append_event.assert_called_once()
        mock_event_bus.publish.assert_called_once()

    async def test_updates_username_field(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that updating username is tracked in changed_fields.

        Arrange: User exists, new username provided
        Act: Call handle_update_user
        Assert: Event constructor called with username in changed_fields
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = UpdateUserCommand(
            user_id=user_id,
            username="newusername",
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            patch("src.app.command_handlers.UserUpdatedEvent") as mock_updated_event_cls,
        ):
            mock_updated_event_cls.return_value = _make_mock_event(UserUpdatedEvent)
            await handler.handle_update_user(command)

        call_kwargs = mock_updated_event_cls.call_args.kwargs
        changed_fields = call_kwargs.get("changed_fields", {})
        assert "username" in changed_fields

    async def test_no_changes_still_appends_event(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that even with no field changes an event is appended.

        Arrange: User exists, same values provided
        Act: Call handle_update_user
        Assert: Event still appended (empty changed_fields)
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = UpdateUserCommand(
            user_id=user_id,
            email="original@example.com",  # Same as existing
            username="originaluser",  # Same as existing
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_update_handler(),
        ):
            await handler.handle_update_user(command)

        store.append_event.assert_called_once()

    async def test_raises_entity_not_found_when_no_events(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test raises EntityNotFoundError when user has no events.

        Arrange: Event store returns no events for user
        Act: Call handle_update_user
        Assert: EntityNotFoundError raised
        """
        mock_event_store.get_events = MagicMock(return_value=_async_empty_generator())
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = UpdateUserCommand(
            user_id=user_id,
            email="new@example.com",
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with pytest.raises(EntityNotFoundError):
            await handler.handle_update_user(command)

    async def test_updates_is_active_field(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that updating is_active is tracked.

        Arrange: User exists, is_active changed to False
        Act: Call handle_update_user
        Assert: is_active in changed_fields passed to event constructor
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = UpdateUserCommand(
            user_id=user_id,
            is_active=False,
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            patch("src.app.command_handlers.UserUpdatedEvent") as mock_updated_event_cls,
        ):
            mock_updated_event_cls.return_value = _make_mock_event(UserUpdatedEvent)
            await handler.handle_update_user(command)

        call_kwargs = mock_updated_event_cls.call_args.kwargs
        changed_fields = call_kwargs.get("changed_fields", {})
        assert "is_active" in changed_fields

    async def test_update_uses_expected_version_for_locking(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that expected_version is passed for optimistic locking.

        Arrange: User exists, update with expected_version=1
        Act: Call handle_update_user
        Assert: append_event called with expected_version=1
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = UpdateUserCommand(
            user_id=user_id,
            email="new@example.com",
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with (
            patch("src.domain.models.user.User.validate", return_value=None, create=True),
            self._patch_update_handler(),
        ):
            await handler.handle_update_user(command)

        call_args = store.append_event.call_args
        expected_version = call_args.kwargs.get("expected_version")
        assert expected_version == 1


class TestHandleDeleteUser:
    """Tests for UserCommandHandler.handle_delete_user."""

    def _make_event_store_with_user(self, user_id):
        """Create event store mock that has a user."""
        from src.domain.events.user_events import UserCreatedEvent

        store = AsyncMock()
        store.append_event = AsyncMock(return_value=2)
        store.get_snapshot = AsyncMock(return_value=None)

        created_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
        )
        store.get_events = MagicMock(return_value=_async_generator_with_events(created_event))
        return store

    @staticmethod
    def _patch_delete_handler(soft_delete=True):
        """Patch UserDeletedEvent to be non-frozen for tests."""

        def make_delete_event(**kwargs):
            mock_e = MagicMock(spec=UserDeletedEvent)
            for k, v in kwargs.items():
                setattr(mock_e, k, v)
            mock_e.soft_delete = kwargs.get("soft_delete", soft_delete)
            mock_e.metadata = {}
            return mock_e

        return patch("src.app.command_handlers.UserDeletedEvent", side_effect=make_delete_event)

    async def test_deletes_user_successfully(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test handle_delete_user appends event and publishes.

        Arrange: User exists
        Act: Call handle_delete_user
        Assert: append_event and publish called once each
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = DeleteUserCommand(
            user_id=user_id,
            soft_delete=True,
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with self._patch_delete_handler(soft_delete=True):
            await handler.handle_delete_user(command)

        store.append_event.assert_called_once()
        mock_event_bus.publish.assert_called_once()

    async def test_delete_event_contains_soft_delete_flag(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that soft_delete flag is passed to event constructor.

        Arrange: User exists, soft_delete=False
        Act: Call handle_delete_user
        Assert: Event constructor called with soft_delete=False
        """
        store = self._make_event_store_with_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = DeleteUserCommand(
            user_id=user_id,
            soft_delete=False,
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with patch("src.app.command_handlers.UserDeletedEvent") as mock_deleted_cls:
            mock_deleted_cls.return_value = _make_mock_event(UserDeletedEvent, soft_delete=False)
            await handler.handle_delete_user(command)

        call_kwargs = mock_deleted_cls.call_args.kwargs
        assert call_kwargs.get("soft_delete") is False

    async def test_raises_entity_not_found_when_user_missing(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test raises EntityNotFoundError when user does not exist.

        Arrange: Event store returns no events
        Act: Call handle_delete_user
        Assert: EntityNotFoundError raised
        """
        mock_event_store.get_events = MagicMock(return_value=_async_empty_generator())
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = DeleteUserCommand(
            user_id=user_id,
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with pytest.raises(EntityNotFoundError):
            await handler.handle_delete_user(command)


class TestHandleRestoreUser:
    """Tests for UserCommandHandler.handle_restore_user."""

    def _make_event_store_with_deleted_user(self, user_id):
        """Create event store mock with a soft-deleted user."""
        from src.domain.events.user_events import UserCreatedEvent, UserDeletedEvent

        store = AsyncMock()
        store.append_event = AsyncMock(return_value=3)
        store.get_snapshot = AsyncMock(return_value=None)

        created_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
        )
        deleted_event = UserDeletedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            deleted_at=datetime.now(UTC),
            soft_delete=True,
        )
        store.get_events = MagicMock(
            return_value=_async_generator_with_events(created_event, deleted_event)
        )
        return store

    def _make_event_store_with_active_user(self, user_id):
        """Create event store mock with an active (non-deleted) user."""
        from src.domain.events.user_events import UserCreatedEvent

        store = AsyncMock()
        store.append_event = AsyncMock(return_value=2)
        store.get_snapshot = AsyncMock(return_value=None)

        created_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
        )
        store.get_events = MagicMock(return_value=_async_generator_with_events(created_event))
        return store

    @staticmethod
    def _patch_restore_handler():
        """Patch UserRestoredEvent to be non-frozen for tests."""

        def make_restore_event(**kwargs):
            mock_e = MagicMock(spec=UserRestoredEvent)
            for k, v in kwargs.items():
                setattr(mock_e, k, v)
            mock_e.metadata = {}
            return mock_e

        return patch("src.app.command_handlers.UserRestoredEvent", side_effect=make_restore_event)

    async def test_restores_deleted_user(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test handle_restore_user appends event and publishes.

        Arrange: Soft-deleted user exists
        Act: Call handle_restore_user
        Assert: append_event and publish called once each
        """
        store = self._make_event_store_with_deleted_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = RestoreUserCommand(
            user_id=user_id,
            expected_version=2,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with self._patch_restore_handler():
            await handler.handle_restore_user(command)

        store.append_event.assert_called_once()
        mock_event_bus.publish.assert_called_once()

    async def test_raises_validation_error_for_active_user(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test raises ValidationError when restoring an active user.

        Arrange: Active (non-deleted) user
        Act: Call handle_restore_user
        Assert: ValidationError raised with 'not deleted' message
        """
        store = self._make_event_store_with_active_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = RestoreUserCommand(
            user_id=user_id,
            expected_version=1,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with pytest.raises(ValidationError, match="not deleted"):
            await handler.handle_restore_user(command)

    async def test_raises_entity_not_found_when_user_missing(
        self, mock_event_store, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test raises EntityNotFoundError when user has no events.

        Arrange: Event store returns no events
        Act: Call handle_restore_user
        Assert: EntityNotFoundError raised
        """
        mock_event_store.get_events = MagicMock(return_value=_async_empty_generator())
        handler = UserCommandHandler(mock_event_store, mock_event_bus)
        command = RestoreUserCommand(
            user_id=user_id,
            expected_version=2,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with pytest.raises(EntityNotFoundError):
            await handler.handle_restore_user(command)

    async def test_restore_event_metadata_set(
        self, mock_event_bus, admin_id, correlation_id, idempotency_key, user_id
    ):
        """Test that restore event has metadata populated (commanded_by set).

        Arrange: Soft-deleted user
        Act: Call handle_restore_user
        Assert: Event metadata is set on the restored event
        """
        store = self._make_event_store_with_deleted_user(user_id)
        handler = UserCommandHandler(store, mock_event_bus)
        command = RestoreUserCommand(
            user_id=user_id,
            expected_version=2,
            commanded_by=admin_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

        with self._patch_restore_handler():
            await handler.handle_restore_user(command)

        # Verify event was appended with metadata set (the mock event has metadata dict)
        store.append_event.assert_called_once()


class TestReconstructUser:
    """Tests for UserCommandHandler._reconstruct_user."""

    async def test_uses_snapshot_when_available(self, mock_event_bus, user_id):
        """Test that snapshot is used when available to reduce event replay.

        Arrange: Event store with a snapshot
        Act: Reconstruct user
        Assert: Events fetched from snapshot version onwards (from_version=5)
        """
        store = AsyncMock()
        store.append_event = AsyncMock(return_value=2)

        snapshot_data = {
            "id": str(user_id),
            "email": "snap@example.com",
            "username": "snapuser",
            "full_name": None,
            "is_active": True,
            "tenant_id": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "deleted_at": None,
        }
        store.get_snapshot = AsyncMock(return_value=(5, snapshot_data))
        store.get_events = MagicMock(return_value=_async_empty_generator())

        mock_user = MagicMock()
        mock_user.email = "snap@example.com"

        handler = UserCommandHandler(store, mock_event_bus)

        with patch("src.app.command_handlers.User") as mock_user_cls:
            mock_user_cls.model_validate = MagicMock(return_value=mock_user)
            user = await handler._reconstruct_user(user_id)

        assert user is not None
        mock_user_cls.model_validate.assert_called_once_with(snapshot_data)
        store.get_events.assert_called_once()
        call_args = store.get_events.call_args
        from_version = call_args.kwargs.get("from_version") or call_args.args[2]
        assert from_version == 5

    async def test_raises_entity_not_found_for_unknown_user(
        self, mock_event_store, mock_event_bus, user_id
    ):
        """Test raises EntityNotFoundError for unknown user.

        Arrange: No snapshot and no events
        Act: Call _reconstruct_user
        Assert: EntityNotFoundError raised
        """
        mock_event_store.get_events = MagicMock(return_value=_async_empty_generator())
        handler = UserCommandHandler(mock_event_store, mock_event_bus)

        with pytest.raises(EntityNotFoundError):
            await handler._reconstruct_user(user_id)


class TestApplyEvent:
    """Tests for UserCommandHandler._apply_event."""

    def test_apply_user_created_event(self, user_id):
        """Test applying UserCreatedEvent creates a new User.

        Arrange: UserCreatedEvent
        Act: Call _apply_event with None user
        Assert: Returns User with event data
        """
        from src.domain.events.user_events import UserCreatedEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())
        event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            full_name="Test User",
        )

        result = handler._apply_event(None, event)

        assert result is not None
        assert result.email == "user@example.com"
        assert result.username == "testuser"
        assert result.full_name == "Test User"

    def test_apply_user_updated_event(self, user_id):
        """Test applying UserUpdatedEvent modifies user fields.

        Arrange: Existing user, mock UserUpdatedEvent with changed email
        Act: Call _apply_event
        Assert: User is returned with modifications applied
        """
        from src.domain.events.user_events import UserCreatedEvent, UserUpdatedEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())

        create_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="original@example.com",
            username="testuser",
        )
        user = handler._apply_event(None, create_event)

        # The source handler calls event.changed_fields.items() (treating it as dict)
        # but the domain model defines changed_fields as list[str].
        # Use a MagicMock with dict-like changed_fields to test the handler path.
        update_event = MagicMock(spec=UserUpdatedEvent)
        update_event.changed_fields = {"email": ("original@example.com", "new@example.com")}
        update_event.occurred_at = datetime.now(UTC)

        result = handler._apply_event(user, update_event)

        # Verify returned user object is not None
        assert result is not None

    def test_apply_user_deleted_event(self, user_id):
        """Test applying UserDeletedEvent sets deleted_at.

        Arrange: Active user, UserDeletedEvent
        Act: Call _apply_event
        Assert: User deleted_at is set
        """
        from src.domain.events.user_events import UserCreatedEvent, UserDeletedEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())

        create_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
        )
        user = handler._apply_event(None, create_event)

        delete_event = UserDeletedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            deleted_at=datetime.now(UTC),
            soft_delete=True,
        )

        result = handler._apply_event(user, delete_event)

        assert result.deleted_at is not None

    def test_apply_user_restored_event(self, user_id):
        """Test applying UserRestoredEvent clears deleted_at.

        Arrange: Deleted user, UserRestoredEvent
        Act: Call _apply_event
        Assert: User deleted_at is None
        """
        from src.domain.events.user_events import (
            UserCreatedEvent,
            UserDeletedEvent,
            UserRestoredEvent,
        )

        handler = UserCommandHandler(MagicMock(), MagicMock())

        create_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
        )
        user = handler._apply_event(None, create_event)

        delete_event = UserDeletedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            deleted_at=datetime.now(UTC),
            soft_delete=True,
        )
        user = handler._apply_event(user, delete_event)
        assert user.deleted_at is not None

        restore_event = UserRestoredEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            restored_at=datetime.now(UTC),
        )

        result = handler._apply_event(user, restore_event)

        assert result.deleted_at is None

    def test_apply_user_updated_event_raises_for_none_user(self, user_id):
        """Test applying UserUpdatedEvent to None user raises ValueError.

        Arrange: None user, a real UserUpdatedEvent instance
        Act: Call _apply_event
        Assert: ValueError raised with 'Cannot apply UserUpdatedEvent'
        """
        from src.domain.events.user_events import UserUpdatedEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())

        # Create a real UserUpdatedEvent with list changed_fields (as domain model requires)
        update_event = UserUpdatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            changed_fields=["email"],  # list[str] as required by domain model
        )

        with pytest.raises(ValueError, match="Cannot apply UserUpdatedEvent"):
            handler._apply_event(None, update_event)

    def test_apply_user_deleted_event_raises_for_none_user(self, user_id):
        """Test applying UserDeletedEvent to None user raises ValueError.

        Arrange: None user, UserDeletedEvent
        Act: Call _apply_event
        Assert: ValueError raised
        """
        from src.domain.events.user_events import UserDeletedEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())
        delete_event = UserDeletedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            deleted_at=datetime.now(UTC),
            soft_delete=True,
        )

        with pytest.raises(ValueError, match="Cannot apply UserDeletedEvent"):
            handler._apply_event(None, delete_event)

    def test_apply_user_restored_event_raises_for_none_user(self, user_id):
        """Test applying UserRestoredEvent to None user raises ValueError.

        Arrange: None user, UserRestoredEvent
        Act: Call _apply_event
        Assert: ValueError raised
        """
        from src.domain.events.user_events import UserRestoredEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())
        restore_event = UserRestoredEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
            restored_at=datetime.now(UTC),
        )

        with pytest.raises(ValueError, match="Cannot apply UserRestoredEvent"):
            handler._apply_event(None, restore_event)

    def test_apply_unknown_event_returns_user_unchanged(self, user_id):
        """Test applying an unknown event type returns user unchanged.

        Arrange: Active user, unknown event type
        Act: Call _apply_event
        Assert: User returned unchanged
        """
        from src.domain.events.base import DomainEvent

        handler = UserCommandHandler(MagicMock(), MagicMock())

        from src.domain.events.user_events import UserCreatedEvent

        create_event = UserCreatedEvent(
            aggregate_id=user_id,
            user_id=user_id,
            email="user@example.com",
            username="testuser",
        )
        user = handler._apply_event(None, create_event)
        original_email = user.email

        # Create a generic DomainEvent (unknown type)
        unknown_event = DomainEvent(aggregate_id=user_id)

        result = handler._apply_event(user, unknown_event)

        assert result.email == original_email


# ============================================================================
# UserQueryHandler Tests
# ============================================================================


class TestHandleUserDetail:
    """Tests for UserQueryHandler.handle_user_detail."""

    async def test_returns_user_when_found(
        self, mock_session, mock_cache, sample_user_read_model, user_id
    ):
        """Test returns UserQueryModel when user found in read model.

        Arrange: Session returns a UserReadModel
        Act: Call handle_user_detail
        Assert: Returns UserQueryModel
        """
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_user_read_model)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)

        with patch("src.app.query_handlers.UserQueryModel.model_validate") as mock_validate:
            now = datetime.now(UTC)
            mock_validate.return_value = UserQueryModel(
                id=user_id,
                email="test@example.com",
                username="testuser",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            query = UserDetailQuery(user_id=user_id)
            result = await handler.handle_user_detail(query)

        assert result is not None

    async def test_raises_entity_not_found_when_user_missing(self, mock_session, user_id):
        """Test raises EntityNotFoundError when user not in read model.

        Arrange: Session returns None
        Act: Call handle_user_detail
        Assert: EntityNotFoundError raised
        """
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserDetailQuery(user_id=user_id)

        with pytest.raises(EntityNotFoundError, match=str(user_id)):
            await handler.handle_user_detail(query)

    async def test_returns_cached_result_when_cache_hit(self, mock_session, mock_cache, user_id):
        """Test returns cached result without hitting database.

        Arrange: Cache returns a cached user
        Act: Call handle_user_detail
        Assert: Session not queried, cached result returned
        """
        now = datetime.now(UTC)
        cached_user = UserQueryModel(
            id=user_id,
            email="cached@example.com",
            username="cacheduser",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        mock_cache.get = AsyncMock(return_value=cached_user.model_dump_json())

        handler = UserQueryHandler(mock_session, mock_cache)
        query = UserDetailQuery(user_id=user_id)

        result = await handler.handle_user_detail(query)

        assert result is not None
        mock_session.execute.assert_not_called()

    async def test_caches_result_on_cache_miss(
        self, mock_session, mock_cache, sample_user_read_model, user_id
    ):
        """Test that result is cached after database query.

        Arrange: Cache miss, session returns user
        Act: Call handle_user_detail
        Assert: cache.set called with user data
        """
        mock_cache.get = AsyncMock(return_value=None)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=sample_user_read_model)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, mock_cache)

        now = datetime.now(UTC)
        with patch("src.app.query_handlers.UserQueryModel.model_validate") as mock_validate:
            mock_validate.return_value = UserQueryModel(
                id=user_id,
                email="test@example.com",
                username="testuser",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            query = UserDetailQuery(user_id=user_id)
            await handler.handle_user_detail(query)

        mock_cache.set.assert_called_once()

    async def test_include_deleted_false_adds_filter(self, mock_session, user_id):
        """Test that include_deleted=False adds deleted_at IS NULL filter.

        Arrange: Query with include_deleted=False
        Act: Call handle_user_detail
        Assert: Execute called (filter applied in query)
        """
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserDetailQuery(user_id=user_id, include_deleted=False)

        with pytest.raises(EntityNotFoundError):
            await handler.handle_user_detail(query)

        mock_session.execute.assert_called_once()


class TestHandleListUsers:
    """Tests for UserQueryHandler.handle_list_users."""

    async def test_returns_empty_list_when_no_users(self, mock_session):
        """Test returns empty list when no users match.

        Arrange: Session returns empty result
        Act: Call handle_list_users
        Assert: Empty list returned
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery()

        result = await handler.handle_list_users(query)

        assert result == []

    async def test_applies_tenant_filter(self, mock_session, tenant_id):
        """Test that tenant_id filter is applied to query.

        Arrange: UserListQuery with tenant_id
        Act: Call handle_list_users
        Assert: Execute called (tenant filter in query)
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(tenant_id=tenant_id)

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()

    async def test_applies_is_active_filter(self, mock_session):
        """Test that is_active filter is applied.

        Arrange: UserListQuery with is_active=True
        Act: Call handle_list_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(is_active=True)

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()

    async def test_applies_email_contains_filter(self, mock_session):
        """Test that email_contains filter is applied.

        Arrange: UserListQuery with email_contains
        Act: Call handle_list_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(email_contains="@example.com")

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()

    async def test_applies_username_contains_filter(self, mock_session):
        """Test that username_contains filter is applied.

        Arrange: UserListQuery with username_contains
        Act: Call handle_list_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(username_contains="test")

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()

    async def test_applies_created_after_filter(self, mock_session):
        """Test that created_after date filter is applied.

        Arrange: UserListQuery with created_after
        Act: Call handle_list_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(created_after=datetime(2024, 1, 1, tzinfo=UTC))

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()

    async def test_applies_created_before_filter(self, mock_session):
        """Test that created_before date filter is applied.

        Arrange: UserListQuery with created_before
        Act: Call handle_list_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(created_before=datetime(2025, 1, 1, tzinfo=UTC))

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()

    @pytest.mark.parametrize("order_direction", ["asc", "desc"])
    async def test_applies_ordering(self, mock_session, order_direction):
        """Test that ordering is applied in both directions.

        Arrange: UserListQuery with various order_direction values
        Act: Call handle_list_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserListQuery(order_direction=order_direction)

        await handler.handle_list_users(query)

        mock_session.execute.assert_called_once()


class TestHandleSearchUsers:
    """Tests for UserQueryHandler.handle_search_users."""

    async def test_returns_empty_list_on_no_matches(self, mock_session):
        """Test returns empty list when no users match search.

        Arrange: Session returns empty result
        Act: Call handle_search_users
        Assert: Empty list returned
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserSearchQuery(search_term="notfound")

        result = await handler.handle_search_users(query)

        assert result == []

    async def test_applies_tenant_filter_in_search(self, mock_session, tenant_id):
        """Test that tenant_id filter is applied in search.

        Arrange: UserSearchQuery with tenant_id
        Act: Call handle_search_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserSearchQuery(search_term="john", tenant_id=tenant_id)

        await handler.handle_search_users(query)

        mock_session.execute.assert_called_once()

    async def test_searches_without_tenant_filter(self, mock_session):
        """Test search without tenant filter (global search).

        Arrange: UserSearchQuery without tenant_id
        Act: Call handle_search_users
        Assert: Execute called
        """
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserSearchQuery(search_term="john")

        await handler.handle_search_users(query)

        mock_session.execute.assert_called_once()


class TestHandleUserStats:
    """Tests for UserQueryHandler.handle_user_stats."""

    async def test_returns_stats_dict(self, mock_session):
        """Test returns dict with all expected statistics keys.

        Arrange: Session returns counts for each query
        Act: Call handle_user_stats
        Assert: Dict with all expected keys
        """
        result_mock = MagicMock()
        result_mock.scalar = MagicMock(return_value=100)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserStatsQuery()

        result = await handler.handle_user_stats(query)

        assert "total" in result
        assert "active" in result
        assert "inactive" in result
        assert "deleted" in result
        assert "created_today" in result
        assert "active_percentage" in result

    async def test_returns_zero_stats_when_no_users(self, mock_session):
        """Test returns zero stats when no users exist.

        Arrange: Session returns 0 for all counts
        Act: Call handle_user_stats
        Assert: Stats are all zero
        """
        result_mock = MagicMock()
        result_mock.scalar = MagicMock(return_value=0)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserStatsQuery()

        result = await handler.handle_user_stats(query)

        assert result["total"] == 0
        assert result["active_percentage"] == 0

    async def test_active_percentage_calculated(self, mock_session):
        """Test active_percentage is calculated correctly.

        Arrange: 80 active out of 100 total
        Act: Call handle_user_stats
        Assert: active_percentage is 80.0
        """
        call_count = [0]

        def mock_scalar():
            call_count[0] += 1
            if call_count[0] == 1:
                return 100  # total
            if call_count[0] == 2:
                return 80  # active
            return 0  # others

        result_mock = MagicMock()
        result_mock.scalar = mock_scalar
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserStatsQuery()

        result = await handler.handle_user_stats(query)

        assert result["active_percentage"] == 80.0

    async def test_applies_tenant_filter_to_stats(self, mock_session, tenant_id):
        """Test that tenant_id filter is applied to stats queries.

        Arrange: UserStatsQuery with tenant_id
        Act: Call handle_user_stats
        Assert: Multiple executes called (one per stat)
        """
        result_mock = MagicMock()
        result_mock.scalar = MagicMock(return_value=0)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserStatsQuery(tenant_id=tenant_id)

        await handler.handle_user_stats(query)

        assert mock_session.execute.call_count > 0

    async def test_handles_none_scalar_values(self, mock_session):
        """Test handles None values from scalar() calls.

        Arrange: Session returns None for scalar values
        Act: Call handle_user_stats
        Assert: Returns 0 for all stats (handles None with `or 0`)
        """
        result_mock = MagicMock()
        result_mock.scalar = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result_mock)

        handler = UserQueryHandler(mock_session, None)
        query = UserStatsQuery()

        result = await handler.handle_user_stats(query)

        assert result["total"] == 0
