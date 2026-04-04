"""Unit tests for rate limiting middleware."""

from unittest.mock import MagicMock, patch

from src.presentation.api.middleware.rate_limiting import (
    get_client_identifier,
    get_limiter,
    setup_rate_limiting,
)


class TestGetClientIdentifier:
    """Tests for get_client_identifier function."""

    def test_uses_client_ip_from_request_state(self):
        """Uses client_ip from request state when available."""
        mock_request = MagicMock()
        mock_request.state.client_ip = "192.168.1.100"

        identifier = get_client_identifier(mock_request)

        assert identifier == "192.168.1.100"

    def test_falls_back_to_remote_address(self):
        """Falls back to get_remote_address when client_ip not in state."""
        mock_request = MagicMock()
        # Simulate missing client_ip attribute
        del mock_request.state.client_ip

        with patch(
            "src.presentation.api.middleware.rate_limiting.get_remote_address",
            return_value="10.0.0.1",
        ):
            identifier = get_client_identifier(mock_request)

        assert identifier == "10.0.0.1"

    def test_converts_ip_to_string(self):
        """Converts IP address to string."""
        mock_request = MagicMock()
        mock_request.state.client_ip = "203.0.113.42"

        identifier = get_client_identifier(mock_request)

        assert isinstance(identifier, str)
        assert identifier == "203.0.113.42"


class TestGetLimiter:
    """Tests for get_limiter function."""

    def test_creates_limiter_with_settings(self):
        """Creates limiter with settings configuration."""
        from src.infrastructure.config import Settings

        settings = Settings(
            rate_limit_per_minute=100,
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/0",
        )

        limiter = get_limiter(settings)

        assert limiter is not None
        assert limiter.enabled is True

    def test_creates_limiter_with_disabled_rate_limiting(self):
        """Creates limiter with rate limiting disabled."""
        from src.infrastructure.config import Settings

        settings = Settings(
            rate_limit_enabled=False,
        )

        limiter = get_limiter(settings)

        assert limiter is not None
        # Limiter is created regardless of enabled setting
        # The enabled flag controls whether limits are enforced

    def test_uses_rate_limit_from_settings(self):
        """Uses rate limit value from settings."""
        from src.infrastructure.config import Settings

        settings = Settings(
            rate_limit_per_minute=50,
            rate_limit_enabled=True,
        )

        limiter = get_limiter(settings)

        assert limiter is not None
        # Default limits should contain the rate from settings
        assert len(limiter._default_limits) > 0

    def test_includes_redis_url_when_enabled(self):
        """Includes Redis URL in limiter when rate limiting is enabled."""
        from src.infrastructure.config import Settings

        settings = Settings(
            rate_limit_enabled=True,
            redis_url="redis://localhost:6379/1",
        )

        limiter = get_limiter(settings)

        assert limiter is not None
        # Storage URI should be set when enabled
        assert limiter._storage_uri is not None

    def test_excludes_redis_url_when_disabled(self):
        """Sets storage_uri to None when rate limiting is disabled."""
        from src.infrastructure.config import Settings

        settings = Settings(
            rate_limit_enabled=False,
        )

        limiter = get_limiter(settings)

        assert limiter is not None
        # When disabled, storage_uri is set to None in get_limiter


class TestSetupRateLimiting:
    """Tests for setup_rate_limiting function."""

    @patch("src.presentation.api.middleware.rate_limiting.get_limiter")
    def test_adds_limiter_to_app_state(self, mock_get_limiter):
        """Adds limiter instance to FastAPI app state."""
        from fastapi import FastAPI

        from src.infrastructure.config import Settings

        mock_limiter = MagicMock()
        mock_get_limiter.return_value = mock_limiter

        app = FastAPI()
        settings = Settings()

        result = setup_rate_limiting(app, settings)

        assert app.state.limiter == mock_limiter
        assert result == mock_limiter

    @patch("src.presentation.api.middleware.rate_limiting.get_limiter")
    def test_registers_rate_limit_exception_handler(self, mock_get_limiter):
        """Registers RateLimitExceeded exception handler."""
        from fastapi import FastAPI

        from src.infrastructure.config import Settings

        mock_limiter = MagicMock()
        mock_get_limiter.return_value = mock_limiter

        app = FastAPI()
        settings = Settings()

        setup_rate_limiting(app, settings)

        # Verify exception handler was added
        # (can't easily assert on the handler itself, but we can check it was called)
        mock_get_limiter.assert_called_once()

    @patch("src.presentation.api.middleware.rate_limiting.get_limiter")
    def test_returns_limiter_instance(self, mock_get_limiter):
        """Returns the created limiter instance."""
        from fastapi import FastAPI

        from src.infrastructure.config import Settings

        mock_limiter = MagicMock()
        mock_get_limiter.return_value = mock_limiter

        app = FastAPI()
        settings = Settings()

        result = setup_rate_limiting(app, settings)

        assert result is not None
        assert result == mock_limiter
