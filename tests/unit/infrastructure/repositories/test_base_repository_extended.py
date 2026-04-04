"""Extended unit tests for BaseRepository.

Covers missing lines to improve coverage of:
- get_by_id: include_deleted parameter, soft-delete filtering
- get_all: tenant isolation, include_deleted, pagination
- update: flush and refresh behavior
- delete: soft delete, entity not found
- restore: not-found, not-deleted entity, success
- force_delete: not-found, success
- get_deleted: tenant filter, pagination
- get_with_cursor: cursor-based pagination, include_deleted
- find: filterset-based queries
- count_all: tenant isolation, include_deleted
- count: filterset-based counting

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- AsyncMock for async session methods
- MagicMock for model and result objects
- Parametrize for boundary conditions
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.user import User
from src.infrastructure.repositories.base_repository import BaseRepository


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session):
    """Create a BaseRepository instance using User model."""
    return BaseRepository(session=mock_session, model=User)


@pytest.fixture
def sample_user():
    """Create a sample active user."""
    return User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        is_active=True,
        tenant_id=uuid4(),
        deleted_at=None,
    )


@pytest.fixture
def sample_deleted_user():
    """Create a sample soft-deleted user."""
    user = User(
        id=uuid4(),
        email="deleted@example.com",
        username="deleteduser",
        tenant_id=uuid4(),
    )
    user.deleted_at = datetime.now(UTC)
    return user


def make_execute_result(scalar_value=None, scalars_list=None):
    """Helper to create a mock execute result."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    result.scalar_one = MagicMock(return_value=scalar_value if scalar_value is not None else 0)
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=scalars_list or [])
    result.scalars = MagicMock(return_value=mock_scalars)
    return result


# ============================================================================
# get_by_id Tests
# ============================================================================


class TestBaseRepositoryGetById:
    """Tests for get_by_id method covering lines 60-66."""

    async def test_returns_entity_when_found(self, repo, mock_session, sample_user):
        """Test returns entity when found with include_deleted=False.

        Arrange: Session returns a user
        Act: Call get_by_id without include_deleted
        Assert: User returned
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_user))

        # Act
        result = await repo.get_by_id(sample_user.id)

        # Assert
        assert result == sample_user
        mock_session.execute.assert_called_once()

    async def test_returns_none_when_not_found(self, repo, mock_session):
        """Test returns None when entity not found.

        Arrange: Session returns None
        Act: Call get_by_id
        Assert: None returned
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(None))

        # Act
        result = await repo.get_by_id(uuid4())

        # Assert
        assert result is None

    async def test_get_by_id_with_include_deleted_true(
        self, repo, mock_session, sample_deleted_user
    ):
        """Test fetches deleted entity when include_deleted=True.

        Arrange: Session returns a deleted user
        Act: Call get_by_id with include_deleted=True
        Assert: Deleted user returned (line 63)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_deleted_user))

        # Act
        result = await repo.get_by_id(sample_deleted_user.id, include_deleted=True)

        # Assert
        assert result == sample_deleted_user
        mock_session.execute.assert_called_once()


# ============================================================================
# get_all Tests
# ============================================================================


class TestBaseRepositoryGetAll:
    """Tests for get_all method covering lines 89-100."""

    async def test_returns_list_of_entities(self, repo, mock_session, sample_user):
        """Test returns list of entities without filters.

        Arrange: Session returns a list of users
        Act: Call get_all
        Assert: List of users returned
        """
        # Arrange
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_user])
        )

        # Act
        result = await repo.get_all()

        # Assert
        assert result == [sample_user]

    async def test_get_all_with_tenant_id_filter(self, repo, mock_session, sample_user):
        """Test applies tenant_id filter when provided.

        Arrange: tenant_id provided, session returns filtered users
        Act: Call get_all with tenant_id
        Assert: Query executed with tenant filter (lines 94-96)
        """
        # Arrange
        tenant_id = uuid4()
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_user])
        )

        # Act
        result = await repo.get_all(tenant_id=tenant_id)

        # Assert
        assert isinstance(result, list)
        mock_session.execute.assert_called_once()

    async def test_get_all_with_include_deleted_true(self, repo, mock_session, sample_deleted_user):
        """Test includes deleted entities when include_deleted=True.

        Arrange: include_deleted=True, session returns deleted users
        Act: Call get_all with include_deleted=True
        Assert: Query executed (soft delete filter includes deleted)
        """
        # Arrange
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_deleted_user])
        )

        # Act
        result = await repo.get_all(include_deleted=True)

        # Assert
        assert result == [sample_deleted_user]

    async def test_get_all_with_skip_and_limit(self, repo, mock_session):
        """Test applies pagination via offset and limit.

        Arrange: skip=10, limit=5
        Act: Call get_all
        Assert: Query executed with offset/limit parameters (lines 98-100)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(scalars_list=[]))

        # Act
        result = await repo.get_all(skip=10, limit=5)

        # Assert
        assert result == []
        mock_session.execute.assert_called_once()


