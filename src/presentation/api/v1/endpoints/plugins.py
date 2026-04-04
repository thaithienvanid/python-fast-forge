"""Plugin management API endpoints.

Provides endpoints for discovering, managing, and monitoring plugins.
"""

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from src.container import Container
from src.infrastructure.plugins.base import Plugin
from src.infrastructure.plugins.manager import PluginManager
from src.presentation.schemas.plugin import (
    PluginActionResponse,
    PluginDetailsResponse,
    PluginHealthResponse,
    PluginListResponse,
    PluginMetadataResponse,
    PluginStatusResponse,
)


router = APIRouter(tags=["plugins"], prefix="/plugins")


@router.get(
    "",
    response_model=PluginListResponse,
    status_code=status.HTTP_200_OK,
    summary="List All Plugins",
    description="""
List all discovered plugins with their status.

Returns:
- Total number of plugins
- Loaded and active plugin counts
- Status for each plugin (loaded, active, health)

Use this endpoint to:
- Monitor plugin system status
- Discover available plugins
- Check plugin activation state
    """,
)
@inject
async def list_plugins(
    plugin_manager: Annotated[PluginManager, Depends(Provide[Container.plugin_manager])],
) -> PluginListResponse:
    """List all plugins with their current status.

    Args:
        plugin_manager: Injected plugin manager instance

    Returns:
        List of all plugins with status information
    """
    all_plugins = plugin_manager.get_all_plugins()
    loaded_plugins = plugin_manager.get_loaded_plugins()
    active_count = sum(1 for p in loaded_plugins.values() if p.is_active())

    plugin_statuses = []
    for name, plugin in loaded_plugins.items():
        # Get health status
        try:
            health_result = await plugin.health_check()
            health_status = "healthy" if health_result else "unhealthy"
            health_message = None
        except Exception as e:
            health_status = "unknown"
            health_message = str(e)

        # Build metadata
        metadata = PluginMetadataResponse(
            name=plugin.metadata.name,
            version=plugin.metadata.version,
            description=plugin.metadata.description or "",
            author=plugin.metadata.author,
            dependencies=plugin.metadata.dependencies or [],
            tags=plugin.metadata.tags or [],
        )

        plugin_statuses.append(
            PluginStatusResponse(
                name=name,
                is_active=plugin.is_active(),
                is_loaded=True,
                health=health_status,
                health_message=health_message,
                metadata=metadata,
            )
        )

    return PluginListResponse(
        total=len(all_plugins),
        loaded=len(loaded_plugins),
        active=active_count,
        plugins=plugin_statuses,
    )


@router.get(
    "/{plugin_name}",
    response_model=PluginDetailsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Plugin Details",
    description="""
Get detailed information about a specific plugin.

Returns:
- Plugin metadata (name, version, description, author)
- Current status (loaded, active)
- Health check results
- Configuration (non-sensitive)
- Capabilities

Useful for:
- Troubleshooting plugin issues
- Understanding plugin features
- Monitoring individual plugin health
    """,
)
@inject
async def get_plugin(
    plugin_name: str,
    plugin_manager: Annotated[PluginManager, Depends(Provide[Container.plugin_manager])],
) -> PluginDetailsResponse:
    """Get detailed information about a specific plugin.

    Args:
        plugin_name: Name of the plugin to retrieve
        plugin_manager: Injected plugin manager instance

    Returns:
        Detailed plugin information

    Raises:
        HTTPException: 404 if plugin not found
    """
    plugin: Plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found",
        )

    # Get health status
    try:
        health_result = await plugin.health_check()
        health_status = "healthy" if health_result else "unhealthy"
        health_message = None
    except Exception as e:
        health_status = "unknown"
        health_message = str(e)

    # Build metadata
    metadata = PluginMetadataResponse(
        name=plugin.metadata.name,
        version=plugin.metadata.version,
        description=plugin.metadata.description or "",
        author=plugin.metadata.author,
        dependencies=plugin.metadata.dependencies or [],
        tags=plugin.metadata.tags or [],
    )

    # Get plugin capabilities (methods the plugin provides)
    capabilities = []
    if hasattr(plugin, "get_capabilities"):
        capabilities = plugin.get_capabilities()

    # Get plugin configuration (sanitized - no secrets)
    configuration = {}
    if hasattr(plugin, "get_configuration"):
        configuration = plugin.get_configuration()

    return PluginDetailsResponse(
        name=plugin_name,
        is_active=plugin.is_active(),
        is_loaded=True,
        metadata=metadata,
        health=health_status,
        health_message=health_message,
        configuration=configuration,
        capabilities=capabilities,
    )


