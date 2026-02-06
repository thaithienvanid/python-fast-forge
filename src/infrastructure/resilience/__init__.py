"""Resilience patterns for fault tolerance and system stability.

This package provides implementations of common resilience patterns:
- Circuit Breaker: Prevent cascading failures
- Retry: Automatic retry with exponential backoff (future)
- Timeout: Operation timeouts (future)
- Bulkhead: Resource isolation (future)
- Rate Limiter: Request throttling (future)
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerStats,
    CircuitState,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerStats",
    "CircuitState",
]