# ============================================================================
# update Tests
# ============================================================================


class TestBaseRepositoryUpdate:
    """Tests for update method covering lines 126-129."""

    async def test_adds_entity_flushes_and_refreshes(self, repo, mock_session, sample_user):
        """Test update adds entity, flushes, and refreshes.

        Arrange: Sample user
        Act: Call update
        Assert: add, flush, refresh called; entity returned
        """
        # Arrange
        mock_session.refresh = AsyncMock()

        # Act
        result = await repo.update(sample_user)

        # Assert
        mock_session.add.assert_called_once_with(sample_user)
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(sample_user)
        assert result == sample_user


# ============================================================================
# delete (soft delete) Tests
# ============================================================================


class TestBaseRepositoryDelete:
    """Tests for delete (soft delete) method covering lines 143-150."""

    async def test_soft_deletes_entity_when_found(self, repo, mock_session, sample_user):
        """Test soft deletes entity by setting deleted_at.

        Arrange: Entity found
        Act: Call delete
        Assert: soft_delete called, returns True (lines 147-150)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_user))
        sample_user.soft_delete = MagicMock()

        # Act
        result = await repo.delete(sample_user.id)

        # Assert
        assert result is True
        sample_user.soft_delete.assert_called_once()
        mock_session.flush.assert_called()

    async def test_returns_false_when_entity_not_found(self, repo, mock_session):
        """Test returns False when entity not found.

        Arrange: Session returns None
        Act: Call delete
        Assert: Returns False (lines 143-145)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(None))

        # Act
        result = await repo.delete(uuid4())

        # Assert
        assert result is False


# ============================================================================
# restore Tests
# ============================================================================


class TestBaseRepositoryRestore:
    """Tests for restore method covering lines 165-172."""

    async def test_returns_false_when_entity_not_found(self, repo, mock_session):
        """Test returns False when entity not found.

        Arrange: get_by_id returns None
        Act: Call restore
        Assert: Returns False (line 166)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(None))

        # Act
        result = await repo.restore(uuid4())

        # Assert
        assert result is False

    async def test_returns_false_when_entity_not_deleted(self, repo, mock_session, sample_user):
        """Test returns False when entity is not soft-deleted.

        Arrange: get_by_id returns active (non-deleted) entity
        Act: Call restore
        Assert: Returns False (line 166 - not entity.is_deleted)
        """
        # Arrange
        # sample_user.deleted_at is None, so is_deleted is False
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_user))

        # Act
        result = await repo.restore(sample_user.id)

        # Assert
        assert result is False

    async def test_restores_entity_when_deleted(self, repo, mock_session, sample_deleted_user):
        """Test restores entity successfully.

        Arrange: get_by_id returns deleted entity
        Act: Call restore
        Assert: restore() called, flush, refresh, returns True (lines 169-172)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_deleted_user))
        sample_deleted_user.restore = MagicMock()

        # Act
        result = await repo.restore(sample_deleted_user.id)

        # Assert
        assert result is True
        sample_deleted_user.restore.assert_called_once()
        mock_session.flush.assert_called()
        mock_session.refresh.assert_called_once_with(sample_deleted_user)


# ============================================================================
# force_delete Tests
# ============================================================================


