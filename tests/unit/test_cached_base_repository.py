"""Tests for CachedBaseRepository generic cached repository.

Test Organization:
- TestCachedBaseRepositoryAbstractMethods: Abstract method requirements
- TestCachedBaseRepositoryGetById: Caching for get_by_id operations
- TestCachedBaseRepositoryCreate: Cache population on create
- TestCachedBaseRepositoryUpdate: Cache invalidation on update
- TestCached BaseRepositoryDelete: Cache invalidation on delete (soft delete)
- TestCachedBaseRepositoryRestore: Cache invalidation on restore
- TestCachedBaseRepositoryForceDelete: Cache invalidation on force_delete
- TestCachedBaseRepositoryPassthrough: Non-cached operations
- TestCachedBaseRepositoryEdgeCases: Edge cases and error handling
"""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from uuid_extension import uuid7

from src.domain.models.user import User
from src.infrastructure.repositories.cached_base_repository import CachedBaseRepository


# ============================================================================
# Test Concrete Implementation for Testing
# ============================================================================


class ConcreteCachedRepository(CachedBaseRepository[User]):
    """Concrete implementation of CachedBaseRepository for testing.

    This test implementation provides minimal cache key generation logic
    to test the base class functionality.
    """

    def _get_cache_key_by_id(self, id: UUID) -> str:
        """Generate cache key for test entity by ID."""
        return f"test:{id}"

    def _get_all_cache_keys(self, entity: User) -> list[str]:
        """Get all cache keys for test entity."""
        return [
            self._get_cache_key_by_id(entity.id),
            f"test:email:{entity.email.lower()}",
        ]


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_repository():
    """Create a mock base repository."""
    repo = AsyncMock()
    repo._model = User
    return repo


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)  # Cache misses by default
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        id=uuid7(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        is_active=True,
    )


@pytest.fixture
def cached_repo(mock_repository, mock_cache):
    """Create a cached repository instance."""
    return ConcreteCachedRepository(
        repository=mock_repository,
        cache=mock_cache,
        default_ttl=300,
    )


# ============================================================================
# Test CachedBaseRepository Abstract Methods
# ============================================================================


class TestCachedBaseRepositoryAbstractMethods:
    """Test abstract method requirements."""

    def test_cannot_instantiate_without_implementing_abstract_methods(
        self, mock_repository, mock_cache
    ):
        """Test that CachedBaseRepository cannot be instantiated without implementing abstract methods.

        Arrange: Try to create instance without implementing abstract methods
        Act: Attempt instantiation
        Assert: Raises TypeError
        """
        # Act & Assert
        with pytest.raises(TypeError, match="abstract methods"):
            # Try to instantiate abstract class directly
            CachedBaseRepository(mock_repository, mock_cache)

    def test_concrete_implementation_provides_cache_key_methods(self, cached_repo, sample_user):
        """Test that concrete implementation provides cache key methods.

        Arrange: Create concrete implementation
        Act: Call cache key methods
        Assert: Returns expected cache keys
        """
        # Act
        cache_key = cached_repo._get_cache_key_by_id(sample_user.id)
        all_keys = cached_repo._get_all_cache_keys(sample_user)

        # Assert
        assert cache_key == f"test:{sample_user.id}"
        assert len(all_keys) == 2
        assert f"test:{sample_user.id}" in all_keys
        assert f"test:email:{sample_user.email.lower()}" in all_keys


# ============================================================================
# Test CachedBaseRepository get_by_id
# ============================================================================


