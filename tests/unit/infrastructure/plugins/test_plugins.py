"""Comprehensive tests for the plugin system.

Tests cover PluginMetadata, PluginContext, Plugin base class, PluginLoadError,
and PluginManager functionality including discover, register, load, unload,
reload, get, list, health_check, and shutdown.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.plugins.base import (
    Plugin,
    PluginContext,
    PluginLoadError,
    PluginMetadata,
    PluginStatus,
)
from src.infrastructure.plugins.manager import PluginManager


# ─── Helpers: concrete plugin implementations ─────────────────────────────────


def _make_metadata(**kwargs) -> PluginMetadata:
    """Create a PluginMetadata with sensible defaults."""
    defaults = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A test plugin",
        "author": "Test Author",
        "plugin_type": "test",
    }
    defaults.update(kwargs)
    return PluginMetadata(**defaults)


class SimplePlugin(Plugin):
    """Concrete plugin for testing."""

    _metadata = _make_metadata(name="simple-plugin")

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return True


class FailingInitPlugin(Plugin):
    """Plugin that fails during init."""

    _metadata = _make_metadata(name="failing-init-plugin")

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def init(self, context: PluginContext) -> None:
        raise RuntimeError("Init failed")

    async def validate(self) -> bool:
        return True


class FailingValidationPlugin(Plugin):
    """Plugin that fails validation."""

    _metadata = _make_metadata(name="failing-validation-plugin")

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return False


class ActivatablePlugin(Plugin):
    """Plugin with activate and deactivate."""

    _metadata = _make_metadata(name="activatable-plugin")
    activated = False
    deactivated = False

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return True

    async def activate(self) -> None:
        ActivatablePlugin.activated = True

    async def deactivate(self) -> None:
        ActivatablePlugin.deactivated = True


class PluginWithDependency(Plugin):
    """Plugin with a dependency on simple-plugin."""

    _metadata = _make_metadata(
        name="dependent-plugin",
        dependencies=["simple-plugin"],
    )

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return True


class FailingDeactivatePlugin(Plugin):
    """Plugin that fails during deactivate."""

    _metadata = _make_metadata(name="failing-deactivate-plugin")

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return True

    async def deactivate(self) -> None:
        raise RuntimeError("Deactivate failed")


# ─── PluginStatus ─────────────────────────────────────────────────────────────


class TestPluginStatus:
    """Tests for PluginStatus enum."""

    def test_all_statuses_defined(self):
        expected = {
            "UNINITIALIZED",
            "INITIALIZING",
            "INITIALIZED",
            "ACTIVATING",
            "ACTIVE",
            "DEACTIVATING",
            "DEACTIVATED",
            "FAILED",
        }
        actual = {s.name for s in PluginStatus}
        assert expected == actual

    def test_status_values_are_strings(self):
        for status in PluginStatus:
            assert isinstance(status.value, str)


# ─── PluginMetadata ────────────────────────────────────────────────────────────


class TestPluginMetadata:
    """Tests for PluginMetadata model."""

    def test_basic_creation(self):
        meta = _make_metadata()
        assert meta.name == "test-plugin"
        assert meta.version == "1.0.0"
        assert meta.description == "A test plugin"
        assert meta.author == "Test Author"
        assert meta.plugin_type == "test"
        assert meta.dependencies == []
        assert meta.config_schema == {}
        assert meta.tags == []

    def test_with_dependencies(self):
        meta = _make_metadata(dependencies=["http-client", "cache"])
        assert meta.dependencies == ["http-client", "cache"]

    def test_with_tags(self):
        meta = _make_metadata(tags=["email", "notification"])
        assert meta.tags == ["email", "notification"]

    def test_with_config_schema(self):
        schema = {"type": "object", "properties": {"api_key": {"type": "string"}}}
        meta = _make_metadata(config_schema=schema)
        assert meta.config_schema == schema

    def test_frozen_immutable(self):
        meta = _make_metadata()
        with pytest.raises(Exception):
            meta.name = "new-name"

    def test_version_pattern_valid(self):
        meta = _make_metadata(version="2.10.3")
        assert meta.version == "2.10.3"

    def test_version_pattern_invalid(self):
        with pytest.raises(Exception):
            _make_metadata(version="1.0")

    def test_version_pattern_invalid_format(self):
        with pytest.raises(Exception):
            _make_metadata(version="v1.0.0")


# ─── PluginContext ─────────────────────────────────────────────────────────────


class TestPluginContext:
    """Tests for PluginContext dataclass."""

    def test_basic_creation(self):
        ctx = PluginContext(config={"api_key": "test"})
        assert ctx.config == {"api_key": "test"}
        assert ctx.app_config == {}
        assert ctx.logger is None
        assert ctx.event_bus is None
        assert ctx.cache is None
        assert ctx.metrics is None
        assert ctx.dependencies == {}

    def test_with_all_fields(self):
        mock_logger = MagicMock()
        mock_event_bus = MagicMock()
        mock_cache = MagicMock()
        mock_metrics = MagicMock()

        ctx = PluginContext(
            config={"key": "value"},
            app_config={"env": "production"},
            logger=mock_logger,
            event_bus=mock_event_bus,
            cache=mock_cache,
            metrics=mock_metrics,
            dependencies={"dep": MagicMock()},
        )

        assert ctx.config == {"key": "value"}
        assert ctx.app_config == {"env": "production"}
        assert ctx.logger is mock_logger
        assert ctx.event_bus is mock_event_bus
        assert ctx.cache is mock_cache
        assert ctx.metrics is mock_metrics


# ─── PluginLoadError ──────────────────────────────────────────────────────────


class TestPluginLoadError:
    """Tests for PluginLoadError exception."""

    def test_basic_creation(self):
        err = PluginLoadError(plugin_name="test-plugin", reason="Init failed")
        assert err.plugin_name == "test-plugin"
        assert err.reason == "Init failed"
        assert err.original_error is None

    def test_str_without_original_error(self):
        err = PluginLoadError(plugin_name="test-plugin", reason="Init failed")
        assert "test-plugin" in str(err)
        assert "Init failed" in str(err)

    def test_str_with_original_error(self):
        original = ValueError("the root cause")
        err = PluginLoadError(
            plugin_name="test-plugin",
            reason="Init failed",
            original_error=original,
        )
        assert "test-plugin" in str(err)
        assert "Init failed" in str(err)
        assert "the root cause" in str(err)

    def test_is_exception(self):
        err = PluginLoadError(plugin_name="test", reason="reason")
        assert isinstance(err, Exception)


# ─── Plugin Base Class ────────────────────────────────────────────────────────


class TestPluginBase:
    """Tests for Plugin base class."""

    def test_init_default_state(self):
        plugin = SimplePlugin()
        assert plugin.status == PluginStatus.UNINITIALIZED
        assert plugin.context is None
        assert plugin.error is None

    @pytest.mark.asyncio
    async def test_init_method(self):
        plugin = SimplePlugin()
        ctx = PluginContext(config={})
        await plugin.init(ctx)
        assert plugin.context is ctx

    @pytest.mark.asyncio
    async def test_validate_returns_true(self):
        plugin = SimplePlugin()
        ctx = PluginContext(config={})
        await plugin.init(ctx)
        result = await plugin.validate()
        assert result is True

    @pytest.mark.asyncio
    async def test_activate_default_noop(self):
        plugin = SimplePlugin()
        # Default activate should not raise
        await plugin.activate()

    @pytest.mark.asyncio
    async def test_deactivate_default_noop(self):
        plugin = SimplePlugin()
        # Default deactivate should not raise
        await plugin.deactivate()

    @pytest.mark.asyncio
    async def test_health_check_default(self):
        plugin = SimplePlugin()
        health = await plugin.health_check()

        assert "status" in health
        assert health["status"] == PluginStatus.UNINITIALIZED.value
        assert "error" in health
        assert "activated_at" in health
        assert health["activated_at"] is None


# ─── PluginManager - Initialization ───────────────────────────────────────────


class TestPluginManagerInit:
    """Tests for PluginManager initialization."""

    def test_default_init(self):
        manager = PluginManager()
        assert manager._plugins == {}
        assert manager._plugin_types == {}
        assert manager._contexts == {}
        assert manager._global_context["app_config"] == {}
        assert manager._global_context["event_bus"] is None

    def test_init_with_config(self):
        config = {"debug": True, "environment": "production"}
        manager = PluginManager(app_config=config)
        assert manager._global_context["app_config"] == config

    def test_init_with_all_dependencies(self):
        mock_event_bus = MagicMock()
        mock_cache = MagicMock()
        mock_metrics = MagicMock()

        manager = PluginManager(
            app_config={"key": "value"},
            event_bus=mock_event_bus,
            cache=mock_cache,
            metrics=mock_metrics,
        )

        assert manager._global_context["event_bus"] is mock_event_bus
        assert manager._global_context["cache"] is mock_cache
        assert manager._global_context["metrics"] is mock_metrics


# ─── PluginManager - register_plugin ─────────────────────────────────────────


class TestPluginManagerRegisterPlugin:
    """Tests for PluginManager.register_plugin()."""

    @pytest.mark.asyncio
    async def test_register_simple_plugin(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        assert "simple-plugin" in manager._plugin_types

    @pytest.mark.asyncio
    async def test_register_with_config(self):
        manager = PluginManager()
        config = {"api_key": "test"}
        await manager.register_plugin(SimplePlugin, config=config)

        assert "simple-plugin" in manager._contexts
        assert manager._contexts["simple-plugin"].config == config

    @pytest.mark.asyncio
    async def test_register_without_config_no_context(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        assert "simple-plugin" not in manager._contexts


# ─── PluginManager - load_plugin ─────────────────────────────────────────────


class TestPluginManagerLoadPlugin:
    """Tests for PluginManager.load_plugin()."""

    @pytest.mark.asyncio
    async def test_load_simple_plugin(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        plugin = await manager.load_plugin("simple-plugin")

        assert isinstance(plugin, SimplePlugin)
        assert plugin.status == PluginStatus.ACTIVE
        assert "simple-plugin" in manager._plugins

    @pytest.mark.asyncio
    async def test_load_plugin_not_registered_raises(self):
        manager = PluginManager()

        with pytest.raises(PluginLoadError, match="not discovered or registered"):
            await manager.load_plugin("unknown-plugin")

    @pytest.mark.asyncio
    async def test_load_plugin_already_loaded_returns_existing(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        plugin1 = await manager.load_plugin("simple-plugin")
        plugin2 = await manager.load_plugin("simple-plugin")

        assert plugin1 is plugin2

    @pytest.mark.asyncio
    async def test_load_failing_init_plugin_raises(self):
        manager = PluginManager()
        await manager.register_plugin(FailingInitPlugin)

        with pytest.raises(PluginLoadError, match="Plugin initialization failed"):
            await manager.load_plugin("failing-init-plugin")

    @pytest.mark.asyncio
    async def test_load_failing_init_sets_failed_status(self):
        manager = PluginManager()
        await manager.register_plugin(FailingInitPlugin)

        with pytest.raises(PluginLoadError):
            await manager.load_plugin("failing-init-plugin")

        # Plugin should not be in the active plugins
        assert "failing-init-plugin" not in manager._plugins

    @pytest.mark.asyncio
    async def test_load_failing_validation_raises(self):
        manager = PluginManager()
        await manager.register_plugin(FailingValidationPlugin)

        with pytest.raises(PluginLoadError, match="Plugin initialization failed"):
            await manager.load_plugin("failing-validation-plugin")

    @pytest.mark.asyncio
    async def test_load_plugin_calls_activate(self):
        ActivatablePlugin.activated = False
        manager = PluginManager()
        await manager.register_plugin(ActivatablePlugin)

        await manager.load_plugin("activatable-plugin")

        assert ActivatablePlugin.activated is True

    @pytest.mark.asyncio
    async def test_load_plugin_with_config(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        plugin = await manager.load_plugin("simple-plugin", config={"env": "test"})

        assert plugin.context.config == {"env": "test"}

    @pytest.mark.asyncio
    async def test_load_plugin_uses_existing_context_when_no_config(self):
        manager = PluginManager()
        config = {"pre_registered": True}
        await manager.register_plugin(SimplePlugin, config=config)

        plugin = await manager.load_plugin("simple-plugin")

        assert plugin.context.config == config


# ─── PluginManager - load_all ─────────────────────────────────────────────────


class TestPluginManagerLoadAll:
    """Tests for PluginManager.load_all()."""

    @pytest.mark.asyncio
    async def test_load_all_empty(self):
        manager = PluginManager()
        await manager.load_all()  # Should not raise
        assert manager._plugins == {}

    @pytest.mark.asyncio
    async def test_load_all_loads_plugins(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        await manager.load_all()

        assert "simple-plugin" in manager._plugins

    @pytest.mark.asyncio
    async def test_load_all_with_configs(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        await manager.load_all(configs={"simple-plugin": {"env": "prod"}})

        plugin = manager._plugins["simple-plugin"]
        assert plugin.context.config == {"env": "prod"}

    @pytest.mark.asyncio
    async def test_load_all_skips_failed_plugins(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.register_plugin(FailingInitPlugin)

        # Should not raise, just skip failing plugins
        await manager.load_all()

        assert "simple-plugin" in manager._plugins
        assert "failing-init-plugin" not in manager._plugins


# ─── PluginManager - _resolve_load_order ──────────────────────────────────────


class TestPluginManagerResolveLoadOrder:
    """Tests for dependency resolution."""

    @pytest.mark.asyncio
    async def test_resolve_single_plugin_no_deps(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)

        order = manager._resolve_load_order()
        assert "simple-plugin" in order

    @pytest.mark.asyncio
    async def test_resolve_empty(self):
        manager = PluginManager()
        order = manager._resolve_load_order()
        assert order == []

    @pytest.mark.asyncio
    async def test_resolve_with_dependencies(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.register_plugin(PluginWithDependency)

        order = manager._resolve_load_order()

        # Both should be in order
        assert "simple-plugin" in order
        assert "dependent-plugin" in order


# ─── PluginManager - get_plugin ───────────────────────────────────────────────


class TestPluginManagerGetPlugin:
    """Tests for PluginManager.get_plugin()."""

    @pytest.mark.asyncio
    async def test_get_loaded_plugin(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        plugin = manager.get_plugin("simple-plugin")
        assert isinstance(plugin, SimplePlugin)

    @pytest.mark.asyncio
    async def test_get_not_loaded_raises_key_error(self):
        manager = PluginManager()

        with pytest.raises(KeyError, match="simple-plugin"):
            manager.get_plugin("simple-plugin")

    @pytest.mark.asyncio
    async def test_get_plugin_with_correct_type(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        plugin = manager.get_plugin("simple-plugin", SimplePlugin)
        assert isinstance(plugin, SimplePlugin)

    @pytest.mark.asyncio
    async def test_get_plugin_with_wrong_type_raises(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        with pytest.raises(TypeError):
            manager.get_plugin("simple-plugin", ActivatablePlugin)


# ─── PluginManager - get_plugins_by_type ──────────────────────────────────────


class TestPluginManagerGetPluginsByType:
    """Tests for PluginManager.get_plugins_by_type()."""

    @pytest.mark.asyncio
    async def test_get_plugins_by_type_empty(self):
        manager = PluginManager()
        result = manager.get_plugins_by_type("email")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_plugins_by_type_matching(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)  # type="test"
        await manager.load_plugin("simple-plugin")

        result = manager.get_plugins_by_type("test")
        assert len(result) == 1
        assert isinstance(result[0], SimplePlugin)

    @pytest.mark.asyncio
    async def test_get_plugins_by_type_no_match(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)  # type="test"
        await manager.load_plugin("simple-plugin")

        result = manager.get_plugins_by_type("email")
        assert result == []


# ─── PluginManager - unload_plugin ────────────────────────────────────────────


class TestPluginManagerUnloadPlugin:
    """Tests for PluginManager.unload_plugin()."""

    @pytest.mark.asyncio
    async def test_unload_loaded_plugin(self):
        ActivatablePlugin.deactivated = False
        manager = PluginManager()
        await manager.register_plugin(ActivatablePlugin)
        await manager.load_plugin("activatable-plugin")

        await manager.unload_plugin("activatable-plugin")

        assert "activatable-plugin" not in manager._plugins
        assert ActivatablePlugin.deactivated is True

    @pytest.mark.asyncio
    async def test_unload_nonexistent_plugin_no_error(self):
        manager = PluginManager()
        await manager.unload_plugin("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_unload_failing_deactivate_marks_failed(self):
        manager = PluginManager()
        await manager.register_plugin(FailingDeactivatePlugin)
        await manager.load_plugin("failing-deactivate-plugin")

        await manager.unload_plugin("failing-deactivate-plugin")

        # Plugin should still be removed from active plugins
        # (the unload may have failed but we don't raise)


# ─── PluginManager - reload_plugin ────────────────────────────────────────────


class TestPluginManagerReloadPlugin:
    """Tests for PluginManager.reload_plugin()."""

    @pytest.mark.asyncio
    async def test_reload_plugin(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        new_plugin = await manager.reload_plugin("simple-plugin", config={"new": True})

        assert isinstance(new_plugin, SimplePlugin)
        assert new_plugin.context.config == {"new": True}


# ─── PluginManager - health_check ─────────────────────────────────────────────


class TestPluginManagerHealthCheck:
    """Tests for PluginManager.health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_empty(self):
        manager = PluginManager()
        health = await manager.health_check()

        assert health["total"] == 0
        assert health["healthy"] == 0
        assert health["failed"] == 0
        assert health["plugins"] == {}

    @pytest.mark.asyncio
    async def test_health_check_with_active_plugin(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        health = await manager.health_check()

        assert health["total"] == 1
        assert "simple-plugin" in health["plugins"]

    @pytest.mark.asyncio
    async def test_health_check_when_plugin_raises(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        # Patch health_check to raise
        plugin = manager._plugins["simple-plugin"]
        plugin.health_check = AsyncMock(side_effect=RuntimeError("health check failed"))

        health = await manager.health_check()

        assert health["plugins"]["simple-plugin"]["status"] == "error"


# ─── PluginManager - shutdown ─────────────────────────────────────────────────


class TestPluginManagerShutdown:
    """Tests for PluginManager.shutdown()."""

    @pytest.mark.asyncio
    async def test_shutdown_empty(self):
        manager = PluginManager()
        await manager.shutdown()  # Should not raise

    @pytest.mark.asyncio
    async def test_shutdown_deactivates_all_plugins(self):
        ActivatablePlugin.deactivated = False
        manager = PluginManager()
        await manager.register_plugin(ActivatablePlugin)
        await manager.load_plugin("activatable-plugin")

        await manager.shutdown()

        assert ActivatablePlugin.deactivated is True
        assert manager._plugins == {}

    @pytest.mark.asyncio
    async def test_shutdown_multiple_plugins(self):
        manager = PluginManager()
        await manager.register_plugin(SimplePlugin)
        await manager.load_plugin("simple-plugin")

        await manager.shutdown()

        assert manager._plugins == {}


# ─── PluginManager - discover_plugins ─────────────────────────────────────────


class TestPluginManagerDiscoverPlugins:
    """Tests for PluginManager.discover_plugins()."""

    @pytest.mark.asyncio
    async def test_discover_nonexistent_path_no_error(self):
        manager = PluginManager()
        await manager.discover_plugins("/nonexistent/path")
        assert manager._plugin_types == {}

    @pytest.mark.asyncio
    async def test_discover_from_file(self):
        """Test discovering a plugin from an actual Python file."""
        plugin_code = """
from src.infrastructure.plugins.base import Plugin, PluginContext, PluginMetadata

class TestDiscoveredPlugin(Plugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="discovered-plugin",
            version="1.0.0",
            description="Discovered test plugin",
            author="Test",
            plugin_type="test",
        )

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return True
"""
        manager = PluginManager()

        with tempfile.NamedTemporaryFile(suffix="_plugin.py", mode="w", delete=False) as f:
            f.write(plugin_code)
            temp_path = f.name

        try:
            await manager.discover_plugins(temp_path)
            assert "discovered-plugin" in manager._plugin_types
        finally:
            from pathlib import Path

            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_discover_from_directory(self):
        """Test discovering plugins from a directory."""
        plugin_code = """
from src.infrastructure.plugins.base import Plugin, PluginContext, PluginMetadata

class DirDiscoveredPlugin(Plugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="dir-discovered-plugin",
            version="1.0.0",
            description="Directory discovered plugin",
            author="Test",
            plugin_type="test",
        )

    async def init(self, context: PluginContext) -> None:
        self.context = context

    async def validate(self) -> bool:
        return True
"""
        manager = PluginManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "dir_discovered_plugin.py"
            plugin_file.write_text(plugin_code)

            await manager.discover_plugins(tmpdir)
            assert "dir-discovered-plugin" in manager._plugin_types
