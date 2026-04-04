"""Plugin system base interfaces and protocols.

The plugin system enables extending the framework without modifying core code.
This follows the Open/Closed Principle - open for extension, closed for modification.

Plugin Architecture:
- Plugin Protocol: Interface that all plugins must implement
- Plugin Metadata: Name, version, dependencies, configuration schema
- Plugin Lifecycle: init() → validate() → activate() → deactivate()
- Plugin Registry: Discovers, loads, and manages plugins

Benefits:
- Extensibility without core modification
- Hot-reload capability
- Dependency injection integration
- Type-safe plugin interfaces
- Isolated plugin failures

Use Cases:
- Email providers (SendGrid, SES, SMTP)
- Storage backends (S3, GCS, Azure Blob)
- Authentication providers (OAuth, SAML, LDAP)
- Payment gateways (Stripe, PayPal)
- Notification services (Slack, Discord, Teams)

Example:
    >>> class MyEmailPlugin(Plugin):
    ...     async def init(self) -> None:
    ...         self._client = create_email_client(self.config)
    ...
    ...     async def send_email(self, to: str, subject: str, body: str) -> None:
    ...         await self._client.send(to, subject, body)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class PluginStatus(str, Enum):
    """Plugin lifecycle status.

    Attributes:
        UNINITIALIZED: Plugin registered but not initialized
        INITIALIZING: Plugin initialization in progress
        INITIALIZED: Plugin initialized successfully
        ACTIVATING: Plugin activation in progress
        ACTIVE: Plugin active and ready to use
        DEACTIVATING: Plugin deactivation in progress
        DEACTIVATED: Plugin deactivated
        FAILED: Plugin failed during lifecycle
    """

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    DEACTIVATED = "deactivated"
    FAILED = "failed"


class PluginMetadata(BaseModel):
    """Plugin metadata and configuration.

    Describes plugin capabilities, dependencies, and configuration schema.

    Attributes:
        name: Unique plugin name (e.g., "sendgrid-email")
        version: Semantic version (e.g., "1.0.0")
        description: Human-readable description
        author: Plugin author/maintainer
        plugin_type: Plugin category (e.g., "email", "storage", "auth")
        dependencies: Required plugin dependencies
        config_schema: JSON schema for plugin configuration
        tags: Searchable tags for plugin discovery

    Example:
        >>> metadata = PluginMetadata(
        ...     name="sendgrid-email",
        ...     version="1.0.0",
        ...     description="SendGrid email provider",
        ...     plugin_type="email",
        ...     dependencies=["http-client"],
        ...     config_schema={
        ...         "type": "object",
        ...         "properties": {
        ...             "api_key": {"type": "string"},
        ...             "from_email": {"type": "string", "format": "email"},
        ...         },
        ...         "required": ["api_key"],
        ...     },
        ... )
    """

    name: str = Field(..., description="Unique plugin identifier")
    version: str = Field(..., description="Semantic version", pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(..., description="Human-readable description")
    author: str = Field(..., description="Plugin author/maintainer")
    plugin_type: str = Field(..., description="Plugin category (email, storage, auth, etc.)")
    dependencies: list[str] = Field(default_factory=list, description="Required plugin names")
    config_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for configuration"
    )
    tags: list[str] = Field(default_factory=list, description="Searchable tags")

    model_config = ConfigDict(frozen=True)  # Immutable


@dataclass
class PluginContext:
    """Runtime context provided to plugins.

    This context is injected into plugins during initialization,
    providing access to shared resources and services.

    Attributes:
        config: Plugin-specific configuration (validated against schema)
        app_config: Global application configuration (read-only)
        logger: Logger instance for plugin
        event_bus: Event bus for publishing domain events
        cache: Cache client (Redis)
        metrics: Metrics collector (Prometheus, StatsD)
        dependencies: Dependency injection container

    Example:
        >>> context = PluginContext(
        ...     config={"api_key": "sk_..."},
        ...     app_config=app.config,
        ...     logger=get_logger("plugin.sendgrid"),
        ...     event_bus=event_bus,
        ... )
        >>> plugin.init(context)
    """

    config: dict[str, Any]
    app_config: dict[str, Any] = field(default_factory=dict)
    logger: Any | None = None
    event_bus: Any | None = None
    cache: Any | None = None
    metrics: Any | None = None
    dependencies: dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """Base class for all plugins.

    Plugins must inherit from this class and implement the abstract methods.
    The plugin lifecycle is managed by the PluginManager.

    Lifecycle:
        1. __init__() - Plugin instantiated
        2. init(context) - Initialize resources
        3. validate() - Validate configuration
        4. activate() - Activate plugin (start background tasks, etc.)
        5. deactivate() - Deactivate plugin (cleanup, stop tasks)

    Attributes:
        metadata: Plugin metadata (name, version, type, etc.)
        status: Current plugin status
        context: Runtime context (config, logger, dependencies)
        error: Last error message (if status == FAILED)

    Example:
        >>> class SendGridEmailPlugin(Plugin):
        ...     @property
        ...     def metadata(self) -> PluginMetadata:
        ...         return PluginMetadata(
        ...             name="sendgrid-email",
        ...             version="1.0.0",
        ...             description="SendGrid email provider",
        ...             plugin_type="email",
        ...         )
        ...
        ...     async def init(self, context: PluginContext) -> None:
        ...         self.context = context
        ...         self._client = SendGridClient(api_key=context.config["api_key"])
        ...
        ...     async def validate(self) -> bool:
        ...         return "api_key" in self.context.config
        ...
        ...     async def activate(self) -> None:
        ...         # Test API connection
        ...         await self._client.ping()
        ...
        ...     async def deactivate(self) -> None:
        ...         await self._client.close()
    """

    def __init__(self):
        """Initialize plugin."""
        self.status: PluginStatus = PluginStatus.UNINITIALIZED
        self.context: PluginContext | None = None
        self.error: str | None = None
        self._activated_at: datetime | None = None
        self._deactivated_at: datetime | None = None

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata.

        Returns:
            Plugin metadata with name, version, type, etc.
        """

    @abstractmethod
    async def init(self, context: PluginContext) -> None:
        """Initialize plugin with runtime context.

        Called once during plugin loading. Initialize resources,
        connections, clients, etc.

        Args:
            context: Runtime context with config, logger, dependencies

        Raises:
            Exception: If initialization fails
        """

    @abstractmethod
    async def validate(self) -> bool:
        """Validate plugin configuration and state.

        Called after init() to verify the plugin is properly configured
        and ready to activate.

        Returns:
            True if valid, False otherwise

        Example:
            >>> async def validate(self) -> bool:
            ...     # Check required config keys
            ...     if "api_key" not in self.context.config:
            ...         return False
            ...     # Test connection
            ...     return await self._client.test_connection()
        """

    async def activate(self) -> None:
        """Activate plugin.

        Called after validation to activate the plugin. Start background
        tasks, subscribe to events, register endpoints, etc.

        This method is optional - override only if needed.

        Example:
            >>> async def activate(self) -> None:
            ...     # Start background task
            ...     self._task = asyncio.create_task(self._background_worker())
            ...     # Subscribe to events
            ...     self.context.event_bus.subscribe("user.created", self._on_user_created)
        """

    async def deactivate(self) -> None:
        """Deactivate plugin.

        Called during plugin unload or application shutdown. Cleanup
        resources, close connections, cancel tasks, etc.

        This method is optional - override only if needed.

        Example:
            >>> async def deactivate(self) -> None:
            ...     # Cancel background task
            ...     self._task.cancel()
            ...     # Close connections
            ...     await self._client.close()
        """

    def is_active(self) -> bool:
        """Check if plugin is currently active.

        Returns:
            True if plugin status is ACTIVE, False otherwise

        Example:
            >>> if plugin.is_active():
            ...     await plugin.do_work()
        """
        return self.status == PluginStatus.ACTIVE

    async def health_check(self) -> dict[str, Any]:
        """Check plugin health.

        Returns health status for monitoring/diagnostics.

        Returns:
            Health status dictionary

        Example:
            >>> health = await plugin.health_check()
            >>> print(health)
            {
                "status": "healthy",
                "response_time_ms": 45,
                "last_error": None,
                "uptime_seconds": 3600,
            }
        """
        return {
            "status": self.status.value,
            "error": self.error,
            "activated_at": self._activated_at.isoformat() if self._activated_at else None,
        }


