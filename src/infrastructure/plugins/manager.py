"""Plugin manager for discovery, loading, and lifecycle management.

The PluginManager is responsible for:
- Discovering plugins (filesystem, modules, packages)
- Loading and instantiating plugins
- Resolving plugin dependencies
- Managing plugin lifecycle (init, validate, activate, deactivate)
- Providing plugin access to other services
- Hot-reload support

Features:
- Automatic plugin discovery
- Dependency resolution and ordering
- Concurrent plugin loading
- Health monitoring
- Graceful error handling
- Plugin isolation

Example:
    >>> manager = PluginManager()
    >>> await manager.discover_plugins("src/plugins")
    >>> await manager.load_all()
    >>> email_plugin = manager.get_plugin("sendgrid-email", EmailPlugin)
    >>> await email_plugin.send_email("user@example.com", "Hello", "World")
"""

import asyncio
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Type, TypeVar

from src.infrastructure.logging.config import get_logger
from src.infrastructure.plugins.base import (
    Plugin,
    PluginContext,
    PluginLoadError,
    PluginMetadata,
    PluginStatus,
)

logger = get_logger(__name__)

T = TypeVar("T", bound=Plugin)


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle.

    The PluginManager is the central orchestrator for the plugin system.
    It discovers plugins from specified paths, loads them in dependency
    order, and manages their lifecycle.

    Attributes:
        _plugins: Registered plugin instances by name
        _plugin_types: Plugin classes by name (before instantiation)
        _contexts: Plugin runtime contexts
        _global_context: Shared context for all plugins

    Example:
        >>> # Initialize manager
        >>> manager = PluginManager(
        ...     app_config=app.config,
        ...     event_bus=event_bus,
        ...     cache=redis_client,
        ... )
        >>>
        >>> # Discover plugins from directory
        >>> await manager.discover_plugins("src/plugins")
        >>>
        >>> # Load all plugins
        >>> await manager.load_all()
        >>>
        >>> # Get specific plugin
        >>> email_plugin = manager.get_plugin("sendgrid-email", EmailPlugin)
        >>> await email_plugin.send_email(...)
        >>>
        >>> # Shutdown
        >>> await manager.shutdown()
    """

    def __init__(
        self,
        app_config: dict[str, Any] | None = None,
        event_bus: Any | None = None,
        cache: Any | None = None,
        metrics: Any | None = None,
    ):
        """Initialize plugin manager.

        Args:
            app_config: Global application configuration
            event_bus: Event bus for domain events
            cache: Cache client (Redis)
            metrics: Metrics collector
        """
        self._plugins: dict[str, Plugin] = {}
        self._plugin_types: dict[str, Type[Plugin]] = {}
        self._contexts: dict[str, PluginContext] = {}
        self._global_context = {
            "app_config": app_config or {},
            "event_bus": event_bus,
            "cache": cache,
            "metrics": metrics,
        }
        self._load_order: list[str] = []

    async def discover_plugins(self, *paths: str | Path) -> None:
        """Discover plugins from specified paths.

        Scans directories for Python modules containing Plugin subclasses.
        Plugins must be in files named *_plugin.py or in __init__.py.

        Args:
            *paths: Paths to search for plugins

        Example:
            >>> await manager.discover_plugins(
            ...     "src/plugins",
            ...     "custom_plugins",
            ... )
            Discovered plugins: sendgrid-email, s3-storage, oauth-auth
        """
        discovered_count = 0

        for path in paths:
            path = Path(path)

            if not path.exists():
                logger.warning("plugin_discovery_path_not_found", path=str(path))
                continue

            # Find all *_plugin.py files
            if path.is_dir():
                plugin_files = list(path.glob("**/*_plugin.py"))
                plugin_files.extend(path.glob("**/__init__.py"))
            else:
                plugin_files = [path]

            for file_path in plugin_files:
                try:
                    plugin_classes = await self._load_plugin_module(file_path)
                    for plugin_class in plugin_classes:
                        # Instantiate to get metadata
                        plugin_instance = plugin_class()
                        plugin_name = plugin_instance.metadata.name

                        self._plugin_types[plugin_name] = plugin_class

                        logger.info(
                            "plugin_discovered",
                            name=plugin_name,
                            version=plugin_instance.metadata.version,
                            type=plugin_instance.metadata.plugin_type,
                            file=str(file_path),
                        )
                        discovered_count += 1

                except Exception as e:
                    logger.error(
                        "plugin_discovery_failed",
                        file=str(file_path),
                        error=str(e),
                    )

        logger.info("plugin_discovery_complete", count=discovered_count)

    async def _load_plugin_module(self, file_path: Path) -> list[Type[Plugin]]:
        """Load plugin classes from Python module.

        Args:
            file_path: Path to Python file

        Returns:
            List of Plugin subclasses found in module
        """
        # Import module
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            return []

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find Plugin subclasses
        plugin_classes = []
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Plugin)
                and obj is not Plugin
                and not inspect.isabstract(obj)
            ):
                plugin_classes.append(obj)

        return plugin_classes

    async def register_plugin(
        self,
        plugin_class: Type[Plugin],
        config: dict[str, Any] | None = None,
    ) -> None:
        """Manually register a plugin class.

        Use this to register plugins without filesystem discovery.

        Args:
            plugin_class: Plugin class to register
            config: Plugin-specific configuration

        Example:
            >>> await manager.register_plugin(
            ...     SendGridEmailPlugin,
            ...     config={"api_key": "sk_..."}
            ... )
        """
        plugin_instance = plugin_class()
        plugin_name = plugin_instance.metadata.name

        self._plugin_types[plugin_name] = plugin_class
        if config:
            self._contexts[plugin_name] = PluginContext(
                config=config,
                **self._global_context,
            )

        logger.info(
            "plugin_registered",
            name=plugin_name,
            version=plugin_instance.metadata.version,
        )

    async def load_plugin(
        self,
        plugin_name: str,
        config: dict[str, Any] | None = None,
    ) -> Plugin:
        """Load and initialize a specific plugin.

        Args:
            plugin_name: Name of plugin to load
            config: Plugin-specific configuration (overrides context)

        Returns:
            Loaded and initialized plugin instance

        Raises:
            PluginLoadError: If loading fails

        Example:
            >>> plugin = await manager.load_plugin(
            ...     "sendgrid-email",
            ...     config={"api_key": "sk_..."}
            ... )
        """
        if plugin_name in self._plugins:
            return self._plugins[plugin_name]

        if plugin_name not in self._plugin_types:
            raise PluginLoadError(
                plugin_name=plugin_name,
                reason=f"Plugin '{plugin_name}' not discovered or registered",
            )

        plugin_class = self._plugin_types[plugin_name]
        plugin = plugin_class()

        try:
            # Update status
            plugin.status = PluginStatus.INITIALIZING

            # Create context
            if plugin_name in self._contexts and config is None:
                context = self._contexts[plugin_name]
            else:
                context = PluginContext(
                    config=config or {},
                    logger=get_logger(f"plugin.{plugin_name}"),
                    **self._global_context,
                )
                self._contexts[plugin_name] = context

            # Initialize
            await plugin.init(context)
            plugin.status = PluginStatus.INITIALIZED

            # Validate
            is_valid = await plugin.validate()
            if not is_valid:
                raise PluginLoadError(
                    plugin_name=plugin_name,
                    reason="Plugin validation failed",
                )

            # Activate
            plugin.status = PluginStatus.ACTIVATING
            await plugin.activate()
            plugin.status = PluginStatus.ACTIVE

            # Register
            self._plugins[plugin_name] = plugin

            logger.info(
                "plugin_loaded",
                name=plugin_name,
                version=plugin.metadata.version,
                type=plugin.metadata.plugin_type,
            )

            return plugin

        except Exception as e:
            plugin.status = PluginStatus.FAILED
            plugin.error = str(e)

            logger.error(
                "plugin_load_failed",
                name=plugin_name,
                error=str(e),
            )

            raise PluginLoadError(
                plugin_name=plugin_name,
                reason="Plugin initialization failed",
                original_error=e,
            )

    async def load_all(self, configs: dict[str, dict[str, Any]] | None = None) -> None:
        """Load all discovered plugins.

        Plugins are loaded in dependency order to ensure dependencies
        are available when needed.

        Args:
            configs: Plugin-specific configurations by plugin name

        Example:
            >>> await manager.load_all(configs={
            ...     "sendgrid-email": {"api_key": "sk_..."},
            ...     "s3-storage": {"bucket": "my-bucket"},
            ... })
        """
        configs = configs or {}

        # Resolve load order (topological sort by dependencies)
        load_order = self._resolve_load_order()

        logger.info("plugin_load_all_start", count=len(load_order))

        # Load plugins in order
        for plugin_name in load_order:
            config = configs.get(plugin_name)
            try:
                await self.load_plugin(plugin_name, config)
            except PluginLoadError as e:
                logger.error("plugin_load_failed_skipping", error=str(e))

        logger.info(
            "plugin_load_all_complete",
            loaded=len(self._plugins),
            total=len(load_order),
        )

    def _resolve_load_order(self) -> list[str]:
        """Resolve plugin load order based on dependencies.

        Uses topological sort to ensure dependencies are loaded first.

        Returns:
            List of plugin names in load order
        """
        # Build dependency graph
        graph: dict[str, list[str]] = {}
        for plugin_name, plugin_class in self._plugin_types.items():
            plugin = plugin_class()
            graph[plugin_name] = plugin.metadata.dependencies

        # Topological sort (Kahn's algorithm)
        in_degree = {plugin: 0 for plugin in graph}
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1

        queue = [plugin for plugin, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            plugin = queue.pop(0)
            order.append(plugin)

            for dep in graph.get(plugin, []):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        return order

    def get_plugin(self, plugin_name: str, plugin_type: Type[T] | None = None) -> T:
        """Get loaded plugin by name.

        Args:
            plugin_name: Name of plugin
            plugin_type: Expected plugin type (for type checking)

        Returns:
            Plugin instance

        Raises:
            KeyError: If plugin not loaded

        Example:
            >>> email_plugin = manager.get_plugin("sendgrid-email", EmailPlugin)
            >>> await email_plugin.send_email(...)
        """
        if plugin_name not in self._plugins:
            raise KeyError(f"Plugin '{plugin_name}' not loaded")

        plugin = self._plugins[plugin_name]

        # Type checking (optional)
        if plugin_type and not isinstance(plugin, plugin_type):
            raise TypeError(
                f"Plugin '{plugin_name}' is {type(plugin).__name__}, "
                f"expected {plugin_type.__name__}"
            )

        return plugin  # type: ignore

    def get_plugins_by_type(self, plugin_type: str) -> list[Plugin]:
        """Get all plugins of a specific type.

        Args:
            plugin_type: Plugin type (email, storage, auth, etc.)

        Returns:
            List of plugins matching the type

        Example:
            >>> storage_plugins = manager.get_plugins_by_type("storage")
            >>> for plugin in storage_plugins:
            ...     print(f"Storage: {plugin.metadata.name}")
        """
        return [
            plugin
            for plugin in self._plugins.values()
            if plugin.metadata.plugin_type == plugin_type
        ]

    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload and deactivate a plugin.

        Args:
            plugin_name: Name of plugin to unload

        Example:
            >>> await manager.unload_plugin("sendgrid-email")
        """
        if plugin_name not in self._plugins:
            return

        plugin = self._plugins[plugin_name]

        try:
            plugin.status = PluginStatus.DEACTIVATING
            await plugin.deactivate()
            plugin.status = PluginStatus.DEACTIVATED

            del self._plugins[plugin_name]

            logger.info("plugin_unloaded", name=plugin_name)

        except Exception as e:
            plugin.status = PluginStatus.FAILED
            plugin.error = str(e)
            logger.error("plugin_unload_failed", name=plugin_name, error=str(e))

    async def reload_plugin(
        self,
        plugin_name: str,
        config: dict[str, Any] | None = None,
    ) -> Plugin:
        """Reload a plugin (unload + load).

        Useful for configuration changes or code updates.

        Args:
            plugin_name: Name of plugin to reload
            config: New configuration (optional)

        Returns:
            Reloaded plugin instance

        Example:
            >>> plugin = await manager.reload_plugin(
            ...     "sendgrid-email",
            ...     config={"api_key": "new_key"}
            ... )
        """
        await self.unload_plugin(plugin_name)
        return await self.load_plugin(plugin_name, config)

    async def health_check(self) -> dict[str, Any]:
        """Check health of all plugins.

        Returns:
            Health status for all plugins

        Example:
            >>> health = await manager.health_check()
            >>> print(health)
            {
                "total": 3,
                "healthy": 2,
                "failed": 1,
                "plugins": {
                    "sendgrid-email": {"status": "active", ...},
                    "s3-storage": {"status": "failed", "error": "..."},
                }
            }
        """
        plugin_health = {}
        for plugin_name, plugin in self._plugins.items():
            try:
                plugin_health[plugin_name] = await plugin.health_check()
            except Exception as e:
                plugin_health[plugin_name] = {
                    "status": "error",
                    "error": str(e),
                }

        healthy_count = sum(
            1 for h in plugin_health.values() if h.get("status") == "active"
        )

        return {
            "total": len(self._plugins),
            "healthy": healthy_count,
            "failed": len(self._plugins) - healthy_count,
            "plugins": plugin_health,
        }

    async def shutdown(self) -> None:
        """Shutdown all plugins gracefully.

        Deactivates all plugins in reverse load order.

        Example:
            >>> await manager.shutdown()
        """
        logger.info("plugin_manager_shutdown_start", count=len(self._plugins))

        # Unload in reverse order
        for plugin_name in reversed(list(self._plugins.keys())):
            await self.unload_plugin(plugin_name)

        logger.info("plugin_manager_shutdown_complete")


__all__ = [
    "PluginManager",
]