class TestCachedBaseRepositoryGetById:
    """Test caching for get_by_id operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_cache_hit(self, cached_repo, mock_cache, mock_repository, sample_user):
        """Test get_by_id returns cached value on cache hit.

        Arrange: Mock cache to return user data
        Act: Call get_by_id
        Assert: Returns user from cache, repository not called
        """
        # Arrange
        cached_data = {
            "id": str(sample_user.id),
            "email": sample_user.email,
            "username": sample_user.username,
            "full_name": sample_user.full_name,
            "is_active": sample_user.is_active,
        }
        mock_cache.get.return_value = cached_data

        # Act
        result = await cached_repo.get_by_id(sample_user.id)

        # Assert
        assert result is not None
        assert result.email == sample_user.email
        mock_cache.get.assert_called_once_with(f"test:{sample_user.id}")
        mock_repository.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_id_cache_miss_populates_cache(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test get_by_id fetches from DB on cache miss and populates cache.

        Arrange: Mock cache miss, mock repository to return user
        Act: Call get_by_id
        Assert: Returns user from DB, cache is populated
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_repository.get_by_id.return_value = sample_user

        # Act
        result = await cached_repo.get_by_id(sample_user.id)

        # Assert
        assert result == sample_user
        mock_cache.get.assert_called_once()
        mock_repository.get_by_id.assert_called_once_with(sample_user.id, include_deleted=False)
        mock_cache.set.assert_called_once_with(f"test:{sample_user.id}", sample_user, ttl=300)

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_does_not_cache(
        self, cached_repo, mock_cache, mock_repository
    ):
        """Test get_by_id does not cache when entity not found.

        Arrange: Mock repository to return None
        Act: Call get_by_id
        Assert: Returns None, cache not populated
        """
        # Arrange
        user_id = uuid7()
        mock_cache.get.return_value = None
        mock_repository.get_by_id.return_value = None

        # Act
        result = await cached_repo.get_by_id(user_id)

        # Assert
        assert result is None
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_id_with_include_deleted_bypasses_cache(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test get_by_id with include_deleted=True bypasses cache.

        Arrange: Mock repository to return user
        Act: Call get_by_id with include_deleted=True
        Assert: Fetches from DB, cache not used
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user

        # Act
        result = await cached_repo.get_by_id(sample_user.id, include_deleted=True)

        # Assert
        assert result == sample_user
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()
        mock_repository.get_by_id.assert_called_once_with(sample_user.id, include_deleted=True)


# ============================================================================
# Test CachedBaseRepository create
# ============================================================================


class TestCachedBaseRepositoryCreate:
    """Test cache population on create operations."""

    @pytest.mark.asyncio
    async def test_create_populates_cache(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test create populates cache after creation.

        Arrange: Mock repository to return created user
        Act: Call create
        Assert: Returns created user, cache is populated
        """
        # Arrange
        mock_repository.create.return_value = sample_user

        # Act
        result = await cached_repo.create(sample_user)

        # Assert
        assert result == sample_user
        mock_repository.create.assert_called_once_with(sample_user)
        mock_cache.set.assert_called_once_with(f"test:{sample_user.id}", sample_user, ttl=300)

    @pytest.mark.asyncio
    async def test_create_with_custom_ttl(self, mock_repository, mock_cache, sample_user):
        """Test create uses custom TTL when specified.

        Arrange: Create cached repo with custom TTL
        Act: Call create
        Assert: Cache populated with custom TTL
        """
        # Arrange
        custom_ttl = 600
        cached_repo = ConcreteCachedRepository(mock_repository, mock_cache, default_ttl=custom_ttl)
        mock_repository.create.return_value = sample_user

        # Act
        result = await cached_repo.create(sample_user)

        # Assert
        assert result == sample_user
        mock_cache.set.assert_called_once_with(f"test:{sample_user.id}", sample_user, ttl=600)


# ============================================================================
# Test CachedBaseRepository update
# ============================================================================