class PluginInterface(Protocol):
    """Protocol for type-safe plugin interfaces.

    Use this to define plugin type interfaces without inheritance.
    This allows for structural subtyping (duck typing with type safety).

    Example:
        >>> class EmailPlugin(PluginInterface):
        ...     async def send_email(self, to: str, subject: str, body: str) -> None: ...
        >>> class SendGridEmailPlugin(Plugin):
        ...     async def send_email(self, to: str, subject: str, body: str) -> None:
        ...         await self._client.send(to, subject, body)
        >>> # Type checker knows SendGridEmailPlugin implements EmailPlugin
        >>> plugin: EmailPlugin = SendGridEmailPlugin()
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        ...

    async def init(self, context: PluginContext) -> None:
        """Initialize plugin."""
        ...

    async def validate(self) -> bool:
        """Validate plugin."""
        ...


@dataclass
class PluginLoadError(Exception):
    """Plugin loading failed.

    Raised when a plugin cannot be loaded, initialized, or validated.

    Attributes:
        plugin_name: Name of the plugin that failed
        reason: Human-readable error reason
        original_error: Original exception (if any)
    """

    plugin_name: str
    reason: str
    original_error: Exception | None = None

    def __str__(self) -> str:
        """String representation."""
        msg = f"Failed to load plugin '{self.plugin_name}': {self.reason}"
        if self.original_error:
            msg += f" (caused by: {self.original_error})"
        return msg


__all__ = [
    "Plugin",
    "PluginContext",
    "PluginInterface",
    "PluginLoadError",
    "PluginMetadata",
    "PluginStatus",
]
