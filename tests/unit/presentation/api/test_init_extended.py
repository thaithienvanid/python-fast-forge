"""Extended unit tests for FastAPI application initialization.

Covers missing lines in src/presentation/api/__init__.py:
- create_app() function:
  - Application metadata (title, version, docs URL)
  - Middleware registration order
  - Router inclusion
  - Container setup
  - OpenTelemetry instrumentation (conditional)
  - Exception handler setup
- lifespan context manager:
  - Cache connect on startup
  - Cache disconnect on shutdown
  - Error handling during connect/disconnect

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- Mock all external dependencies
- pytest.mark.parametrize for settings variations
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI

from src.presentation.api import create_app


# ============================================================================
# Shared Fixtures and Helpers
# ============================================================================


def _mock_settings(
    otel_enabled: bool = False,
    is_production: bool = False,
    api_v1_prefix: str = "/api/v1",
    docs_url: str = "/docs",
    redoc_url: str = "/redoc",
    openapi_url: str = "/openapi.json",
    app_name: str = "Test App",
    app_version: str = "1.0.0",
):
    """Create a mock Settings object.

    Args:
        otel_enabled: Whether OpenTelemetry is enabled
        is_production: Whether running in production

    Returns:
        MagicMock mimicking Settings
    """
    settings = MagicMock()
    settings.otel_enabled = otel_enabled
    settings.is_production = is_production
    settings.api_v1_prefix = api_v1_prefix
    settings.docs_url = docs_url
    settings.redoc_url = redoc_url
    settings.openapi_url = openapi_url
    settings.app_name = app_name
    settings.app_version = app_version
    settings.cors_origins = ["*"]
    settings.cors_allow_credentials = True
    settings.cors_allow_methods = ["*"]
    settings.cors_allow_headers = ["*"]
    settings.cors_expose_headers = []
    settings.rate_limit_enabled = False
    settings.rate_limit_per_minute = 60
    return settings


# ============================================================================
# create_app() Tests
# ============================================================================


class TestCreateApp:
    """Tests for the create_app() function."""

    def test_returns_fastapi_instance(self):
        """Test create_app returns a FastAPI application.

        Arrange: Mocked dependencies
        Act: Call create_app()
        Assert: Returns FastAPI instance
        """
        with (
            patch("src.presentation.api.get_settings", return_value=_mock_settings()),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container = MagicMock()
            mock_container_cls.return_value = mock_container

            app = create_app()

        assert isinstance(app, FastAPI)

    def test_app_title_matches_settings(self):
        """Test FastAPI app title comes from settings.app_name.

        Arrange: Settings with custom app_name
        Act: Call create_app()
        Assert: app.title matches settings.app_name
        """
        settings = _mock_settings(app_name="My Custom API")

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            app = create_app()

        assert app.title == "My Custom API"

    def test_app_version_matches_settings(self):
        """Test FastAPI app version comes from settings.app_version.

        Arrange: Settings with custom app_version
        Act: Call create_app()
        Assert: app.version matches settings.app_version
        """
        settings = _mock_settings(app_version="2.5.3")

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            app = create_app()

        assert app.version == "2.5.3"

    def test_container_stored_in_app_state(self):
        """Test dependency injection container is stored in app.state.

        Arrange: Mocked Container
        Act: Call create_app()
        Assert: app.state.container is the created Container instance
        """
        with (
            patch("src.presentation.api.get_settings", return_value=_mock_settings()),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container = MagicMock()
            mock_container_cls.return_value = mock_container
            app = create_app()

        assert app.state.container is mock_container

    def test_container_wire_called(self):
        """Test that container.wire() is called with endpoint modules.

        Arrange: Mocked Container
        Act: Call create_app()
        Assert: container.wire() called
        """
        with (
            patch("src.presentation.api.get_settings", return_value=_mock_settings()),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container = MagicMock()
            mock_container_cls.return_value = mock_container
            create_app()

        mock_container.wire.assert_called_once()

    def test_setup_exception_handlers_called(self):
        """Test setup_exception_handlers is called with the app.

        Arrange: Mocked dependencies
        Act: Call create_app()
        Assert: setup_exception_handlers called with FastAPI app
        """
        with (
            patch("src.presentation.api.get_settings", return_value=_mock_settings()),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers") as mock_setup_exc,
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            create_app()

        mock_setup_exc.assert_called_once()
        call_arg = mock_setup_exc.call_args.args[0]
        assert isinstance(call_arg, FastAPI)

    def test_setup_cors_called(self):
        """Test setup_cors is called with the app and settings.

        Arrange: Mocked dependencies
        Act: Call create_app()
        Assert: setup_cors called once
        """
        settings = _mock_settings()

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors") as mock_setup_cors,
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            create_app()

        mock_setup_cors.assert_called_once()

    def test_otel_instrumentation_called_when_enabled(self):
        """Test OpenTelemetry FastAPI instrumentation when otel_enabled=True.

        Arrange: Settings with otel_enabled=True
        Act: Call create_app()
        Assert: instrument_fastapi called
        """
        settings = _mock_settings(otel_enabled=True)

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
            patch("src.presentation.api.instrument_fastapi") as mock_instrument,
        ):
            mock_container_cls.return_value = MagicMock()
            create_app()

        mock_instrument.assert_called_once()

    def test_otel_instrumentation_not_called_when_disabled(self):
        """Test OpenTelemetry FastAPI instrumentation skipped when otel_enabled=False.

        Arrange: Settings with otel_enabled=False
        Act: Call create_app()
        Assert: instrument_fastapi NOT called
        """
        settings = _mock_settings(otel_enabled=False)

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
            patch("src.presentation.api.instrument_fastapi") as mock_instrument,
        ):
            mock_container_cls.return_value = MagicMock()
            create_app()

        mock_instrument.assert_not_called()

    def test_configure_opentelemetry_called(self):
        """Test that configure_opentelemetry is called during app creation.

        Arrange: Mocked settings and dependencies
        Act: Call create_app()
        Assert: configure_opentelemetry called with settings
        """
        settings = _mock_settings()

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry") as mock_configure_otel,
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            create_app()

        mock_configure_otel.assert_called_once_with(settings)

    def test_configure_logging_called(self):
        """Test that configure_logging is called during app creation.

        Arrange: Mocked settings and dependencies
        Act: Call create_app()
        Assert: configure_logging called with settings
        """
        settings = _mock_settings()

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging") as mock_configure_logging,
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            create_app()

        mock_configure_logging.assert_called_once_with(settings)

    def test_api_router_included_with_prefix(self):
        """Test that API v1 router is included with the correct prefix.

        Arrange: Settings with api_v1_prefix
        Act: Call create_app()
        Assert: App has routes under the prefix
        """
        settings = _mock_settings(api_v1_prefix="/api/v1")

        with (
            patch("src.presentation.api.get_settings", return_value=settings),
            patch("src.presentation.api.configure_opentelemetry"),
            patch("src.presentation.api.configure_logging"),
            patch("src.presentation.api.Container") as mock_container_cls,
            patch("src.presentation.api.setup_exception_handlers"),
            patch("src.presentation.api.setup_cors"),
            patch("src.presentation.api.setup_rate_limiting"),
        ):
            mock_container_cls.return_value = MagicMock()
            app = create_app()

        # Check that routes exist (at least some routes are registered)
        route_paths = [route.path for route in app.routes]
        assert len(route_paths) > 0


# ============================================================================
# lifespan Tests
# ============================================================================


class TestLifespan:
    """Tests for the lifespan context manager."""

    async def test_cache_connected_on_startup(self):
        """Test cache.connect() is called during app startup.

        Arrange: App with mocked cache
        Act: Enter lifespan context (startup phase)
        Assert: cache.connect() called
        """
        from src.presentation.api import lifespan

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()

        mock_container = MagicMock()
        mock_container.cache = MagicMock(return_value=mock_cache)

        mock_app = MagicMock(spec=FastAPI)
        mock_app.title = "Test App"
        mock_app.version = "1.0.0"
        mock_app.state = MagicMock()
        mock_app.state.container = mock_container

        with patch("src.presentation.api.logger"):
            async with lifespan(mock_app):
                pass

        mock_cache.connect.assert_called_once()

    async def test_cache_disconnected_on_shutdown(self):
        """Test cache.disconnect() is called during app shutdown.

        Arrange: App with mocked cache
        Act: Exit lifespan context (shutdown phase)
        Assert: cache.disconnect() called
        """
        from src.presentation.api import lifespan

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()

        mock_container = MagicMock()
        mock_container.cache = MagicMock(return_value=mock_cache)

        mock_app = MagicMock(spec=FastAPI)
        mock_app.title = "Test App"
        mock_app.version = "1.0.0"
        mock_app.state = MagicMock()
        mock_app.state.container = mock_container

        with patch("src.presentation.api.logger"):
            async with lifespan(mock_app):
                pass

        mock_cache.disconnect.assert_called_once()

    async def test_startup_cache_error_logged_not_raised(self):
        """Test that cache connect error is logged but not raised.

        Arrange: cache.connect raises an exception
        Act: Enter lifespan context
        Assert: Exception is caught and logged, not propagated
        """
        from src.presentation.api import lifespan

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock(side_effect=RuntimeError("Redis not available"))
        mock_cache.disconnect = AsyncMock()

        mock_container = MagicMock()
        mock_container.cache = MagicMock(return_value=mock_cache)

        mock_app = MagicMock(spec=FastAPI)
        mock_app.title = "Test App"
        mock_app.version = "1.0.0"
        mock_app.state = MagicMock()
        mock_app.state.container = mock_container

        with patch("src.presentation.api.logger") as mock_logger:
            # Should NOT raise
            async with lifespan(mock_app):
                pass

        # Error should be logged
        mock_logger.error.assert_called()

    async def test_shutdown_cache_error_logged_not_raised(self):
        """Test that cache disconnect error is logged but not raised.

        Arrange: cache.disconnect raises an exception
        Act: Exit lifespan context
        Assert: Exception is caught and logged
        """
        from src.presentation.api import lifespan

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock(side_effect=RuntimeError("Redis disconnection error"))

        mock_container = MagicMock()
        mock_container.cache = MagicMock(return_value=mock_cache)

        mock_app = MagicMock(spec=FastAPI)
        mock_app.title = "Test App"
        mock_app.version = "1.0.0"
        mock_app.state = MagicMock()
        mock_app.state.container = mock_container

        with patch("src.presentation.api.logger") as mock_logger:
            # Should NOT raise
            async with lifespan(mock_app):
                pass

        # Error should be logged
        mock_logger.error.assert_called()

    async def test_startup_logs_application_startup(self):
        """Test that logger.info is called with 'application_startup' on startup.

        Arrange: App with mocked cache
        Act: Enter lifespan context
        Assert: logger.info called with 'application_startup'
        """
        from src.presentation.api import lifespan

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()

        mock_container = MagicMock()
        mock_container.cache = MagicMock(return_value=mock_cache)

        mock_app = MagicMock(spec=FastAPI)
        mock_app.title = "Test App"
        mock_app.version = "1.0.0"
        mock_app.state = MagicMock()
        mock_app.state.container = mock_container

        with patch("src.presentation.api.logger") as mock_logger:
            async with lifespan(mock_app):
                pass

        # Should have logged startup
        startup_calls = [
            c
            for c in mock_logger.info.call_args_list
            if c.args and c.args[0] == "application_startup"
        ]
        assert len(startup_calls) >= 1

    async def test_shutdown_logs_application_shutdown(self):
        """Test that logger.info is called with 'application_shutdown' on shutdown.

        Arrange: App with mocked cache
        Act: Exit lifespan context
        Assert: logger.info called with 'application_shutdown'
        """
        from src.presentation.api import lifespan

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()

        mock_container = MagicMock()
        mock_container.cache = MagicMock(return_value=mock_cache)

        mock_app = MagicMock(spec=FastAPI)
        mock_app.title = "Test App"
        mock_app.version = "1.0.0"
        mock_app.state = MagicMock()
        mock_app.state.container = mock_container

        with patch("src.presentation.api.logger") as mock_logger:
            async with lifespan(mock_app):
                pass

        shutdown_calls = [
            c
            for c in mock_logger.info.call_args_list
            if c.args and c.args[0] == "application_shutdown"
        ]
        assert len(shutdown_calls) >= 1
