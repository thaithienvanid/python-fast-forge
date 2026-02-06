"""Result type for explicit error handling without exceptions.

This module provides a Result type inspired by Rust's Result<T, E> and
functional programming patterns. It makes error handling explicit and
composable, avoiding silent failures and hidden None returns.

Benefits:
- Explicit error handling (no silent failures)
- Type-safe error propagation
- Composable with map/bind operations
- Better than None returns (includes error context)
- Better than exceptions (explicit in type signature)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")  # Success type
E = TypeVar("E")  # Error type
U = TypeVar("U")  # Mapped success type


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Success result containing a value.

    Example:
        >>> result = Ok(42)
        >>> result.is_ok()
        True
        >>> result.unwrap()
        42
    """

    value: T

    def is_ok(self) -> bool:
        """Check if result is successful."""
        return True

    def is_err(self) -> bool:
        """Check if result is an error."""
        return False

    def unwrap(self) -> T:
        """Get the success value.

        Returns:
            The wrapped success value

        Example:
            >>> Ok(42).unwrap()
            42
        """
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the success value or return default.

        Args:
            default: Value to return if this is an error

        Returns:
            The wrapped value (default is ignored for Ok)

        Example:
            >>> Ok(42).unwrap_or(0)
            42
        """
        return self.value

    def unwrap_or_else(self, f: Callable[[E], T]) -> T:
        """Get the success value or compute from error.

        Args:
            f: Function to compute default from error (not called for Ok)

        Returns:
            The wrapped value

        Example:
            >>> Ok(42).unwrap_or_else(lambda e: 0)
            42
        """
        return self.value

    def map(self, f: Callable[[T], U]) -> Result[U, E]:
        """Transform the success value if Ok.

        Args:
            f: Function to transform the value

        Returns:
            Ok with transformed value

        Example:
            >>> Ok(42).map(lambda x: x * 2)
            Ok(value=84)
        """
        return Ok(f(self.value))

    def map_err(self, f: Callable[[E], E]) -> Result[T, E]:
        """Transform the error value if Err (no-op for Ok).

        Args:
            f: Function to transform error (not called for Ok)

        Returns:
            Same Ok instance

        Example:
            >>> Ok(42).map_err(lambda e: str(e))
            Ok(value=42)
        """
        return self

    def and_then(self, f: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Chain operations that return Results (monadic bind).

        Args:
            f: Function that takes success value and returns new Result

        Returns:
            Result from calling f with the value

        Example:
            >>> Ok(42).and_then(lambda x: Ok(x * 2))
            Ok(value=84)
            >>> Ok(42).and_then(lambda x: Err("failed"))
            Err(error='failed')
        """
        return f(self.value)

    def __repr__(self) -> str:
        """String representation."""
        return f"Ok(value={self.value!r})"


@dataclass(frozen=True)
class Err(Generic[E]):
    """Error result containing an error value.

    Example:
        >>> result = Err("something went wrong")
        >>> result.is_err()
        True
        >>> result.unwrap_or(0)
        0
    """

    error: E

    def is_ok(self) -> bool:
        """Check if result is successful."""
        return False

    def is_err(self) -> bool:
        """Check if result is an error."""
        return True

    def unwrap(self) -> T:
        """Get the success value (raises for Err).

        Raises:
            ValueError: Always, with the error message

        Example:
            >>> Err("failed").unwrap()
            Traceback (most recent call last):
            ValueError: Called unwrap on Err: failed
        """
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default: T) -> T:
        """Get the success value or return default.

        Args:
            default: Value to return for error

        Returns:
            The default value

        Example:
            >>> Err("failed").unwrap_or(42)
            42
        """
        return default

    def unwrap_or_else(self, f: Callable[[E], T]) -> T:
        """Get the success value or compute from error.

        Args:
            f: Function to compute default from error

        Returns:
            Result of calling f with the error

        Example:
            >>> Err("failed").unwrap_or_else(lambda e: len(e))
            6
        """
        return f(self.error)

    def map(self, f: Callable[[T], U]) -> Result[U, E]:
        """Transform the success value if Ok (no-op for Err).

        Args:
            f: Function to transform value (not called for Err)

        Returns:
            Same Err instance

        Example:
            >>> Err("failed").map(lambda x: x * 2)
            Err(error='failed')
        """
        return self  # type: ignore

    def map_err(self, f: Callable[[E], E]) -> Result[T, E]:
        """Transform the error value if Err.

        Args:
            f: Function to transform error

        Returns:
            Err with transformed error

        Example:
            >>> Err("failed").map_err(lambda e: e.upper())
            Err(error='FAILED')
        """
        return Err(f(self.error))

    def and_then(self, f: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Chain operations that return Results (no-op for Err).

        Args:
            f: Function that would transform value (not called for Err)

        Returns:
            Same Err instance

        Example:
            >>> Err("failed").and_then(lambda x: Ok(x * 2))
            Err(error='failed')
        """
        return self  # type: ignore

    def __repr__(self) -> str:
        """String representation."""
        return f"Err(error={self.error!r})"


# Type alias for Result
Result = Ok[T] | Err[E]


# Convenience functions for creating Results
def ok(value: T) -> Ok[T]:
    """Create a success Result.

    Args:
        value: Success value to wrap

    Returns:
        Ok instance containing the value

    Example:
        >>> result = ok(42)
        >>> result.unwrap()
        42
    """
    return Ok(value)


def err(error: E) -> Err[E]:
    """Create an error Result.

    Args:
        error: Error value to wrap

    Returns:
        Err instance containing the error

    Example:
        >>> result = err("something failed")
        >>> result.is_err()
        True
    """
    return Err(error)


# Example usage and patterns
if __name__ == "__main__":
    # Example 1: Basic usage
    def divide(a: int, b: int) -> Result[float, str]:
        """Divide two numbers, returning Result."""
        if b == 0:
            return err("Division by zero")
        return ok(a / b)

    result = divide(10, 2)
    if result.is_ok():
        print(f"Success: {result.unwrap()}")  # Success: 5.0
    else:
        print(f"Error: {result.error}")

    # Example 2: Using unwrap_or
    value = divide(10, 0).unwrap_or(0.0)
    print(f"Value with default: {value}")  # Value with default: 0.0

    # Example 3: Chaining with map
    result = divide(10, 2).map(lambda x: x * 2)
    print(f"Doubled: {result.unwrap()}")  # Doubled: 10.0

    # Example 4: Chaining with and_then
    def safe_sqrt(x: float) -> Result[float, str]:
        """Square root that returns Result."""
        if x < 0:
            return err("Cannot sqrt negative number")
        return ok(x**0.5)

    result = divide(16, 2).and_then(safe_sqrt)
    print(f"Result: {result.unwrap()}")  # Result: 2.828...

    # Example 5: Error propagation
    result = divide(16, 0).and_then(safe_sqrt)
    print(f"Propagated error: {result.error}")  # Propagated error: Division by zero
