"""FastAPI application factory and configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.container import Container
from src.infrastructure.config import Settings, get_settings
from src.infrastructure.logging.config import configure_logging, get_logger
from src.infrastructure.telemetry import configure_opentelemetry, instrument_fastapi
from src.presentation.api.middleware.cors import setup_cors
from src.presentation.api.middleware.error_handling import setup_exception_handlers
from src.presentation.api.middleware.logging import LoggingMiddleware
from src.presentation.api.middleware.rate_limiting import setup_rate_limiting
from src.presentation.api.middleware.request_context import RequestContextMiddleware
from src.presentation.api.middleware.security_headers import SecurityHeadersMiddleware
from src.presentation.api.v1 import api_router


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan events."""
    # Startup
    logger.info("application_startup", app_name=app.title, version=app.version)

    # Initialize cache
    try:
        cache = app.state.container.cache()
        await cache.connect()
        logger.info("cache_initialized")
    except Exception as e:
        logger.error("cache_initialization_failed", error=str(e))

    yield

    # Shutdown
    try:
        cache = app.state.container.cache()
        await cache.disconnect()
        logger.info("cache_disconnected")
    except Exception as e:
        logger.error("cache_disconnect_failed", error=str(e))

    logger.info("application_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    # Configure OpenTelemetry (before logging)
    configure_opentelemetry(settings)

    # Configure logging (with trace context)
    configure_logging(settings)

    # Create and wire dependency injection container
    container = Container()
    container.wire(
        modules=[
            "src.presentation.api.v1.endpoints.users",
            "src.presentation.api.v1.endpoints.health",
        ]
    )

    # OpenAPI tags for documentation organization
    tags_metadata = [
        {
            "name": "health",
            "description": """
Health check and monitoring endpoints.

Use these endpoints to verify the API and its dependencies are operational.
            """,
        },
        {
            "name": "users",
            "description": """
User management endpoints with CRUD operations.

### Features
- **Multi-tenancy**: Isolate users by tenant via `X-Tenant-ID` header
- **Soft Delete**: Recoverable deletion with restore capability
- **Batch Operations**: Create multiple users atomically with Unit of Work pattern
- **Validation**: Email and username format validation
- **Pagination**: List endpoints support skip/limit parameters

### Tenant Isolation
Include the `X-Tenant-ID` header to filter operations by tenant.
Without this header, operations are tenant-agnostic.
            """,
        },
        {
            "name": "Partners (API Signature Auth)",
            "description": """
B2B partner endpoints requiring HMAC-SHA256 signature authentication.

### Authentication
All endpoints require the following headers:
- **X-API-Client-ID**: Your unique client identifier
- **X-API-Timestamp**: ISO 8601 timestamp (must be within 5 minutes)
- **X-API-Signature**: HMAC-SHA256 signature of the request

### Signature Generation
```python
import hmac
import hashlib
from datetime import datetime, timezone

timestamp = datetime.now(timezone.utc).isoformat()
signature_string = f"{method}\\n{path}\\n{timestamp}\\n{body_hash}"
signature = hmac.new(
    client_secret.encode(),
    signature_string.encode(),
    hashlib.sha256
).hexdigest()
```

See individual endpoints for detailed examples.
            """,
        },
    ]

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
# Python FastAPI Boilerplate

A production-ready FastAPI boilerplate with **Clean Architecture**, comprehensive features, and best practices.

## Features

### Architecture & Patterns
- **Clean Architecture**: Domain, Application, Infrastructure, and Presentation layers
- **Unit of Work Pattern**: Atomic transactions for batch operations
- **Repository Pattern**: Data access abstraction with caching support
- **Dependency Injection**: Using `dependency-injector` for IoC
- **Soft Delete**: Recoverable deletion with `deleted_at` timestamps

### Security
- **API Signature Authentication**: HMAC-SHA256 request signing for B2B partners
- **Multi-tenancy Support**: Tenant isolation via `X-Tenant-ID` header
- **Security Headers**: Comprehensive security headers (CSP, HSTS, X-Frame-Options, etc.)
- **Rate Limiting**: Redis-backed rate limiting per client

### Observability
- **OpenTelemetry**: Distributed tracing with OTLP export
- **Structured Logging**: JSON logging with trace context
- **Health Checks**: Database and service health monitoring

### Developer Experience
- **FastAPI**: Modern, async, with automatic OpenAPI docs
- **Type Safety**: Full type hints with MyPy validation
- **Testing**: Comprehensive unit and integration tests
- **Docker**: Development and production Docker setup with profiles
        """,
        openapi_tags=tags_metadata,
        contact={
            "name": "API Support",
            "url": "https://github.com/thaithienvanid/python-fast-forge",
            "email": "support@example.com",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
        servers=[
            {
                "url": "http://localhost:8000",
                "description": "Local development server",
            },
            {
                "url": "https://api.example.com",
                "description": "Production server",
            },
        ],
    )

    # Store container in app state for access if needed
    app.state.container = container

    # Instrument FastAPI with OpenTelemetry
    if settings.otel_enabled:
        instrument_fastapi(app)

    # Setup exception handlers
    setup_exception_handlers(app)

    # Setup middleware (order matters!)
    # Security headers should be added early in the chain
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(LoggingMiddleware)
    setup_cors(app, settings)
    setup_rate_limiting(app, settings)

    # Include routers
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app
