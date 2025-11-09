"""CORS (Cross-Origin Resource Sharing) middleware configuration.

Configures CORS settings for the FastAPI application to control which
origins can access the API and what methods/headers are allowed.
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.infrastructure.config import Settings


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
        expose_headers=settings.cors_expose_headers,
    )
