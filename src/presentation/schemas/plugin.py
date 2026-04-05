"""Plugin system response schemas.

Pydantic models for plugin management API responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class PluginMetadataResponse(BaseModel):
    """Plugin metadata response model."""

    name: str = Field(..., description="Unique plugin name")
    version: str = Field(..., description="Plugin version (semver)")
    description: str = Field(..., description="Plugin description")
    author: str | None = Field(None, description="Plugin author")
    dependencies: list[str] = Field(default_factory=list, description="Plugin dependencies")
    tags: list[str] = Field(default_factory=list, description="Plugin tags/categories")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "email",
                    "version": "1.0.0",
                    "description": "Email delivery plugin (SMTP + SendGrid)",
                    "author": "Python Fast Forge Team",
                    "dependencies": [],
                    "tags": ["email", "messaging", "communication"],
                }
            ]
        }
    }


class PluginStatusResponse(BaseModel):
    """Plugin status response model."""

    name: str = Field(..., description="Plugin name")
    is_active: bool = Field(..., description="Whether plugin is currently active")
    is_loaded: bool = Field(..., description="Whether plugin is loaded")
    health: str = Field(..., description="Plugin health status (healthy/unhealthy/unknown)")
    health_message: str | None = Field(None, description="Health check message")
    metadata: PluginMetadataResponse = Field(..., description="Plugin metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "email",
                    "is_active": True,
                    "is_loaded": True,
                    "health": "healthy",
                    "health_message": "SMTP connection successful",
                    "metadata": {
                        "name": "email",
                        "version": "1.0.0",
                        "description": "Email delivery plugin",
                        "author": "Python Fast Forge Team",
                        "dependencies": [],
                        "tags": ["email"],
                    },
                }
            ]
        }
    }


class PluginListResponse(BaseModel):
    """Plugin list response model."""

    total: int = Field(..., description="Total number of plugins")
    loaded: int = Field(..., description="Number of loaded plugins")
    active: int = Field(..., description="Number of active plugins")
    plugins: list[PluginStatusResponse] = Field(..., description="List of plugins")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total": 3,
                    "loaded": 3,
                    "active": 2,
                    "plugins": [
                        {
                            "name": "email",
                            "is_active": True,
                            "is_loaded": True,
                            "health": "healthy",
                            "health_message": None,
                            "metadata": {
                                "name": "email",
                                "version": "1.0.0",
                                "description": "Email plugin",
                                "author": None,
                                "dependencies": [],
                                "tags": [],
                            },
                        }
                    ],
                }
            ]
        }
    }


class PluginDetailsResponse(BaseModel):
    """Detailed plugin information response."""

    name: str
    is_active: bool
    is_loaded: bool
    metadata: PluginMetadataResponse
    health: str
    health_message: str | None
    configuration: dict[str, Any] = Field(default_factory=dict, description="Plugin configuration")
    capabilities: list[str] = Field(default_factory=list, description="Plugin capabilities")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "email",
                    "is_active": True,
                    "is_loaded": True,
                    "metadata": {
                        "name": "email",
                        "version": "1.0.0",
                        "description": "Email plugin",
                        "author": None,
                        "dependencies": [],
                        "tags": ["email"],
                    },
                    "health": "healthy",
                    "health_message": "All providers operational",
                    "configuration": {"smtp_host": "localhost", "smtp_port": 587},
                    "capabilities": ["send_email", "send_bulk_email", "send_template_email"],
                }
            ]
        }
    }


class PluginHealthResponse(BaseModel):
    """Plugin health check response."""

    name: str
    health: str
    message: str | None
    details: dict[str, Any] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "email",
                    "health": "healthy",
                    "message": "SMTP connection successful, SendGrid API reachable",
                    "details": {"smtp_status": "connected", "sendgrid_status": "ok"},
                }
            ]
        }
    }


class PluginActionResponse(BaseModel):
    """Generic plugin action response."""

    success: bool
    message: str
    plugin_name: str
    action: str  # "activated", "deactivated", "reloaded"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Plugin 'email' activated successfully",
                    "plugin_name": "email",
                    "action": "activated",
                }
            ]
        }
    }


__all__ = [
    "PluginActionResponse",
    "PluginDetailsResponse",
    "PluginHealthResponse",
    "PluginListResponse",
    "PluginMetadataResponse",
    "PluginStatusResponse",
]
