"""Plugin management use cases.

Business logic for plugin discovery, lifecycle management, and monitoring.
"""

from typing import Any

from src.infrastructure.plugins.base import Plugin
from src.infrastructure.plugins.manager import PluginManager


class ListPluginsUseCase:
    """Use case for listing all discovered plugins with their status."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize use case.

        Args:
            plugin_manager: Plugin manager instance
        """
        self._manager = plugin_manager

    async def execute(self) -> dict[str, Any]:
        """List all plugins with their current status.

        Returns:
            Dictionary containing:
                - total: Total number of plugins
                - loaded: Number of loaded plugins
                - active: Number of active plugins
                - plugins: List of plugin information dictionaries

        Example:
            ```python
            use_case = ListPluginsUseCase(plugin_manager)
            result = await use_case.execute()
            print(f"Total plugins: {result['total']}")
            for plugin in result["plugins"]:
                print(f"- {plugin['name']}: {plugin['status']}")
            ```
        """
        all_plugins = self._manager.get_all_plugins()
        loaded_plugins = self._manager.get_loaded_plugins()
        active_count = sum(1 for p in loaded_plugins.values() if p.is_active())

        plugins_info = []
        for name, plugin in loaded_plugins.items():
            # Get health status
            try:
                health_result = await plugin.health_check()
                health_status = "healthy" if health_result else "unhealthy"
                health_message = None
            except Exception as e:
                health_status = "unknown"
                health_message = str(e)

            plugins_info.append(
                {
                    "name": name,
                    "is_active": plugin.is_active(),
                    "is_loaded": True,
                    "health": health_status,
                    "health_message": health_message,
                    "metadata": {
                        "name": plugin.metadata.name,
                        "version": plugin.metadata.version,
                        "description": plugin.metadata.description or "",
                        "author": plugin.metadata.author,
                        "dependencies": plugin.metadata.dependencies or [],
                        "tags": plugin.metadata.tags or [],
                    },
                }
            )

        return {
            "total": len(all_plugins),
            "loaded": len(loaded_plugins),
            "active": active_count,
            "plugins": plugins_info,
        }


class GetPluginDetailsUseCase:
    """Use case for retrieving detailed information about a specific plugin."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize use case.

        Args:
            plugin_manager: Plugin manager instance
        """
        self._manager = plugin_manager

    async def execute(self, plugin_name: str) -> dict[str, Any]:
        """Get detailed information about a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary containing plugin details

        Raises:
            ValueError: If plugin not found
        """
        plugin: Plugin = self._manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        # Get health status
        try:
            health_result = await plugin.health_check()
            health_status = "healthy" if health_result else "unhealthy"
            health_message = None
        except Exception as e:
            health_status = "unknown"
            health_message = str(e)

        # Get capabilities (if plugin provides them)
        capabilities = []
        if hasattr(plugin, "get_capabilities"):
            capabilities = plugin.get_capabilities()

        # Get configuration (sanitized)
        configuration = {}
        if hasattr(plugin, "get_configuration"):
            configuration = plugin.get_configuration()

        return {
            "name": plugin_name,
            "is_active": plugin.is_active(),
            "is_loaded": True,
            "metadata": {
                "name": plugin.metadata.name,
                "version": plugin.metadata.version,
                "description": plugin.metadata.description or "",
                "author": plugin.metadata.author,
                "dependencies": plugin.metadata.dependencies or [],
                "tags": plugin.metadata.tags or [],
            },
            "health": health_status,
            "health_message": health_message,
            "configuration": configuration,
            "capabilities": capabilities,
        }