@router.get(
    "/{plugin_name}/health",
    response_model=PluginHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Plugin Health Check",
    description="""
Perform health check on a specific plugin.

Returns:
- Health status (healthy/unhealthy/unknown)
- Health message with details
- Additional diagnostic information

Use this for:
- Monitoring plugin availability
- Troubleshooting plugin issues
- Alerting on plugin failures
    """,
)
@inject
async def plugin_health(
    plugin_name: str,
    plugin_manager: Annotated[PluginManager, Depends(Provide[Container.plugin_manager])],
) -> PluginHealthResponse:
    """Check health of a specific plugin.

    Args:
        plugin_name: Name of the plugin to check
        plugin_manager: Injected plugin manager instance

    Returns:
        Health check results

    Raises:
        HTTPException: 404 if plugin not found
    """
    plugin: Plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found",
        )

    try:
        health_result = await plugin.health_check()
        health_status = "healthy" if health_result else "unhealthy"
        message = "Plugin is operational" if health_result else "Plugin health check failed"
        details = None
    except Exception as e:
        health_status = "unknown"
        message = f"Health check error: {e!s}"
        details = {"error": str(e), "error_type": type(e).__name__}

    return PluginHealthResponse(
        name=plugin_name,
        health=health_status,
        message=message,
        details=details,
    )


@router.post(
    "/{plugin_name}/activate",
    response_model=PluginActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Plugin",
    description="""
Activate a plugin, making it available for use.

Actions performed:
1. Load plugin if not already loaded
2. Activate plugin (calls plugin.activate())
3. Verify activation successful

Use this to:
- Enable a plugin after deployment
- Re-enable a temporarily disabled plugin
- Start using a newly discovered plugin
    """,
)
@inject
async def activate_plugin(
    plugin_name: str,
    plugin_manager: Annotated[PluginManager, Depends(Provide[Container.plugin_manager])],
) -> PluginActionResponse:
    """Activate a plugin.

    Args:
        plugin_name: Name of the plugin to activate
        plugin_manager: Injected plugin manager instance

    Returns:
        Activation result

    Raises:
        HTTPException: 404 if plugin not found, 500 if activation fails
    """
    try:
        # Load plugin if not already loaded
        plugin: Plugin | None = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            # Try to discover and load
            await plugin_manager.discover_plugins()
            plugin = plugin_manager.get_plugin(plugin_name)

            if not plugin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Plugin '{plugin_name}' not found",
                )

        # Activate if not already active
        if not plugin.is_active():
            await plugin.activate()

        return PluginActionResponse(
            success=True,
            message=f"Plugin '{plugin_name}' activated successfully",
            plugin_name=plugin_name,
            action="activated",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate plugin '{plugin_name}': {e!s}",
        ) from e


@router.post(
    "/{plugin_name}/deactivate",
    response_model=PluginActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Plugin",
    description="""
Deactivate a plugin, making it unavailable for use.

Actions performed:
1. Check plugin is loaded
2. Deactivate plugin (calls plugin.deactivate())
3. Cleanup resources
4. Verify deactivation successful

Use this to:
- Temporarily disable a plugin
- Stop a misbehaving plugin
- Prepare for plugin updates
    """,
)
@inject
async def deactivate_plugin(
    plugin_name: str,
    plugin_manager: Annotated[PluginManager, Depends(Provide[Container.plugin_manager])],
) -> PluginActionResponse:
    """Deactivate a plugin.

    Args:
        plugin_name: Name of the plugin to deactivate
        plugin_manager: Injected plugin manager instance

    Returns:
        Deactivation result

    Raises:
        HTTPException: 404 if plugin not found, 500 if deactivation fails
    """
    plugin: Plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found",
        )

    try:
        if plugin.is_active():
            await plugin.deactivate()

        return PluginActionResponse(
            success=True,
            message=f"Plugin '{plugin_name}' deactivated successfully",
            plugin_name=plugin_name,
            action="deactivated",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate plugin '{plugin_name}': {e!s}",
        ) from e


@router.post(
    "/{plugin_name}/reload",
    response_model=PluginActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reload Plugin",
    description="""
Hot-reload a plugin with updated configuration or code.

Actions performed:
1. Deactivate plugin
2. Unload plugin from memory
3. Rediscover and reload plugin
4. Reactivate plugin
5. Verify reload successful

Use this to:
- Apply configuration changes without restart
- Update plugin code during development
- Recover from plugin errors
    """,
)
@inject
async def reload_plugin(
    plugin_name: str,
    plugin_manager: Annotated[PluginManager, Depends(Provide[Container.plugin_manager])],
) -> PluginActionResponse:
    """Reload a plugin (hot-reload).

    Args:
        plugin_name: Name of the plugin to reload
        plugin_manager: Injected plugin manager instance

    Returns:
        Reload result

    Raises:
        HTTPException: 404 if plugin not found, 500 if reload fails
    """
    plugin: Plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' not found",
        )

    try:
        was_active = plugin.is_active()

        # Deactivate and unload
        if was_active:
            await plugin.deactivate()
        await plugin_manager.unload_plugin(plugin_name)

        # Rediscover and reload
        await plugin_manager.discover_plugins()
        plugin = plugin_manager.get_plugin(plugin_name)

        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' not found after reload")

        # Reactivate if it was active before
        if was_active:
            await plugin.activate()

        return PluginActionResponse(
            success=True,
            message=f"Plugin '{plugin_name}' reloaded successfully",
            plugin_name=plugin_name,
            action="reloaded",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload plugin '{plugin_name}': {e!s}",
        ) from e


__all__ = ["router"]