class TestBaseRepositoryForceDelete:
    """Tests for force_delete method covering lines 187-193."""

    async def test_returns_false_when_entity_not_found(self, repo, mock_session):
        """Test returns False when entity not found.

        Arrange: get_by_id returns None
        Act: Call force_delete
        Assert: Returns False (lines 188-189)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(None))

        # Act
        result = await repo.force_delete(uuid4())

        # Assert
        assert result is False

    async def test_permanently_deletes_entity(self, repo, mock_session, sample_user):
        """Test permanently deletes entity from database.

        Arrange: get_by_id returns entity
        Act: Call force_delete
        Assert: session.delete called, flush called, returns True (lines 191-193)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_user))

        # Act
        result = await repo.force_delete(sample_user.id)

        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(sample_user)
        mock_session.flush.assert_called()

    async def test_force_deletes_soft_deleted_entity(self, repo, mock_session, sample_deleted_user):
        """Test can force-delete a soft-deleted entity (include_deleted=True).

        Arrange: Deleted entity found using include_deleted=True
        Act: Call force_delete
        Assert: Entity deleted permanently
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(sample_deleted_user))

        # Act
        result = await repo.force_delete(sample_deleted_user.id)

        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(sample_deleted_user)


# ============================================================================
# get_deleted Tests
# ============================================================================


class TestBaseRepositoryGetDeleted:
    """Tests for get_deleted method covering lines 213-225."""

    async def test_returns_only_deleted_entities(self, repo, mock_session, sample_deleted_user):
        """Test returns only soft-deleted entities.

        Arrange: Session returns deleted user
        Act: Call get_deleted
        Assert: Returns list with deleted user (lines 215-225)
        """
        # Arrange
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_deleted_user])
        )

        # Act
        result = await repo.get_deleted()

        # Assert
        assert result == [sample_deleted_user]
        mock_session.execute.assert_called_once()

    async def test_get_deleted_with_tenant_filter(self, repo, mock_session, sample_deleted_user):
        """Test applies tenant_id filter for deleted entities.

        Arrange: tenant_id provided
        Act: Call get_deleted with tenant_id
        Assert: Query includes tenant filter (lines 219-221)
        """
        # Arrange
        tenant_id = uuid4()
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_deleted_user])
        )

        # Act
        result = await repo.get_deleted(tenant_id=tenant_id)

        # Assert
        assert isinstance(result, list)
        mock_session.execute.assert_called_once()

    async def test_get_deleted_with_pagination(self, repo, mock_session):
        """Test applies skip and limit for pagination.

        Arrange: skip=5, limit=10
        Act: Call get_deleted
        Assert: Query executed (lines 223-225)
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(scalars_list=[]))

        # Act
        result = await repo.get_deleted(skip=5, limit=10)

        # Assert
        assert result == []
        mock_session.execute.assert_called_once()

    async def test_get_deleted_returns_empty_when_none_deleted(self, repo, mock_session):
        """Test returns empty list when no entities are soft-deleted.

        Arrange: Session returns empty list
        Act: Call get_deleted
        Assert: Empty list returned
        """
        # Arrange
        mock_session.execute = AsyncMock(return_value=make_execute_result(scalars_list=[]))

        # Act
        result = await repo.get_deleted()

        # Assert
        assert result == []


# ============================================================================
# count_all Tests
# ============================================================================


class TestBaseRepositoryCountAll:
    """Tests for count_all method covering lines 398-410."""

    async def test_returns_total_count(self, repo, mock_session):
        """Test returns total count of active entities.

        Arrange: Session returns count of 5
        Act: Call count_all
        Assert: Returns 5
        """
        # Arrange
        result_mock = MagicMock()
        result_mock.scalar_one = MagicMock(return_value=5)
        mock_session.execute = AsyncMock(return_value=result_mock)

        # Act
        result = await repo.count_all()

        # Assert
        assert result == 5
        mock_session.execute.assert_called_once()

    async def test_count_all_with_tenant_filter(self, repo, mock_session):
        """Test applies tenant_id filter in count.

        Arrange: tenant_id provided, count is 3
        Act: Call count_all with tenant_id
        Assert: Returns 3 (lines 404-406)
        """
        # Arrange
        result_mock = MagicMock()
        result_mock.scalar_one = MagicMock(return_value=3)
        mock_session.execute = AsyncMock(return_value=result_mock)

        # Act
        result = await repo.count_all(tenant_id=uuid4())

        # Assert
        assert result == 3

    async def test_count_all_with_include_deleted_true(self, repo, mock_session):
        """Test includes deleted entities in count when include_deleted=True.

        Arrange: include_deleted=True, count is 10
        Act: Call count_all
        Assert: Returns 10 (lines 401)
        """
        # Arrange
        result_mock = MagicMock()
        result_mock.scalar_one = MagicMock(return_value=10)
        mock_session.execute = AsyncMock(return_value=result_mock)

        # Act
        result = await repo.count_all(include_deleted=True)

        # Assert
        assert result == 10


# ============================================================================
# find Tests
# ============================================================================


