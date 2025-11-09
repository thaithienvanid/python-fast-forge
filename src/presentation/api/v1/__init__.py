from fastapi import APIRouter

from src.presentation.api.v1.endpoints import health, partners, users


api_router = APIRouter()

# Include routers
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(partners.router)
