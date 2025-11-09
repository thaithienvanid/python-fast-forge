"""Circuit breaker pattern for resilient external service calls.

This module implements the circuit breaker pattern to prevent cascading
failures when calling external services. It monitors failure rates and
temporarily halts requests to failing services, allowing them time to recover.
"""

from collections.abc import Callable
from typing import Any

import pybreaker
from pybreaker import CircuitBreaker

from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)


class CircuitBreakerService:
    """Manages circuit breakers for external service resilience.

    The circuit breaker pattern prevents cascading failures by:
    1. Monitoring failure rates for external service calls
    2. Opening the circuit (blocking calls) when failure threshold is exceeded
    3. Periodically attempting to close the circuit (resume calls) after recovery time
    4. Logging state transitions for observability

    Circuit States:
        - Closed: Normal operation, requests pass through
        - Open: Too many failures, requests are blocked immediately
        - Half-Open: Testing recovery, limited requests allowed
    """

    def __init__(self) -> None:
        """Initialize circuit breaker service with empty breaker registry."""
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_breaker(
        self,
        name: str,
        fail_max: int = 5,
        timeout_duration: int = 60,
        reset_timeout: int = 30,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for a named service.

        Args:
            name: Unique identifier for the circuit breaker (typically service name)
            fail_max: Number of consecutive failures before opening circuit
            timeout_duration: Operation timeout in seconds
            reset_timeout: Seconds to wait before attempting to close circuit

        Returns:
            Circuit breaker instance for the named service
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                fail_max=fail_max,
                reset_timeout=reset_timeout,
                name=name,
                listeners=[self._create_listener(name)],
            )
            logger.info(
                "circuit_breaker_created",
                name=name,
                fail_max=fail_max,
                timeout=timeout_duration,
            )
        return self._breakers[name]

    def _create_listener(self, name: str) -> pybreaker.CircuitBreakerListener:
        """Create event listener for circuit breaker monitoring.

        Args:
            name: Circuit breaker name for logging context

        Returns:
            Circuit breaker listener that logs state changes and failures
        """

        class LoggingListener(pybreaker.CircuitBreakerListener):
            """Logs circuit breaker state transitions and call outcomes."""

            def state_change(self, cb: CircuitBreaker, old_state: Any, new_state: Any) -> None:
                """Log circuit state transitions (closed → open → half-open).

                Args:
                    cb: Circuit breaker instance
                    old_state: Previous circuit state
                    new_state: New circuit state
                """
                logger.warning(
                    "circuit_breaker_state_change",
                    breaker=name,
                    old_state=str(old_state),
                    new_state=str(new_state),
                )

            def failure(self, cb: CircuitBreaker, exc: BaseException) -> None:
                """Log service call failures and current failure count.

                Args:
                    cb: Circuit breaker instance
                    exc: Exception that caused the failure
                """
                logger.error(
                    "circuit_breaker_failure",
                    breaker=name,
                    error=str(exc),
                    failure_count=cb.fail_counter,
                )

            def success(self, cb: CircuitBreaker) -> None:
                """Log successful service calls.

                Args:
                    cb: Circuit breaker instance
                """
                logger.debug("circuit_breaker_success", breaker=name)

        return LoggingListener()

    async def call_with_breaker(
        self,
        breaker_name: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            breaker_name: Name of circuit breaker to use
            func: Async function to call with protection
            args: Positional arguments for function
            kwargs: Keyword arguments for function

        Returns:
            Function result if successful

        Raises:
            CircuitBreakerError: If circuit is open (service unavailable)
            Exception: Any exception raised by the protected function
        """
        breaker = self.get_breaker(breaker_name)
        return await breaker.call_async(func, *args, **kwargs)  # type: ignore[no-untyped-call]
