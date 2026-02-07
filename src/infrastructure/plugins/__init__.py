"""Plugin system for extensible framework architecture.

The plugin system enables extending the framework without modifying core code.
This follows the Open/Closed Principle and allows for:

- Hot-reloadable plugins
- Type-safe plugin interfaces
- Dependency injection
- Automatic discovery
- Lifecycle management

Example:
    >>> from src.infrastructure.plugins import PluginManager
    >>> from src.infrastructure.plugins.builtin import EmailPlugin
    >>>
    >>> manager = PluginManager()
    >>> await manager.discover_plugins("src/plugins")
    >>> await manager.load_all()
    >>>
    >>> email = manager.get_plugin("sendgrid-email", EmailPlugin)
    >>> await email.send_email("user@example.com", "Hello", "World")
"""

from src.infrastructure.plugins.base import (
    Plugin,
    PluginContext,
    PluginInterface,
    PluginLoadError,
    PluginMetadata,
    PluginStatus,
)
from src.infrastructure.plugins.manager import PluginManager


__all__ = [
    "Plugin",
    "PluginContext",
    "PluginInterface",
    "PluginLoadError",
    "PluginManager",
    "PluginMetadata",
    "PluginStatus",
]
