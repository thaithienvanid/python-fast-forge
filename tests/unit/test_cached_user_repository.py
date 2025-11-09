"""Tests for CachedUserRepository.

Test Organization:
- TestCachedUserRepositoryInheritance: Inheritance from CachedBaseRepository
- TestCachedUserRepositoryCacheKeys: Cache key generation
- TestCachedUserRepositoryGetByEmail: Email-based caching
- TestCachedUserRepositoryGetByUsername: Username-based caching
- TestCachedUserRepositoryInvalidation: Cache invalidation on write operations
- TestCachedUserRepositoryPassthrough: Non-cached operations
"""

from unittest.mock import AsyncMock

import pytest
from uuid_extension import uuid7

from src.domain.models.user import User
from src.infrastructure.repositories.cached_user_repository import CachedUserRepository


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_user_repository():
    """Create a mock UserRepository."""
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
def cached_user_repo(mock_user_repository, mock_cache):
    """Create a cached user repository instance."""
    return CachedUserRepository(
        repository=mock_user_repository,
        cache=mock_cache,
        default_ttl=300,
    )


# ============================================================================
# Test CachedUserRepository Inheritance
# ============================================================================


class TestCachedUserRepositoryInheritance:
    """Test inheritance from CachedBaseRepository."""

    def test_extends_cached_base_repository(self, cached_user_repo):
        """Test that CachedUserRepository extends CachedBaseRepository.

        Arrange: Create cached user repository
        Act: Check base classes
        Assert: Inherits from CachedBaseRepository
        """
        # Act
        from src.infrastructure.repositories.cached_base_repository import CachedBaseRepository

        # Assert
        assert isinstance(cached_user_repo, CachedBaseRepository)

    def test_implements_user_repository_interface(self, cached_user_repo):
        """Test that CachedUserRepository implements IUserRepository.

        Arrange: Create cached user repository
        Act: Check interfaces
        Assert: Implements IUserRepository interface
        """
        # Act
        from src.domain.interfaces import IUserRepository

        # Assert
        assert isinstance(cached_user_repo, IUserRepository)

    def test_has_all_required_methods(self, cached_user_repo):
        """Test that CachedUserRepository has all required methods.

        Arrange: Create cached user repository
        Act: Check methods
        Assert: Has all CRUD and user-specific methods
        """
        # Assert: Has base repository methods
        assert hasattr(cached_user_repo, "get_by_id")
        assert hasattr(cached_user_repo, "create")
        assert hasattr(cached_user_repo, "update")
        assert hasattr(cached_user_repo, "delete")
        assert hasattr(cached_user_repo, "restore")
        assert hasattr(cached_user_repo, "force_delete")
        assert hasattr(cached_user_repo, "get_all")
        assert hasattr(cached_user_repo, "get_deleted")

        # Assert: Has user-specific methods
        assert hasattr(cached_user_repo, "get_by_email")
        assert hasattr(cached_user_repo, "get_by_username")
        assert hasattr(cached_user_repo, "find")
        assert hasattr(cached_user_repo, "count")


# ============================================================================
# Test CachedUserRepository Cache Keys
# ============================================================================


class TestCachedUserRepositoryCacheKeys:
    """Test cache key generation methods."""

    def test_get_cache_key_by_id(self, cached_user_repo, sample_user):
        """Test cache key generation by ID.

        Arrange: Create cached user repository
        Act: Call _get_cache_key_by_id
        Assert: Returns correct cache key format
        """
        # Act
        cache_key = cached_user_repo._get_cache_key_by_id(sample_user.id)

        # Assert
        assert cache_key == f"user:{sample_user.id}"

    def test_get_all_cache_keys(self, cached_user_repo, sample_user):
        """Test getting all cache keys for a user.

        Arrange: Create user with email and username
        Act: Call _get_all_cache_keys
        Assert: Returns all three cache keys (ID, email, username)
        """
        # Act
        cache_keys = cached_user_repo._get_all_cache_keys(sample_user)

        # Assert
        assert len(cache_keys) == 3
        assert f"user:{sample_user.id}" in cache_keys
        assert f"user:email:{sample_user.email.lower()}" in cache_keys
        assert f"user:username:{sample_user.username.lower()}" in cache_keys

    def test_cache_key_by_email_lowercase(self, cached_user_repo):
        """Test email cache key generation uses lowercase.

        Arrange: Create cached user repository
        Act: Call _cache_key_by_email with mixed case
        Assert: Returns lowercase cache key
        """
        # Act
        cache_key = cached_user_repo._cache_key_by_email("Test@Example.COM")

        # Assert
        assert cache_key == "user:email:test@example.com"

    def test_cache_key_by_username_lowercase(self, cached_user_repo):
        """Test username cache key generation uses lowercase.

        Arrange: Create cached user repository
        Act: Call _cache_key_by_username with mixed case
        Assert: Returns lowercase cache key
        """
        # Act
        cache_key = cached_user_repo._cache_key_by_username("TestUser")

        # Assert
        assert cache_key == "user:username:testuser"


