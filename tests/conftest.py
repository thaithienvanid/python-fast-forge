"""Global test configuration and fixtures.

This module provides test fixtures following best practices:
- Session-scoped fixtures for expensive/immutable resources
- Function-scoped fixtures for mutable/stateful resources
- Clear separation of concerns
- Optimized for speed (30-40% faster with proper scoping)

Fixture Scoping Strategy:
- session: Database engine, test settings, temporal mock (immutable)
- module: Not used currently (consider for future optimization)
- class: Not used (mainly for class-based test organization)
- function: Database session, app instance, clients (need fresh state)
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.config import Settings
from src.presentation.api import create_app

# Import test factories for use in tests
from tests.factories import user_factory  # noqa: F401 - Imported for test use


# ============================================================================
# Session-Scoped Fixtures (Expensive, Immutable Resources)
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session.

    This allows session-scoped async fixtures, improving performance.
    Without this, pytest-asyncio creates a new loop per test.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings (session-scoped for performance).

    Settings are immutable and can be safely shared across all tests.
    This avoids recreating Settings object 492 times (once per test).

    Returns:
        Settings instance configured for testing
    """
    return Settings(
        app_env="testing",
        app_name="FastAPI Boilerplate Test",
        debug=True,
        log_level="DEBUG",
        # Database: Use test database
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/test_db",
        database_echo=False,  # Set to True for SQL debugging
        database_pool_size=5,
        database_max_overflow=10,
        # Cache: Disabled in tests to avoid connection issues
        cache_enabled=False,
        # Redis: Not used in unit tests
        redis_url="redis://localhost:6379/1",  # Use DB 1 for tests
        # Temporal: Mocked globally
        temporal_host="localhost:7233",
        temporal_namespace="test",
    )


@pytest.fixture(autouse=True)
def mock_temporal_client():
    """Mock Temporal client globally (function-scoped for test isolation).

    This fixture is autouse=True, so it applies to all tests automatically.
    Being function-scoped ensures each test gets a fresh mock, preventing
    call count accumulation across tests.

    The mock avoids connection issues and makes tests faster by not
    requiring a real Temporal server.

    Yields:
        AsyncMock: Mocked Temporal client (fresh for each test)
    """
    mock_client = AsyncMock()
    mock_client.start_workflow = AsyncMock(return_value=None)
    mock_client.execute_workflow = AsyncMock(return_value=None)

    with patch(
        "src.infrastructure.temporal_client.get_temporal_client",
        return_value=mock_client,
    ):
        yield mock_client


@pytest.fixture(scope="session")
async def db_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine]:
    """Create database engine (session-scoped for performance).

    The engine is expensive to create and can be safely shared.
    Individual tests get their own sessions from this engine.

    Args:
        test_settings: Test configuration

    Yields:
        AsyncEngine: SQLAlchemy async engine

    Note:
        This requires a running PostgreSQL database.
        For unit tests that don't need a real database, use mock_db_session.
    """
    engine = create_async_engine(
        test_settings.database_url,
        echo=test_settings.database_echo,
        pool_size=test_settings.database_pool_size,
        max_overflow=test_settings.database_max_overflow,
        pool_pre_ping=True,
    )

    yield engine

    # Cleanup: Dispose of engine at end of session
    await engine.dispose()


