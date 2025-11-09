"""Integration tests for rate limiting with Redis storage backend.

Note: Tests requiring Redis are skipped by default.
See docs/how-to/running-tests.md for Redis setup instructions.
"""

import logging

import pytest
from fastapi import FastAPI, Request, status
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from src.infrastructure.config import Settings
from src.presentation.api.middleware.rate_limiting import (
    get_client_identifier,
    get_limiter,
    setup_rate_limiting,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def settings_with_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create settings with rate limiting enabled.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        Settings with rate limiting enabled
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    return Settings()


@pytest.fixture
def settings_without_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Create settings with rate limiting disabled.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        Settings with rate limiting disabled
    """
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    return Settings()


@pytest.fixture
def app_with_rate_limiting(settings_with_rate_limiting: Settings) -> FastAPI:
    """Create FastAPI app with rate limiting configured.

    Args:
        settings_with_rate_limiting: Settings with rate limiting enabled

    Returns:
        FastAPI app with rate limiting middleware
    """
    app = FastAPI()
    limiter = setup_rate_limiting(app, settings_with_rate_limiting)

    @app.get("/test")
    @limiter.limit("5/minute")
    async def test_endpoint(request: Request) -> dict:
        request.state.client_ip = "127.0.0.1"
        return {"message": "success"}

    return app


@pytest.fixture(autouse=True)
def clear_redis_before_behavior_test(request, settings_with_rate_limiting: Settings) -> None:
    """Clear Redis database before each TestRateLimitingBehavior test to ensure clean state.

    This prevents rate limiting state from persisting between tests.
    """
    # Only clear Redis for TestRateLimitingBehavior tests
    if request.cls and request.cls.__name__ == "TestRateLimitingBehavior":
        import redis

        try:
            # Parse Redis URL to get host, port, db
            from urllib.parse import urlparse

            parsed = urlparse(settings_with_rate_limiting.redis_url)
            host = parsed.hostname
            port = parsed.port
            db = int(parsed.path.lstrip("/")) if parsed.path else 0

            # Connect and flush
            r = redis.Redis(host=host, port=port, db=db)
            r.flushdb()
        except Exception:
            # If Redis is not available, skip clearing (tests will be skipped anyway)
            logger = logging.getLogger(__name__)
            logger.debug("Redis not available for flushing")


# ============================================================================
# Test Classes
# ============================================================================


class TestGetClientIdentifier:
    """Test client identifier extraction for rate limiting.

    The client identifier (typically IP address) is used as the key
    for rate limiting. It can come from request.state.client_ip
    (set by middleware) or fall back to get_remote_address().
    """

    def test_extracts_from_request_state_client_ip(self, mocker) -> None:
        """Test client identifier from request.state.client_ip.

        Arrange: Mock request with client_ip in state
        Act: Call get_client_identifier
        Assert: Returns client_ip from state
        """
        # Arrange
        mock_request = mocker.Mock(spec=Request)
        mock_request.state.client_ip = "203.0.113.42"

        # Act
        identifier = get_client_identifier(mock_request)

        # Assert
        assert identifier == "203.0.113.42"

    def test_falls_back_to_remote_address_when_no_state(self, mocker) -> None:
        """Test fallback to get_remote_address when state lacks client_ip.

        Arrange: Mock request without client_ip in state, mock get_remote_address
        Act: Call get_client_identifier
        Assert: Returns value from get_remote_address
        """
        # Arrange
        mock_request = mocker.Mock(spec=Request)
        mock_state = mocker.Mock(spec=[])  # Empty spec = no attributes
        mock_request.state = mock_state
        mocker.patch(
            "src.presentation.api.middleware.rate_limiting.get_remote_address",
            return_value="192.168.1.100",
        )

        # Act
        identifier = get_client_identifier(mock_request)

        # Assert
        assert identifier == "192.168.1.100"

    def test_handles_ipv6_addresses(self, mocker) -> None:
        """Test client identifier extraction with IPv6 addresses.

        Arrange: Mock request with IPv6 address in client_ip
        Act: Call get_client_identifier
        Assert: Returns IPv6 address
        """
        # Arrange
        mock_request = mocker.Mock(spec=Request)
        mock_request.state.client_ip = "2001:db8::1"

        # Act
        identifier = get_client_identifier(mock_request)

        # Assert
        assert identifier == "2001:db8::1"

    def test_handles_localhost_addresses(self, mocker) -> None:
        """Test client identifier extraction with localhost address.

        Arrange: Mock request with localhost (127.0.0.1)
        Act: Call get_client_identifier
        Assert: Returns localhost address
        """
        # Arrange
        mock_request = mocker.Mock(spec=Request)
        mock_request.state.client_ip = "127.0.0.1"

        # Act
        identifier = get_client_identifier(mock_request)

        # Assert
        assert identifier == "127.0.0.1"


class TestGetLimiter:
    """Test limiter creation and configuration.

    The limiter is configured with Redis storage when enabled,
    or in-memory storage when disabled.
    """

    def test_creates_limiter_instance(self, settings_with_rate_limiting: Settings) -> None:
        """Test get_limiter creates Limiter instance.

        Arrange: Settings with rate limiting enabled
        Act: Call get_limiter
        Assert: Returns Limiter instance
        """
        # Arrange: (settings fixture provides configuration)

        # Act
        limiter = get_limiter(settings_with_rate_limiting)

        # Assert
        assert isinstance(limiter, Limiter)

    def test_configures_redis_storage_when_enabled(
        self, settings_with_rate_limiting: Settings
    ) -> None:
        """Test limiter uses Redis storage URI when enabled.

        Arrange: Settings with rate limiting enabled
        Act: Call get_limiter
        Assert: Limiter has Redis storage URI configured
        """
        # Arrange: (settings fixture provides configuration)

        # Act
        limiter = get_limiter(settings_with_rate_limiting)

        # Assert
        assert limiter._storage_uri == settings_with_rate_limiting.redis_url

    def test_disables_storage_when_rate_limiting_disabled(
        self, settings_without_rate_limiting: Settings
    ) -> None:
        """Test limiter has no storage when rate limiting disabled.

        Arrange: Settings with rate limiting disabled
        Act: Call get_limiter
        Assert: Limiter is disabled with no storage URI
        """
        # Arrange: (settings fixture provides configuration)

        # Act
        limiter = get_limiter(settings_without_rate_limiting)

        # Assert
        assert limiter.enabled is False
        assert limiter._storage_uri is None

    def test_limiter_is_reusable_across_requests(
        self, settings_with_rate_limiting: Settings
    ) -> None:
        """Test limiter instance can be reused.

        Arrange: Settings with rate limiting enabled
        Act: Call get_limiter twice
        Assert: Can create multiple limiter instances
        """
        # Arrange: (settings fixture provides configuration)

        # Act
        limiter1 = get_limiter(settings_with_rate_limiting)
        limiter2 = get_limiter(settings_with_rate_limiting)

        # Assert
        assert isinstance(limiter1, Limiter)
        assert isinstance(limiter2, Limiter)
        # They're separate instances but have same config
        assert limiter1._storage_uri == limiter2._storage_uri


class TestSetupRateLimiting:
    """Test rate limiting setup in FastAPI application.

    The setup_rate_limiting function configures the limiter,
    registers exception handlers, and stores limiter in app.state.
    """

    def test_returns_limiter_instance(self, settings_with_rate_limiting: Settings) -> None:
        """Test setup_rate_limiting returns limiter instance.

        Arrange: Create FastAPI app and settings
        Act: Call setup_rate_limiting
        Assert: Returns Limiter instance
        """
        # Arrange
        app = FastAPI()

        # Act
        limiter = setup_rate_limiting(app, settings_with_rate_limiting)

        # Assert
        assert isinstance(limiter, Limiter)

    def test_stores_limiter_in_app_state(self, settings_with_rate_limiting: Settings) -> None:
        """Test limiter is stored in app.state.

        Arrange: Create FastAPI app
        Act: Call setup_rate_limiting
        Assert: Limiter stored in app.state.limiter
        """
        # Arrange
        app = FastAPI()

        # Act
        limiter = setup_rate_limiting(app, settings_with_rate_limiting)

        # Assert
        assert app.state.limiter == limiter

    def test_registers_rate_limit_exceeded_exception_handler(
        self, settings_with_rate_limiting: Settings
    ) -> None:
        """Test RateLimitExceeded exception handler is registered.

        Arrange: Create FastAPI app
        Act: Call setup_rate_limiting
        Assert: RateLimitExceeded in app exception handlers
        """
        # Arrange
        app = FastAPI()

        # Act
        setup_rate_limiting(app, settings_with_rate_limiting)

        # Assert
        assert RateLimitExceeded in app.exception_handlers

    def test_exception_handler_is_callable(self, settings_with_rate_limiting: Settings) -> None:
        """Test registered exception handler is callable.

        Arrange: Create FastAPI app
        Act: Call setup_rate_limiting
        Assert: Exception handler is callable
        """
        # Arrange
        app = FastAPI()

        # Act
        setup_rate_limiting(app, settings_with_rate_limiting)

        # Assert
        handler = app.exception_handlers[RateLimitExceeded]
        assert callable(handler)

    def test_setup_with_disabled_rate_limiting(
        self, settings_without_rate_limiting: Settings
    ) -> None:
        """Test setup works when rate limiting is disabled.

        Arrange: Create FastAPI app and settings with rate limiting disabled
        Act: Call setup_rate_limiting
        Assert: Limiter created but disabled
        """
        # Arrange
        app = FastAPI()

        # Act
        limiter = setup_rate_limiting(app, settings_without_rate_limiting)

        # Assert
        assert isinstance(limiter, Limiter)
        assert limiter.enabled is False


class TestRateLimitingBehavior:
    """Test actual rate limiting behavior.

    These tests verify rate limits are enforced correctly.
    Most require actual Redis server and are skipped by default.
    """

    @pytest.mark.skip(reason="Requires Redis server running")
    def test_allows_requests_within_limit(self, app_with_rate_limiting: FastAPI) -> None:
        """Test requests within rate limit are allowed.

        Arrange: Create client with rate limited endpoint (5/minute)
        Act: Make 5 requests
        Assert: All requests return 200 OK
        """
        # Arrange
        client = TestClient(app_with_rate_limiting)

        # Act & Assert
        for i in range(5):
            response = client.get("/test")
            assert response.status_code == status.HTTP_200_OK, f"Request {i + 1} failed"
            assert response.json() == {"message": "success"}

    @pytest.mark.skip(reason="Requires Redis server running")
    def test_blocks_requests_exceeding_limit(self, app_with_rate_limiting: FastAPI) -> None:
        """Test requests exceeding rate limit are blocked with 429.

        Arrange: Create client with rate limited endpoint (5/minute)
        Act: Make 5 successful requests, then 1 more
        Assert: 6th request returns 429 Too Many Requests
        """
        # Arrange
        client = TestClient(app_with_rate_limiting)

        # Act: Make 5 requests (should succeed)
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == status.HTTP_200_OK

        # Act: Make 6th request (should be rate limited)
        response = client.get("/test")

        # Assert
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.skip(reason="Requires Redis server running")
    def test_rate_limits_per_client_ip(self, app_with_rate_limiting: FastAPI) -> None:
        """Test rate limiting is enforced per client IP.

        Arrange: Create client with rate limited endpoint
        Act: Make 5 requests from same client, then 1 more
        Assert: 6th request is rate limited
        """
        # Arrange
        client = TestClient(app_with_rate_limiting)

        # Act: Client makes 5 requests (should succeed)
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == status.HTTP_200_OK

        # Act: Client makes 6th request (should be rate limited)
        response = client.get("/test")

        # Assert
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.skip(reason="Requires Redis server running")
    @pytest.mark.asyncio
    async def test_rate_limits_shared_across_app_instances(
        self, settings_with_rate_limiting: Settings
    ) -> None:
        """Test rate limits are shared across multiple app instances via Redis.

        This simulates horizontal scaling where multiple app instances
        share rate limit state through Redis storage.

        Arrange: Create two separate FastAPI app instances with same Redis
        Act: Make 3 requests to app1, 2 requests to app2 (same client IP)
        Assert: 6th request to either app is rate limited (5/minute shared)
        """
        # Arrange: Create two separate app instances
        app1 = FastAPI()
        limiter1 = setup_rate_limiting(app1, settings_with_rate_limiting)

        @app1.get("/test")
        @limiter1.limit("5/minute")
        async def test_endpoint1(request: Request) -> dict:
            request.state.client_ip = "203.0.113.42"
            return {"instance": "app1"}

        app2 = FastAPI()
        limiter2 = setup_rate_limiting(app2, settings_with_rate_limiting)

        @app2.get("/test")
        @limiter2.limit("5/minute")
        async def test_endpoint2(request: Request) -> dict:
            request.state.client_ip = "203.0.113.42"  # Same client IP
            return {"instance": "app2"}

        client1 = TestClient(app1)
        client2 = TestClient(app2)

        # Act: Make 3 requests to instance 1
        for _ in range(3):
            response = client1.get("/test")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["instance"] == "app1"

        # Act: Make 2 requests to instance 2 (same client IP)
        for _ in range(2):
            response = client2.get("/test")
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["instance"] == "app2"

        # Assert: Total is 5 requests, next should be rate limited on both
        response1 = client1.get("/test")
        assert response1.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        response2 = client2.get("/test")
        assert response2.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestRateLimitingConfiguration:
    """Test rate limiting configuration options.

    Verifies different configuration scenarios work correctly.
    """

    def test_rate_limiting_can_be_disabled(self, settings_without_rate_limiting: Settings) -> None:
        """Test rate limiting can be completely disabled.

        Arrange: Settings with rate limiting disabled
        Act: Create limiter
        Assert: Limiter is disabled
        """
        # Arrange: (settings fixture provides configuration)

        # Act
        limiter = get_limiter(settings_without_rate_limiting)

        # Assert
        assert limiter.enabled is False

    def test_redis_url_is_configurable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Redis URL can be configured.

        Arrange: Set custom Redis URL in environment
        Act: Create settings and limiter
        Assert: Limiter uses custom Redis URL
        """
        # Arrange
        custom_redis_url = "redis://custom-host:6380/2"
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        monkeypatch.setenv("REDIS_URL", custom_redis_url)
        settings = Settings()

        # Act
        limiter = get_limiter(settings)

        # Assert
        assert limiter._storage_uri == custom_redis_url

    def test_rate_limit_per_minute_is_configurable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rate limit per minute can be configured.

        Arrange: Set custom rate limit in environment
        Act: Create settings
        Assert: Settings has custom rate limit
        """
        # Arrange
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10")

        # Act
        settings = Settings()

        # Assert
        assert settings.rate_limit_per_minute == 10
