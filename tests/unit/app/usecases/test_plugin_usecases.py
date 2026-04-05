"""Tests for plugin management use cases.

Minimal test cases maximizing branch coverage across all 6 use cases.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from src.infrastructure.plugins.base import PluginMetadata


def _make_plugin(*, active: bool = True, healthy: bool = True) -> MagicMock:
    """Create a mock plugin with configurable state."""
    plugin = MagicMock()
    plugin.is_active.return_value = active
    plugin.health_check = AsyncMock(return_value=healthy)
    plugin.activate = AsyncMock()
    plugin.deactivate = AsyncMock()
    type(plugin).metadata = PropertyMock(
        return_value=PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test",
            plugin_type="test",
            dependencies=["dep-1"],
            tags=["tag-1"],
        )
    )
    return plugin


def _make_manager(**overrides: object) -> MagicMock:
    """Create a mock PluginManager (no spec - usecases use dynamic methods)."""
    manager = MagicMock()
    # Make async methods return AsyncMock
    manager.discover_plugins = AsyncMock()
    manager.unload_plugin = AsyncMock()
    for k, v in overrides.items():
        setattr(manager, k, v)
    return manager


class TestListPluginsUseCase:
    async def test_lists_healthy_and_unhealthy_plugins(self) -> None:
        """Lists all plugins with health status for healthy, unhealthy, and error cases."""
        from src.app.usecases.plugin_usecases import ListPluginsUseCase

        healthy = _make_plugin(active=True, healthy=True)
        unhealthy = _make_plugin(active=False, healthy=False)
        erroring = _make_plugin(active=True)
        erroring.health_check = AsyncMock(side_effect=RuntimeError("boom"))

        manager = _make_manager()
        manager.get_all_plugins.return_value = {"h": healthy, "u": unhealthy, "e": erroring}
        manager.get_loaded_plugins.return_value = {"h": healthy, "u": unhealthy, "e": erroring}

        uc = ListPluginsUseCase(manager)
        result = await uc.execute()

        assert result["total"] == 3
        assert result["loaded"] == 3
        assert result["active"] == 2  # healthy + erroring are active

        statuses = {p["name"]: p["health"] for p in result["plugins"]}
        assert statuses["h"] == "healthy"
        assert statuses["u"] == "unhealthy"
        assert statuses["e"] == "unknown"


class TestGetPluginDetailsUseCase:
    async def test_gets_plugin_details(self) -> None:
        """Returns full plugin details including health and metadata."""
        from src.app.usecases.plugin_usecases import GetPluginDetailsUseCase

        plugin = _make_plugin()
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = GetPluginDetailsUseCase(manager)
        result = await uc.execute("test-plugin")

        assert result["name"] == "test-plugin"
        assert result["is_active"] is True
        assert result["health"] == "healthy"
        assert result["metadata"]["version"] == "1.0.0"

    async def test_not_found(self) -> None:
        """Raises ValueError when plugin not found."""
        from src.app.usecases.plugin_usecases import GetPluginDetailsUseCase

        manager = _make_manager()
        manager.get_plugin.return_value = None

        uc = GetPluginDetailsUseCase(manager)
        with pytest.raises(ValueError, match="not found"):
            await uc.execute("missing")

    async def test_health_check_error(self) -> None:
        """Reports unknown health when health check fails."""
        from src.app.usecases.plugin_usecases import GetPluginDetailsUseCase

        plugin = _make_plugin()
        plugin.health_check = AsyncMock(side_effect=RuntimeError("check failed"))
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = GetPluginDetailsUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["health"] == "unknown"
        assert "check failed" in result["health_message"]

    async def test_with_capabilities_and_config(self) -> None:
        """Includes capabilities and configuration when plugin provides them."""
        from src.app.usecases.plugin_usecases import GetPluginDetailsUseCase

        plugin = _make_plugin()
        plugin.get_capabilities = MagicMock(return_value=["send_email"])
        plugin.get_configuration = MagicMock(return_value={"host": "smtp.test.com"})
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = GetPluginDetailsUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["capabilities"] == ["send_email"]
        assert result["configuration"]["host"] == "smtp.test.com"


class TestActivatePluginUseCase:
    async def test_activates_inactive_plugin(self) -> None:
        """Activates a plugin that is not yet active."""
        from src.app.usecases.plugin_usecases import ActivatePluginUseCase

        plugin = _make_plugin(active=False)
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = ActivatePluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["success"] is True
        plugin.activate.assert_awaited_once()

    async def test_already_active(self) -> None:
        """Does not re-activate already active plugin."""
        from src.app.usecases.plugin_usecases import ActivatePluginUseCase

        plugin = _make_plugin(active=True)
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = ActivatePluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["success"] is True
        plugin.activate.assert_not_awaited()

    async def test_discovers_and_activates(self) -> None:
        """Discovers plugin if not initially found, then activates."""
        from src.app.usecases.plugin_usecases import ActivatePluginUseCase

        plugin = _make_plugin(active=False)
        manager = _make_manager()
        manager.get_plugin.side_effect = [None, plugin]

        uc = ActivatePluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["success"] is True
        manager.discover_plugins.assert_called_once()

    async def test_not_found_after_discovery(self) -> None:
        """Raises ValueError when plugin not found even after discovery."""
        from src.app.usecases.plugin_usecases import ActivatePluginUseCase

        manager = _make_manager()
        manager.get_plugin.return_value = None

        uc = ActivatePluginUseCase(manager)
        with pytest.raises(ValueError, match="not found"):
            await uc.execute("missing")

    async def test_activation_failure(self) -> None:
        """Raises RuntimeError when activation fails."""
        from src.app.usecases.plugin_usecases import ActivatePluginUseCase

        plugin = _make_plugin(active=False)
        plugin.activate = AsyncMock(side_effect=RuntimeError("init error"))
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = ActivatePluginUseCase(manager)
        with pytest.raises(RuntimeError, match="Failed to activate"):
            await uc.execute("test-plugin")


class TestDeactivatePluginUseCase:
    async def test_deactivates_active_plugin(self) -> None:
        from src.app.usecases.plugin_usecases import DeactivatePluginUseCase

        plugin = _make_plugin(active=True)
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = DeactivatePluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["action"] == "deactivated"
        plugin.deactivate.assert_awaited_once()

    async def test_already_inactive(self) -> None:
        from src.app.usecases.plugin_usecases import DeactivatePluginUseCase

        plugin = _make_plugin(active=False)
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = DeactivatePluginUseCase(manager)
        result = await uc.execute("test-plugin")
        plugin.deactivate.assert_not_awaited()
        assert result["success"] is True

    async def test_not_found(self) -> None:
        from src.app.usecases.plugin_usecases import DeactivatePluginUseCase

        manager = _make_manager()
        manager.get_plugin.return_value = None

        uc = DeactivatePluginUseCase(manager)
        with pytest.raises(ValueError, match="not found"):
            await uc.execute("missing")

    async def test_deactivation_failure(self) -> None:
        from src.app.usecases.plugin_usecases import DeactivatePluginUseCase

        plugin = _make_plugin(active=True)
        plugin.deactivate = AsyncMock(side_effect=RuntimeError("cleanup error"))
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = DeactivatePluginUseCase(manager)
        with pytest.raises(RuntimeError, match="Failed to deactivate"):
            await uc.execute("test-plugin")


class TestReloadPluginUseCase:
    async def test_reloads_active_plugin(self) -> None:
        """Deactivates, unloads, discovers, reactivates."""
        from src.app.usecases.plugin_usecases import ReloadPluginUseCase

        plugin = _make_plugin(active=True)
        reloaded_plugin = _make_plugin(active=False)

        manager = _make_manager()
        manager.get_plugin.side_effect = [plugin, reloaded_plugin]

        uc = ReloadPluginUseCase(manager)
        result = await uc.execute("test-plugin")

        assert result["action"] == "reloaded"
        plugin.deactivate.assert_awaited_once()
        manager.unload_plugin.assert_called_once_with("test-plugin")
        manager.discover_plugins.assert_called_once()
        reloaded_plugin.activate.assert_awaited_once()

    async def test_reloads_inactive_plugin(self) -> None:
        """Reload inactive plugin skips deactivate/reactivate."""
        from src.app.usecases.plugin_usecases import ReloadPluginUseCase

        plugin = _make_plugin(active=False)
        reloaded = _make_plugin(active=False)
        manager = _make_manager()
        manager.get_plugin.side_effect = [plugin, reloaded]

        uc = ReloadPluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["success"] is True
        plugin.deactivate.assert_not_awaited()

    async def test_not_found(self) -> None:
        from src.app.usecases.plugin_usecases import ReloadPluginUseCase

        manager = _make_manager()
        manager.get_plugin.return_value = None

        uc = ReloadPluginUseCase(manager)
        with pytest.raises(ValueError, match="not found"):
            await uc.execute("missing")

    async def test_not_found_after_reload(self) -> None:
        """Plugin disappears after unload+discover."""
        from src.app.usecases.plugin_usecases import ReloadPluginUseCase

        plugin = _make_plugin(active=False)
        manager = _make_manager()
        manager.get_plugin.side_effect = [plugin, None]

        uc = ReloadPluginUseCase(manager)
        with pytest.raises(RuntimeError, match="not found after reload"):
            await uc.execute("test-plugin")


class TestHealthCheckPluginUseCase:
    async def test_healthy_plugin(self) -> None:
        from src.app.usecases.plugin_usecases import HealthCheckPluginUseCase

        plugin = _make_plugin(healthy=True)
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = HealthCheckPluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["health"] == "healthy"
        assert result["details"] is None

    async def test_unhealthy_plugin(self) -> None:
        from src.app.usecases.plugin_usecases import HealthCheckPluginUseCase

        plugin = _make_plugin(healthy=False)
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = HealthCheckPluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["health"] == "unhealthy"

    async def test_health_check_error(self) -> None:
        from src.app.usecases.plugin_usecases import HealthCheckPluginUseCase

        plugin = _make_plugin()
        plugin.health_check = AsyncMock(side_effect=RuntimeError("timeout"))
        manager = _make_manager()
        manager.get_plugin.return_value = plugin

        uc = HealthCheckPluginUseCase(manager)
        result = await uc.execute("test-plugin")
        assert result["health"] == "unknown"
        assert result["details"]["error_type"] == "RuntimeError"

    async def test_not_found(self) -> None:
        from src.app.usecases.plugin_usecases import HealthCheckPluginUseCase

        manager = _make_manager()
        manager.get_plugin.return_value = None

        uc = HealthCheckPluginUseCase(manager)
        with pytest.raises(ValueError, match="not found"):
            await uc.execute("missing")