class TestCachedBaseRepositoryUpdate:
    """Test cache invalidation on update operations."""

    @pytest.mark.asyncio
    async def test_update_invalidates_all_cache_keys(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test update invalidates all related cache keys.

        Arrange: Mock repository to return updated user
        Act: Call update
        Assert: Returns updated user, all cache keys invalidated
        """
        # Arrange
        mock_repository.update.return_value = sample_user

        # Act
        result = await cached_repo.update(sample_user)

        # Assert
        assert result == sample_user
        mock_repository.update.assert_called_once_with(sample_user)

        # Verify all cache keys are deleted
        assert mock_cache.delete.call_count == 2
        deleted_keys = [call[0][0] for call in mock_cache.delete.call_args_list]
        assert f"test:{sample_user.id}" in deleted_keys
        assert f"test:email:{sample_user.email.lower()}" in deleted_keys

    @pytest.mark.asyncio
    async def test_update_invalidates_cache_even_on_error(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test update invalidates cache even if cache deletion fails.

        Arrange: Mock cache delete to fail
        Act: Call update
        Assert: Update succeeds, cache deletion attempted
        """
        # Arrange
        mock_repository.update.return_value = sample_user
        mock_cache.delete.return_value = False  # Simulate cache deletion failure

        # Act
        result = await cached_repo.update(sample_user)

        # Assert: Update still succeeds
        assert result == sample_user
        assert mock_cache.delete.call_count == 2


# ============================================================================
# Test CachedBaseRepository delete
# ============================================================================


class TestCachedBaseRepositoryDelete:
    """Test cache invalidation on delete (soft delete) operations."""

    @pytest.mark.asyncio
    async def test_delete_invalidates_all_cache_keys(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test delete invalidates all related cache keys.

        Arrange: Mock repository to return user then successfully delete
        Act: Call delete
        Assert: Returns True, all cache keys invalidated
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        mock_repository.delete.return_value = True

        # Act
        result = await cached_repo.delete(sample_user.id)

        # Assert
        assert result is True
        mock_repository.delete.assert_called_once_with(sample_user.id)

        # Verify all cache keys are deleted
        assert mock_cache.delete.call_count == 2
        deleted_keys = [call[0][0] for call in mock_cache.delete.call_args_list]
        assert f"test:{sample_user.id}" in deleted_keys
        assert f"test:email:{sample_user.email.lower()}" in deleted_keys

    @pytest.mark.asyncio
    async def test_delete_not_found_does_not_invalidate_cache(
        self, cached_repo, mock_cache, mock_repository
    ):
        """Test delete does not invalidate cache when entity not found.

        Arrange: Mock repository to return None (entity not found)
        Act: Call delete
        Assert: Returns False, cache not invalidated
        """
        # Arrange
        user_id = uuid7()
        mock_repository.get_by_id.return_value = None
        mock_repository.delete.return_value = False

        # Act
        result = await cached_repo.delete(user_id)

        # Assert
        assert result is False
        mock_cache.delete.assert_not_called()


# ============================================================================
# Test CachedBaseRepository restore
# ============================================================================


class TestCachedBaseRepositoryRestore:
    """Test cache invalidation on restore operations."""

    @pytest.mark.asyncio
    async def test_restore_invalidates_all_cache_keys(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test restore invalidates all related cache keys.

        Arrange: Mock repository to return deleted user then successfully restore
        Act: Call restore
        Assert: Returns True, all cache keys invalidated
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        mock_repository.restore.return_value = True

        # Act
        result = await cached_repo.restore(sample_user.id)

        # Assert
        assert result is True
        mock_repository.restore.assert_called_once_with(sample_user.id)

        # Verify all cache keys are deleted
        assert mock_cache.delete.call_count == 2
        deleted_keys = [call[0][0] for call in mock_cache.delete.call_args_list]
        assert f"test:{sample_user.id}" in deleted_keys
        assert f"test:email:{sample_user.email.lower()}" in deleted_keys

    @pytest.mark.asyncio
    async def test_restore_not_found_does_not_invalidate_cache(
        self, cached_repo, mock_cache, mock_repository
    ):
        """Test restore does not invalidate cache when entity not found.

        Arrange: Mock repository to return None (entity not found)
        Act: Call restore
        Assert: Returns False, cache not invalidated
        """
        # Arrange
        user_id = uuid7()
        mock_repository.get_by_id.return_value = None
        mock_repository.restore.return_value = False

        # Act
        result = await cached_repo.restore(user_id)

        # Assert
        assert result is False
        mock_cache.delete.assert_not_called()


# ============================================================================
# Test CachedBaseRepository force_delete
# ============================================================================


class TestCachedBaseRepositoryForceDelete:
    """Test cache invalidation on force_delete (hard delete) operations."""

    @pytest.mark.asyncio
    async def test_force_delete_invalidates_all_cache_keys(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test force_delete invalidates all related cache keys.

        Arrange: Mock repository to return user then successfully force delete
        Act: Call force_delete
        Assert: Returns True, all cache keys invalidated
        """
        # Arrange
        mock_repository.get_by_id.return_value = sample_user
        mock_repository.force_delete.return_value = True

        # Act
        result = await cached_repo.force_delete(sample_user.id)

        # Assert
        assert result is True
        mock_repository.force_delete.assert_called_once_with(sample_user.id)

        # Verify all cache keys are deleted
        assert mock_cache.delete.call_count == 2
        deleted_keys = [call[0][0] for call in mock_cache.delete.call_args_list]
        assert f"test:{sample_user.id}" in deleted_keys
        assert f"test:email:{sample_user.email.lower()}" in deleted_keys

    @pytest.mark.asyncio
    async def test_force_delete_not_found_does_not_invalidate_cache(
        self, cached_repo, mock_cache, mock_repository
    ):
        """Test force_delete does not invalidate cache when entity not found.

        Arrange: Mock repository to return None (entity not found)
        Act: Call force_delete
        Assert: Returns False, cache not invalidated
        """
        # Arrange
        user_id = uuid7()
        mock_repository.get_by_id.return_value = None
        mock_repository.force_delete.return_value = False

        # Act
        result = await cached_repo.force_delete(user_id)

        # Assert
        assert result is False
        mock_cache.delete.assert_not_called()


# ============================================================================
# Test CachedBaseRepository Passthrough Methods
# ============================================================================


class TestCachedBaseRepositoryPassthrough:
    """Test non-cached pass-through operations."""

    @pytest.mark.asyncio
    async def test_get_all_passes_through_to_repository(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test get_all passes through to repository without caching.

        Arrange: Mock repository to return user list
        Act: Call get_all
        Assert: Returns users from repository, cache not used
        """
        # Arrange
        users = [sample_user]
        mock_repository.get_all.return_value = users

        # Act
        result = await cached_repo.get_all(skip=10, limit=20, tenant_id=uuid7())

        # Assert
        assert result == users
        mock_repository.get_all.assert_called_once()
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_deleted_passes_through_to_repository(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test get_deleted passes through to repository without caching.

        Arrange: Mock repository to return deleted users
        Act: Call get_deleted
        Assert: Returns deleted users from repository, cache not used
        """
        # Arrange
        deleted_users = [sample_user]
        mock_repository.get_deleted.return_value = deleted_users

        # Act
        result = await cached_repo.get_deleted(skip=0, limit=100, tenant_id=uuid7())

        # Assert
        assert result == deleted_users
        mock_repository.get_deleted.assert_called_once()
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_passes_through_to_repository(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test find() passes through to repository without caching.

        Arrange: Mock repository to return filtered results
        Act: Call find
        Assert: Returns results from repository, cache not used
        """
        # Arrange
        from unittest.mock import MagicMock

        mock_filterset = MagicMock()
        filtered_users = [sample_user]
        mock_repository.find.return_value = filtered_users

        # Act
        result = await cached_repo.find(mock_filterset, skip=10, limit=50)

        # Assert
        assert result == filtered_users
        mock_repository.find.assert_called_once_with(filterset=mock_filterset, skip=10, limit=50)
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_passes_through_to_repository(
        self, cached_repo, mock_cache, mock_repository
    ):
        """Test count() passes through to repository without caching.

        Arrange: Mock repository to return count
        Act: Call count
        Assert: Returns count from repository, cache not used
        """
        # Arrange
        from unittest.mock import MagicMock

        mock_filterset = MagicMock()
        mock_repository.count.return_value = 100

        # Act
        result = await cached_repo.count(mock_filterset)

        # Assert
        assert result == 100
        mock_repository.count.assert_called_once_with(filterset=mock_filterset)
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()


# ============================================================================
# Test CachedBaseRepository Edge Cases
# ============================================================================


class TestCachedBaseRepositoryEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_cache_get_exception_gracefully(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test gracefully handles cache get exceptions.

        Arrange: Mock cache to raise exception
        Act: Call get_by_id
        Assert: Falls back to repository, operation succeeds
        """
        # Arrange
        mock_cache.get.side_effect = Exception("Cache connection error")
        mock_repository.get_by_id.return_value = sample_user

        # Act & Assert: Should fall back to repository without raising
        result = await cached_repo.get_by_id(sample_user.id)
        assert result == sample_user
        mock_repository.get_by_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_cache_set_exception_gracefully(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test gracefully handles cache set exceptions.

        Arrange: Mock cache set to raise exception
        Act: Call create
        Assert: Operation succeeds, cache error doesn't break flow
        """
        # Arrange
        mock_cache.set.side_effect = Exception("Cache write error")
        mock_repository.create.return_value = sample_user

        # Act & Assert: Should succeed despite cache error
        result = await cached_repo.create(sample_user)
        assert result == sample_user
        mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_cache_delete_exception_gracefully(
        self, cached_repo, mock_cache, mock_repository, sample_user
    ):
        """Test gracefully handles cache delete exceptions.

        Arrange: Mock cache delete to raise exception
        Act: Call update
        Assert: Operation succeeds, cache error doesn't break flow
        """
        # Arrange
        mock_cache.delete.side_effect = Exception("Cache delete error")
        mock_repository.update.return_value = sample_user

        # Act & Assert: Should succeed despite cache error
        result = await cached_repo.update(sample_user)
        assert result == sample_user
        mock_repository.update.assert_called_once()

    def test_get_model_class_returns_correct_type(self, cached_repo):
        """Test _get_model_class returns correct model type.

        Arrange: Create cached repository
        Act: Call _get_model_class
        Assert: Returns User model class
        """
        # Act
        model_class = cached_repo._get_model_class()

        # Assert
        assert model_class == User

    def test_initialization_with_custom_ttl(self, mock_repository, mock_cache):
        """Test initialization accepts custom TTL.

        Arrange: Create cached repo with custom TTL
        Act: Check TTL value
        Assert: TTL is set correctly
        """
        # Arrange & Act
        custom_ttl = 600
        repo = ConcreteCachedRepository(mock_repository, mock_cache, default_ttl=custom_ttl)

        # Assert
        assert repo._default_ttl == custom_ttl
