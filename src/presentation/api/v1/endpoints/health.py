"""Health check endpoints for monitoring and orchestration.

Provides liveness and readiness probes for Kubernetes/Docker
health checks and load balancer routing decisions.
"""

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from src.container import Container
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.persistence.database import Database


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    environment: str
    database: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "version": "1.0.0",
                    "environment": "production",
                    "database": "healthy",
                }
            ]
        }
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="""
Check if the API and its dependencies are operational.

This endpoint performs health checks on:
- Application status
- Database connectivity

Use this endpoint for:
- Load balancer health checks
- Monitoring and alerting
- Deployment verification
    """,
)
@inject
async def health_check(
    database: Annotated[Database, Depends(Provide[Container.database])],
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Health check endpoint using DI container.

    Returns the status of the application and its dependencies.

    Args:
        database: Injected database instance from DI container
        settings: Application settings

    Returns:
        Health status including database connectivity
    """
    db_status = "healthy" if await database.health_check() else "unhealthy"

    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
        database=db_status,
    )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="API Root",
    description="""
Root endpoint that confirms the API is running and provides navigation links.

Returns links to:
- API documentation (Swagger UI)
- Health check endpoint
    """,
)
async def root() -> dict[str, str]:
    """Root endpoint providing API information and navigation links."""
    return {
        "message": "Welcome to FastAPI Boilerplate",
        "docs": "/docs",
        "health": "/health",
    }
