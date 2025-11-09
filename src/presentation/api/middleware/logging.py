"""HTTP request/response logging middleware.

This middleware logs all incoming HTTP requests and outgoing responses
with timing information, enabling observability, debugging, and performance
monitoring.
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive HTTP request/response logging.

    Logs:
    - HTTP method and URL
    - Response status code
    - Request processing duration
    - Additional context from request state
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request, measure duration, and log details.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in the chain

        Returns:
            HTTP response from downstream handlers
        """
        start_time = time.time()

        # Process request through handler chain
        response = await call_next(request)

        # Calculate processing duration
        duration = time.time() - start_time

        # Log request completion with metrics
        logger.info(
            "request_completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            duration=f"{duration:.3f}s",
        )

        return response
