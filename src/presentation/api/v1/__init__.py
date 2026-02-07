from fastapi import APIRouter

from src.presentation.api.v1.endpoints import (
    compliance,
    health,
    partners,
    sse,
    users,
    websocket,
)

api_router = APIRouter()

# Include routers
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(partners.router)
api_router.include_router(compliance.router)
api_router.include_router(websocket.router)
api_router.include_router(sse.router)
