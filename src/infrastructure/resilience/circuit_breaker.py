"""Circuit breaker pattern for database resilience.

Implements the circuit breaker pattern to prevent cascading failures and improve
system resilience. When a service (like a database) starts failing, the circuit
breaker "opens" to fail fast instead of waiting for timeouts.

Circuit States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail immediately
- HALF_OPEN: Testing if service recovered, limited requests allowed

Example:
    ```python
    from src.infrastructure.resilience.circuit_breaker import CircuitBreaker

    # Create circuit breaker for database operations
    db_breaker = CircuitBreaker(
        failure_threshold=5,  # Open after 5 failures
        recovery_timeout=60,  # Try again after 60 seconds
        half_open_max_calls=3,  # Allow 3 test calls in half-open
    )

    # Use with async function
    async def get_user(user_id):
        return await db_breaker.call(repository.get_by_id, user_id)

    # Or use as decorator
    @db_breaker.protect
    async def get_user(user_id):
        return await repository.get_by_id(user_id)
    ```
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, block requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is blocked."""

    def __init__(self, message: str = "Circuit breaker is OPEN") -> None:
        self.message = message
        super().__init__(self.message)


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    last_state_change: float = field(default_factory=time.time)
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0  # Calls rejected while OPEN


class CircuitBreaker(Generic[T]):
    """Circuit breaker for protecting against cascading failures.

    Implements the circuit breaker pattern with configurable thresholds
    and recovery behavior. Tracks failures and automatically opens the
    circuit to fail fast when thresholds are exceeded.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying half-open
        half_open_max_calls: Max concurrent calls allowed in half-open state
        expected_exceptions: Exception types that trigger circuit opening

    Thread-safe for async operations using asyncio.Lock.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        expected_exceptions: tuple[type[Exception], ...] = (Exception,),
        name: str = "CircuitBreaker",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout: Seconds to wait before transitioning to half-open
            half_open_max_calls: Max calls allowed in half-open state
            expected_exceptions: Exception types that count as failures
            name: Identifier for this circuit breaker (for logging/metrics)
        """
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout < 0:
            raise ValueError("recovery_timeout must be >= 0")
        if half_open_max_calls < 1:
            raise ValueError("half_open_max_calls must be >= 1")

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exceptions = expected_exceptions
        self.name = name

        self._stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._stats.state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self._stats

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Function result if successful

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception if function fails

        Example:
            ```python
            result = await breaker.call(db.query, "SELECT * FROM users")
            ```
        """
        async with self._lock:
            self._stats.total_calls += 1

            # Check if we should try the call
            if not await self._allow_request():
                self._stats.total_rejections += 1
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Last failure: {self._stats.last_failure_time}"
                )

            # Track half-open calls
            if self._stats.state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

        # Execute the function (outside the lock)
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except self.expected_exceptions as e:
            await self._on_failure()
            raise

        finally:
            # Decrement half-open counter
            if self._stats.state == CircuitState.HALF_OPEN:
                async with self._lock:
                    self._half_open_calls -= 1

    def protect(
        self, func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        """Decorator to protect an async function with circuit breaker.

        Args:
            func: Async function to protect

        Returns:
            Wrapped function that goes through circuit breaker

        Example:
            ```python
            @circuit_breaker.protect
            async def get_user(user_id: UUID) -> User:
                return await repository.get_by_id(user_id)
            ```
        """

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.call(func, *args, **kwargs)

        return wrapper

    async def _allow_request(self) -> bool:
        """Check if request should be allowed based on current state.

        Returns:
            True if request can proceed, False if it should be blocked
        """
        if self._stats.state == CircuitState.CLOSED:
            return True

        if self._stats.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._stats.last_failure_time is not None:
                elapsed = time.time() - self._stats.last_failure_time
                if elapsed >= self.recovery_timeout:
                    # Transition to half-open
                    self._stats.state = CircuitState.HALF_OPEN
                    self._stats.last_state_change = time.time()
                    self._half_open_calls = 0
                    return True
            return False

        if self._stats.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self._half_open_calls < self.half_open_max_calls

        return False

    async def _on_success(self) -> None:
        """Handle successful function execution."""
        async with self._lock:
            self._stats.success_count += 1
            self._stats.total_successes += 1

            if self._stats.state == CircuitState.HALF_OPEN:
                # Enough successes in half-open, close the circuit
                if self._stats.success_count >= self.half_open_max_calls:
                    self._stats.state = CircuitState.CLOSED
                    self._stats.failure_count = 0
                    self._stats.success_count = 0
                    self._stats.last_state_change = time.time()

            elif self._stats.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._stats.failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed function execution."""
        async with self._lock:
            self._stats.failure_count += 1
            self._stats.total_failures += 1
            self._stats.last_failure_time = time.time()

            if self._stats.state == CircuitState.HALF_OPEN:
                # Failure in half-open, reopen the circuit
                self._stats.state = CircuitState.OPEN
                self._stats.success_count = 0
                self._stats.last_state_change = time.time()

            elif self._stats.state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self._stats.failure_count >= self.failure_threshold:
                    self._stats.state = CircuitState.OPEN
                    self._stats.success_count = 0
                    self._stats.last_state_change = time.time()

    async def reset(self) -> None:
        """Manually reset circuit breaker to closed state.

        Useful for testing or manual intervention after fixing issues.
        """
        async with self._lock:
            self._stats.state = CircuitState.CLOSED
            self._stats.failure_count = 0
            self._stats.success_count = 0
            self._stats.last_failure_time = None
            self._stats.last_state_change = time.time()
            self._half_open_calls = 0

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics for monitoring.

        Returns:
            Dictionary with current metrics including state, counts, and rates
        """
        total_requests = self._stats.total_successes + self._stats.total_failures
        success_rate = (
            (self._stats.total_successes / total_requests * 100)
            if total_requests > 0
            else 0.0
        )
        failure_rate = (
            (self._stats.total_failures / total_requests * 100)
            if total_requests > 0
            else 0.0
        )

        return {
            "name": self.name,
            "state": self._stats.state.value,
            "failure_count": self._stats.failure_count,
            "success_count": self._stats.success_count,
            "total_calls": self._stats.total_calls,
            "total_successes": self._stats.total_successes,
            "total_failures": self._stats.total_failures,
            "total_rejections": self._stats.total_rejections,
            "success_rate": round(success_rate, 2),
            "failure_rate": round(failure_rate, 2),
            "last_failure_time": self._stats.last_failure_time,
            "last_state_change": self._stats.last_state_change,
            "uptime_seconds": time.time() - self._stats.last_state_change,
        }