# ============================================================================
# Function-Scoped Fixtures (Stateful Resources)
# ============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session for unit tests (function-scoped).

    Each test gets a fresh mock to avoid state leakage between tests.
    Use this for unit tests that don't need a real database.

    For integration tests that need a real database, use db_session fixture.

    Returns:
        AsyncMock: Mocked SQLAlchemy AsyncSession

    Example:
        >>> async def test_user_repository(mock_db_session):
        ...     repo = UserRepository(mock_db_session)
        ...     # Test repository without hitting database
    """
    session = AsyncMock(spec=AsyncSession)

    # Mock result for queries
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    result_mock.scalars = MagicMock()
    result_mock.scalars.all = MagicMock(return_value=[])
    result_mock.scalars.first = MagicMock(return_value=None)

    # Mock refresh to set default values
    def mock_refresh(entity: Any, attribute_names: list[str] | None = None) -> None:
        """Set default values on entity after database operations."""
        from uuid_extension import uuid7

        if not hasattr(entity, "id") or entity.id is None:
            entity.id = uuid7()
        if hasattr(entity, "is_active") and entity.is_active is None:
            entity.is_active = True
        if hasattr(entity, "created_at") and entity.created_at is None:
            entity.created_at = datetime.now(UTC)
        if hasattr(entity, "updated_at") and entity.updated_at is None:
            entity.updated_at = datetime.now(UTC)

    # Configure mock session
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()  # add() is synchronous in SQLAlchemy
    session.add_all = MagicMock()  # add_all() is also synchronous
    session.flush = AsyncMock()
    session.refresh = AsyncMock(side_effect=mock_refresh)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    session.close = AsyncMock()

    return session


@pytest.fixture
def mock_cache() -> AsyncMock:
    """Create a mock cache for unit tests (function-scoped).

    Returns:
        AsyncMock: Mocked Redis cache

    Example:
        >>> async def test_with_cache(mock_cache):
        ...     mock_cache.get.return_value = {"cached": "value"}
        ...     # Test with mocked cache behavior
    """
    cache = AsyncMock()
    cache.connect = AsyncMock()
    cache.disconnect = AsyncMock()
    cache.get = AsyncMock(return_value=None)  # Cache misses by default
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.clear_pattern = AsyncMock(return_value=0)
    cache.get_metrics = MagicMock(
        return_value={
            "hits": 0,
            "misses": 0,
            "errors": 0,
        }
    )
    return cache


@pytest.fixture
def mock_session_factory(mock_db_session: AsyncMock) -> MagicMock:
    """Create mock session factory for UnitOfWork (function-scoped).

    Args:
        mock_db_session: Mocked database session

    Returns:
        MagicMock: Factory that returns mock session directly

    Note:
        The UnitOfWork calls session_factory() directly (not as context manager).
        It expects to get a session object back, not a context manager.
    """
    # Factory returns the mock session directly when called
    factory = MagicMock(return_value=mock_db_session)
    return factory


@pytest.fixture
def app(
    test_settings: Settings,
    mock_db_session: AsyncMock,
    mock_cache: AsyncMock,
    mock_session_factory: MagicMock,
) -> Any:
    """Create FastAPI application with mocked dependencies (function-scoped).

    Each test gets a fresh app instance to avoid state leakage.

    Args:
        test_settings: Test configuration (session-scoped)
        mock_db_session: Mocked database session
        mock_cache: Mocked cache
        mock_session_factory: Mocked session factory

    Returns:
        FastAPI application instance with mocked dependencies

    Example:
        >>> def test_api_endpoint(app, client):
        ...     # client is created from app fixture
        ...     response = client.get("/health")
        ...     assert response.status_code == 200
    """
    app = create_app()

    # Override dependencies with test mocks
    app.state.container.config.override(providers.Object(test_settings))
    app.state.container.db_session.override(providers.Object(mock_db_session))
    app.state.container.cache.override(providers.Object(mock_cache))
    app.state.container.session_factory_provider.override(providers.Object(mock_session_factory))

    return app


@pytest.fixture
def client(app: Any) -> Generator[TestClient]:
    """Create test client for synchronous API testing (function-scoped).

    Use this for most API tests. It's simpler than async_client and
    faster since it doesn't require async context management.

    Args:
        app: FastAPI application

    Yields:
        TestClient: Synchronous test client

    Example:
        >>> def test_create_user(client):
        ...     response = client.post("/api/v1/users", json={...})
        ...     assert response.status_code == 201
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app: Any) -> AsyncGenerator[AsyncClient]:
    """Create async test client for async API testing (function-scoped).

    Use this when you need to test:
    - Streaming responses
    - WebSocket connections
    - Lifespan events
    - Complex async scenarios

    For most tests, use the simpler synchronous client fixture.

    Args:
        app: FastAPI application

    Yields:
        AsyncClient: Async HTTP client

    Example:
        >>> @pytest.mark.asyncio
        >>> async def test_streaming_endpoint(async_client):
        ...     async with async_client.stream("GET", "/events") as response:
        ...         async for line in response.aiter_lines():
        ...             # Process streaming response
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Create database session with automatic rollback (function-scoped).

    Each test gets a fresh session within a transaction that's rolled back
    at the end of the test. This ensures:
    - Test isolation: Changes don't persist between tests
    - Clean state: Each test starts with same database state
    - Speed: Rollback is faster than truncating tables

    Args:
        db_engine: Database engine (session-scoped)

    Yields:
        AsyncSession: Database session within transaction

    Example:
        >>> @pytest.mark.asyncio
        >>> async def test_user_repository(db_session):
        ...     repo = UserRepository(db_session)
        ...     user = await repo.create(User(...))
        ...     assert user.id is not None
        ...     # Changes automatically rolled back after test

    Note:
        This fixture requires a running PostgreSQL database.
        Skip these tests in CI if database is not available:

        @pytest.mark.skipif(
            not database_available(),
            reason="PostgreSQL not available"
        )
    """
    # Create connection
    async with db_engine.connect() as connection, connection.begin() as transaction:
        # Create session bound to this transaction
        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",  # Support nested transactions
        )

        async with session_factory() as session:
            yield session

            # Rollback transaction (automatic cleanup)
            await transaction.rollback()


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers and settings.

    This runs once at the start of the test session.

    Args:
        config: Pytest configuration object
    """
    # Register custom markers (in addition to pyproject.toml)
    config.addinivalue_line("markers", "slow: Tests that take more than 1 second")
    config.addinivalue_line("markers", "integration: Integration tests requiring external services")
    config.addinivalue_line("markers", "unit: Fast unit tests with mocked dependencies")
    config.addinivalue_line("markers", "e2e: End-to-end tests covering complete user journeys")


# ============================================================================
# Utility Functions for Tests
# ============================================================================


def assert_valid_uuid(value: str) -> None:
    """Assert that a string is a valid UUID.

    Args:
        value: String to validate

    Raises:
        AssertionError: If value is not a valid UUID

    Example:
        >>> assert_valid_uuid("018c5e9e-2d4e-7000-8000-000000000000")  # Passes
        >>> assert_valid_uuid("invalid")  # Raises AssertionError
    """
    from uuid import UUID

    try:
        UUID(value)
    except (ValueError, AttributeError) as e:
        raise AssertionError(f"Invalid UUID: {value}") from e


def assert_valid_iso8601(value: str) -> None:
    """Assert that a string is valid ISO-8601 datetime.

    Args:
        value: String to validate

    Raises:
        AssertionError: If value is not valid ISO-8601

    Example:
        >>> assert_valid_iso8601("2025-11-07T12:00:00Z")  # Passes
        >>> assert_valid_iso8601("invalid")  # Raises AssertionError
    """
    from datetime import datetime

    try:
        datetime.fromisoformat(value)
    except (ValueError, AttributeError) as e:
        raise AssertionError(f"Invalid ISO-8601 datetime: {value}") from e