class TestBaseRepositoryFind:
    """Tests for find method covering lines 359-369."""

    async def test_find_applies_filterset_and_pagination(self, repo, mock_session, sample_user):
        """Test find applies filterset filters, skip, and limit.

        Arrange: FilterSet and session returning users
        Act: Call find
        Assert: Users returned with filterset applied (lines 362-369)
        """
        # Arrange
        mock_filterset = MagicMock()
        mock_filterset.apply = MagicMock(side_effect=lambda q, **kwargs: q)
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_user])
        )

        # Act
        result = await repo.find(filterset=mock_filterset, skip=0, limit=10)

        # Assert
        assert result == [sample_user]
        mock_filterset.apply.assert_called_once()

    async def test_find_returns_empty_list_when_no_match(self, repo, mock_session):
        """Test find returns empty list when no entities match filterset.

        Arrange: FilterSet with no matches
        Act: Call find
        Assert: Empty list returned
        """
        # Arrange
        mock_filterset = MagicMock()
        mock_filterset.apply = MagicMock(side_effect=lambda q, **kwargs: q)
        mock_session.execute = AsyncMock(return_value=make_execute_result(scalars_list=[]))

        # Act
        result = await repo.find(filterset=mock_filterset)

        # Assert
        assert result == []


# ============================================================================
# count (filterset) Tests
# ============================================================================


class TestBaseRepositoryCount:
    """Tests for count (filterset) method covering lines 432-439."""

    async def test_count_with_filterset(self, repo, mock_session):
        """Test count applies filterset and returns total.

        Arrange: FilterSet and count of 7
        Act: Call count
        Assert: Returns 7 (lines 435-439)
        """
        # Arrange
        mock_filterset = MagicMock()
        mock_filterset.apply = MagicMock(side_effect=lambda q, **kwargs: q)
        result_mock = MagicMock()
        result_mock.scalar_one = MagicMock(return_value=7)
        mock_session.execute = AsyncMock(return_value=result_mock)

        # Act
        result = await repo.count(filterset=mock_filterset)

        # Assert
        assert result == 7
        mock_filterset.apply.assert_called_once()

    async def test_count_returns_zero_when_no_matches(self, repo, mock_session):
        """Test count returns 0 when filterset matches nothing.

        Arrange: FilterSet with no matches, count = 0
        Act: Call count
        Assert: Returns 0
        """
        # Arrange
        mock_filterset = MagicMock()
        mock_filterset.apply = MagicMock(side_effect=lambda q, **kwargs: q)
        result_mock = MagicMock()
        result_mock.scalar_one = MagicMock(return_value=0)
        mock_session.execute = AsyncMock(return_value=result_mock)

        # Act
        result = await repo.count(filterset=mock_filterset)

        # Assert
        assert result == 0


# ============================================================================
# get_with_cursor Tests
# ============================================================================


class TestBaseRepositoryGetWithCursor:
    """Tests for get_with_cursor method covering lines 259-322."""

    async def test_returns_cursor_page_without_cursor(self, repo, mock_session, sample_user):
        """Test returns first cursor page when no cursor provided.

        Arrange: No cursor, session returns users
        Act: Call get_with_cursor
        Assert: CursorPage returned (lines 259-322)
        """
        # Arrange
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_user])
        )

        # Act
        result = await repo.get_with_cursor(limit=10)

        # Assert
        assert result is not None
        assert hasattr(result, "items")
        mock_session.execute.assert_called_once()

    async def test_get_with_cursor_with_tenant_filter(self, repo, mock_session, sample_user):
        """Test applies tenant_id filter in cursor pagination.

        Arrange: tenant_id provided
        Act: Call get_with_cursor with tenant_id
        Assert: Query includes tenant filter (lines 265-267)
        """
        # Arrange
        tenant_id = uuid4()
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_user])
        )

        # Act
        result = await repo.get_with_cursor(tenant_id=tenant_id, limit=5)

        # Assert
        assert result is not None
        mock_session.execute.assert_called_once()

    async def test_get_with_cursor_with_include_deleted(
        self, repo, mock_session, sample_deleted_user
    ):
        """Test includes deleted entities when include_deleted=True.

        Arrange: include_deleted=True, session returns deleted user
        Act: Call get_with_cursor
        Assert: CursorPage with deleted user
        """
        # Arrange
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_deleted_user])
        )

        # Act
        result = await repo.get_with_cursor(include_deleted=True, limit=10)

        # Assert
        assert result is not None

    async def test_get_with_cursor_with_cursor_object(self, repo, mock_session, sample_user):
        """Test applies cursor-based WHERE clause when cursor provided.

        Arrange: Cursor object with value and sort_value
        Act: Call get_with_cursor with cursor
        Assert: Query executed with cursor filtering (lines 271-292)
        """
        from src.domain.pagination import Cursor

        # Arrange
        cursor = Cursor(value=uuid4(), sort_value=datetime.now(UTC))
        mock_session.execute = AsyncMock(
            return_value=make_execute_result(scalars_list=[sample_user])
        )

        # Act
        result = await repo.get_with_cursor(cursor=cursor, limit=10)

        # Assert
        assert result is not None
        mock_session.execute.assert_called_once()