class ActivatePluginUseCase:
    """Use case for activating a plugin."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize use case.

        Args:
            plugin_manager: Plugin manager instance
        """
        self._manager = plugin_manager

    async def execute(self, plugin_name: str) -> dict[str, Any]:
        """Activate a plugin.

        Args:
            plugin_name: Name of the plugin to activate

        Returns:
            Dictionary with activation result

        Raises:
            ValueError: If plugin not found
            RuntimeError: If activation fails
        """
        # Load plugin if not already loaded
        plugin: Plugin | None = self._manager.get_plugin(plugin_name)
        if not plugin:
            # Try to discover and load
            await self._manager.discover_plugins()
            plugin = self._manager.get_plugin(plugin_name)

            if not plugin:
                raise ValueError(f"Plugin '{plugin_name}' not found")

        # Activate if not already active
        if not plugin.is_active():
            try:
                await plugin.activate()
            except Exception as e:
                raise RuntimeError(f"Failed to activate plugin '{plugin_name}': {e}") from e

        return {
            "success": True,
            "message": f"Plugin '{plugin_name}' activated successfully",
            "plugin_name": plugin_name,
            "action": "activated",
        }


class DeactivatePluginUseCase:
    """Use case for deactivating a plugin."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize use case.

        Args:
            plugin_manager: Plugin manager instance
        """
        self._manager = plugin_manager

    async def execute(self, plugin_name: str) -> dict[str, Any]:
        """Deactivate a plugin.

        Args:
            plugin_name: Name of the plugin to deactivate

        Returns:
            Dictionary with deactivation result

        Raises:
            ValueError: If plugin not found
            RuntimeError: If deactivation fails
        """
        plugin: Plugin = self._manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        if plugin.is_active():
            try:
                await plugin.deactivate()
            except Exception as e:
                raise RuntimeError(f"Failed to deactivate plugin '{plugin_name}': {e}") from e

        return {
            "success": True,
            "message": f"Plugin '{plugin_name}' deactivated successfully",
            "plugin_name": plugin_name,
            "action": "deactivated",
        }


class ReloadPluginUseCase:
    """Use case for hot-reloading a plugin."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize use case.

        Args:
            plugin_manager: Plugin manager instance
        """
        self._manager = plugin_manager

    async def execute(self, plugin_name: str) -> dict[str, Any]:
        """Reload a plugin with updated configuration or code.

        Args:
            plugin_name: Name of the plugin to reload

        Returns:
            Dictionary with reload result

        Raises:
            ValueError: If plugin not found
            RuntimeError: If reload fails
        """
        plugin: Plugin = self._manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        try:
            was_active = plugin.is_active()

            # Deactivate and unload
            if was_active:
                await plugin.deactivate()
            await self._manager.unload_plugin(plugin_name)

            # Rediscover and reload
            await self._manager.discover_plugins()
            plugin = self._manager.get_plugin(plugin_name)

            if not plugin:
                raise RuntimeError(f"Plugin '{plugin_name}' not found after reload")

            # Reactivate if it was active before
            if was_active:
                await plugin.activate()

            return {
                "success": True,
                "message": f"Plugin '{plugin_name}' reloaded successfully",
                "plugin_name": plugin_name,
                "action": "reloaded",
            }

        except Exception as e:
            raise RuntimeError(f"Failed to reload plugin '{plugin_name}': {e}") from e


class HealthCheckPluginUseCase:
    """Use case for checking plugin health."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize use case.

        Args:
            plugin_manager: Plugin manager instance
        """
        self._manager = plugin_manager

    async def execute(self, plugin_name: str) -> dict[str, Any]:
        """Perform health check on a plugin.

        Args:
            plugin_name: Name of the plugin to check

        Returns:
            Dictionary with health check results

        Raises:
            ValueError: If plugin not found
        """
        plugin: Plugin = self._manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        try:
            health_result = await plugin.health_check()
            health_status = "healthy" if health_result else "unhealthy"
            message = "Plugin is operational" if health_result else "Plugin health check failed"
            details = None
        except Exception as e:
            health_status = "unknown"
            message = f"Health check error: {e!s}"
            details = {"error": str(e), "error_type": type(e).__name__}

        return {
            "name": plugin_name,
            "health": health_status,
            "message": message,
            "details": details,
        }


__all__ = [
    "ActivatePluginUseCase",
    "DeactivatePluginUseCase",
    "GetPluginDetailsUseCase",
    "HealthCheckPluginUseCase",
    "ListPluginsUseCase",
    "ReloadPluginUseCase",
]
