"""Rate limiting middleware using SlowAPI.

Implements rate limiting to prevent API abuse and ensure fair usage
across all clients. Uses Redis for distributed rate limiting.
"""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.infrastructure.config import Settings


# Type alias for rate limit handler (slowapi uses sync handlers)
RateLimitHandler = Callable[[Request, Any], Response]


def get_client_identifier(request: Request) -> str:
    """Get client identifier for rate limiting.

    Uses client IP from request state (set by RequestContextMiddleware).
    Falls back to get_remote_address if not available.

    This ensures consistent client identification across:
    - Cloudflare (CF-Connecting-IP)
    - Reverse proxies (X-Forwarded-For, X-Real-IP)
    - Direct connections
    """
    # Use client_ip from request state (set by RequestContextMiddleware)
    if hasattr(request.state, "client_ip"):
        return str(request.state.client_ip)

    # Fallback to slowapi's default (not recommended for production)
    return str(get_remote_address(request))


def get_limiter(settings: Settings) -> Limiter:
    """Create rate limiter instance with Redis backend.

    For multi-instance deployments, slowapi uses Redis as a shared backend.
    The Redis URL from settings is automatically used by slowapi when available.

    Note: slowapi automatically detects Redis connection from REDIS_URL env var
    and uses it as storage backend. If Redis is not available, it falls back
    to in-memory storage (not suitable for multi-instance deployments).
    """
    return Limiter(
        key_func=get_client_identifier,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"],
        enabled=settings.rate_limit_enabled,
        # slowapi reads REDIS_URL from environment automatically
        # and uses Redis as storage backend for distributed rate limiting
        storage_uri=settings.redis_url if settings.rate_limit_enabled else None,
    )


def setup_rate_limiting(app: FastAPI, settings: Settings) -> Limiter:
    """Configure rate limiting for the application.

    Uses Redis as shared storage backend for multi-instance support.
    Clients are identified by their real IP address (from Cloudflare/proxy headers).
    """
    limiter = get_limiter(settings)
    app.state.limiter = limiter

    # Cast handler to expected type
    handler: RateLimitHandler = _rate_limit_exceeded_handler
    app.add_exception_handler(RateLimitExceeded, handler)
    return limiter