# ============================================================================
# Test CachedUserRepository get_by_email
# ============================================================================


class TestCachedUserRepositoryGetByEmail:
    """Test email-based caching."""

    @pytest.mark.asyncio
    async def test_get_by_email_cache_hit(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test get_by_email returns cached value on cache hit.

        Arrange: Mock cache to return user data
        Act: Call get_by_email
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
        result = await cached_user_repo.get_by_email("test@example.com")

        # Assert
        assert result is not None
        assert result.email == sample_user.email
        mock_cache.get.assert_called_once_with("user:email:test@example.com")
        mock_user_repository.get_by_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_email_cache_miss_populates_cache(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test get_by_email fetches from DB on cache miss and populates cache.

        Arrange: Mock cache miss, mock repository to return user
        Act: Call get_by_email
        Assert: Returns user from DB, cache is populated
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_user_repository.get_by_email.return_value = sample_user

        # Act
        result = await cached_user_repo.get_by_email("test@example.com")

        # Assert
        assert result == sample_user
        mock_cache.get.assert_called_once()
        mock_user_repository.get_by_email.assert_called_once_with("test@example.com")
        mock_cache.set.assert_called_once_with("user:email:test@example.com", sample_user, ttl=300)

    @pytest.mark.asyncio
    async def test_get_by_email_not_found_does_not_cache(
        self, cached_user_repo, mock_cache, mock_user_repository
    ):
        """Test get_by_email does not cache when user not found.

        Arrange: Mock repository to return None
        Act: Call get_by_email
        Assert: Returns None, cache not populated
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_user_repository.get_by_email.return_value = None

        # Act
        result = await cached_user_repo.get_by_email("nonexistent@example.com")

        # Assert
        assert result is None
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_email_case_insensitive(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test get_by_email cache key is case-insensitive.

        Arrange: Mock repository to return user
        Act: Call get_by_email with mixed case email
        Assert: Cache key is lowercase
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_user_repository.get_by_email.return_value = sample_user

        # Act
        await cached_user_repo.get_by_email("Test@Example.COM")

        # Assert
        mock_cache.get.assert_called_once_with("user:email:test@example.com")
        mock_cache.set.assert_called_once_with("user:email:test@example.com", sample_user, ttl=300)


# ============================================================================
# Test CachedUserRepository get_by_username
# ============================================================================


class TestCachedUserRepositoryGetByUsername:
    """Test username-based caching."""

    @pytest.mark.asyncio
    async def test_get_by_username_cache_hit(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test get_by_username returns cached value on cache hit.

        Arrange: Mock cache to return user data
        Act: Call get_by_username
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
        result = await cached_user_repo.get_by_username("testuser")

        # Assert
        assert result is not None
        assert result.username == sample_user.username
        mock_cache.get.assert_called_once_with("user:username:testuser")
        mock_user_repository.get_by_username.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_username_cache_miss_populates_cache(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test get_by_username fetches from DB on cache miss and populates cache.

        Arrange: Mock cache miss, mock repository to return user
        Act: Call get_by_username
        Assert: Returns user from DB, cache is populated
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_user_repository.get_by_username.return_value = sample_user

        # Act
        result = await cached_user_repo.get_by_username("testuser")

        # Assert
        assert result == sample_user
        mock_cache.get.assert_called_once()
        mock_user_repository.get_by_username.assert_called_once_with("testuser")
        mock_cache.set.assert_called_once_with("user:username:testuser", sample_user, ttl=300)

    @pytest.mark.asyncio
    async def test_get_by_username_not_found_does_not_cache(
        self, cached_user_repo, mock_cache, mock_user_repository
    ):
        """Test get_by_username does not cache when user not found.

        Arrange: Mock repository to return None
        Act: Call get_by_username
        Assert: Returns None, cache not populated
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_user_repository.get_by_username.return_value = None

        # Act
        result = await cached_user_repo.get_by_username("nonexistent")

        # Assert
        assert result is None
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_username_case_insensitive(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test get_by_username cache key is case-insensitive.

        Arrange: Mock repository to return user
        Act: Call get_by_username with mixed case username
        Assert: Cache key is lowercase
        """
        # Arrange
        mock_cache.get.return_value = None
        mock_user_repository.get_by_username.return_value = sample_user

        # Act
        await cached_user_repo.get_by_username("TestUser")

        # Assert
        mock_cache.get.assert_called_once_with("user:username:testuser")
        mock_cache.set.assert_called_once_with("user:username:testuser", sample_user, ttl=300)


# ============================================================================
# Test CachedUserRepository Cache Invalidation
# ============================================================================


class TestCachedUserRepositoryInvalidation:
    """Test cache invalidation on write operations."""

    @pytest.mark.asyncio
    async def test_update_invalidates_email_and_username_caches(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test update invalidates ID, email, and username caches.

        Arrange: Mock repository to return updated user
        Act: Call update
        Assert: All three cache keys are invalidated
        """
        # Arrange
        mock_user_repository.update.return_value = sample_user

        # Act
        result = await cached_user_repo.update(sample_user)

        # Assert
        assert result == sample_user
        assert mock_cache.delete.call_count == 3
        deleted_keys = [call[0][0] for call in mock_cache.delete.call_args_list]
        assert f"user:{sample_user.id}" in deleted_keys
        assert f"user:email:{sample_user.email.lower()}" in deleted_keys
        assert f"user:username:{sample_user.username.lower()}" in deleted_keys

    @pytest.mark.asyncio
    async def test_delete_invalidates_all_caches(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test delete invalidates all user caches.

        Arrange: Mock repository to return user then delete successfully
        Act: Call delete
        Assert: All cache keys invalidated
        """
        # Arrange
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.delete.return_value = True

        # Act
        result = await cached_user_repo.delete(sample_user.id)

        # Assert
        assert result is True
        assert mock_cache.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_create_populates_id_cache_only(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test create populates only ID cache (not email/username).

        Arrange: Mock repository to return created user
        Act: Call create
        Assert: Only ID cache is populated
        """
        # Arrange
        mock_user_repository.create.return_value = sample_user

        # Act
        result = await cached_user_repo.create(sample_user)

        # Assert
        assert result == sample_user
        # Only one cache key set (by ID)
        mock_cache.set.assert_called_once_with(f"user:{sample_user.id}", sample_user, ttl=300)


# ============================================================================
# Test CachedUserRepository Passthrough Methods
# ============================================================================


class TestCachedUserRepositoryPassthrough:
    """Test non-cached pass-through operations.

    Note: find() and count() are now inherited from CachedBaseRepository
    and tested in test_cached_base_repository.py. These tests verify they
    still work correctly in the user-specific context.
    """

    @pytest.mark.asyncio
    async def test_find_passes_through_without_caching(
        self, cached_user_repo, mock_cache, mock_user_repository, sample_user
    ):
        """Test find() passes through without caching (inherited from base).

        Arrange: Mock repository to return filtered users
        Act: Call find
        Assert: Returns users from repository, cache not used
        """
        # Arrange
        from unittest.mock import MagicMock

        mock_filterset = MagicMock()
        users = [sample_user]
        mock_user_repository.find.return_value = users

        # Act
        result = await cached_user_repo.find(mock_filterset, skip=0, limit=100)

        # Assert
        assert result == users
        mock_user_repository.find.assert_called_once()
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_passes_through_without_caching(
        self, cached_user_repo, mock_cache, mock_user_repository
    ):
        """Test count() passes through without caching (inherited from base).

        Arrange: Mock repository to return count
        Act: Call count
        Assert: Returns count from repository, cache not used
        """
        # Arrange
        from unittest.mock import MagicMock

        mock_filterset = MagicMock()
        mock_user_repository.count.return_value = 42

        # Act
        result = await cached_user_repo.count(mock_filterset)

        # Assert
        assert result == 42
        mock_user_repository.count.assert_called_once()
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()
