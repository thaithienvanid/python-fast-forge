"""Unit tests for Result type.

Tests the Result monad implementation for explicit error handling.
"""

import pytest

from src.utils.result import Err, Ok, Result, err, ok


class TestOkResult:
    """Test suite for Ok (success) results."""

    def test_ok_is_ok(self) -> None:
        """Test that Ok.is_ok() returns True."""
        result: Result[int, str] = Ok(42)
        assert result.is_ok() is True
        assert result.is_err() is False

    def test_ok_unwrap(self) -> None:
        """Test that Ok.unwrap() returns the value."""
        result: Result[int, str] = Ok(42)
        assert result.unwrap() == 42

    def test_ok_unwrap_or(self) -> None:
        """Test that Ok.unwrap_or() returns the value (ignores default)."""
        result: Result[int, str] = Ok(42)
        assert result.unwrap_or(0) == 42

    def test_ok_unwrap_or_else(self) -> None:
        """Test that Ok.unwrap_or_else() returns the value (doesn't call function)."""
        result: Result[int, str] = Ok(42)
        assert result.unwrap_or_else(lambda e: 0) == 42

    def test_ok_map(self) -> None:
        """Test that Ok.map() transforms the value."""
        result: Result[int, str] = Ok(42)
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_ok()
        assert mapped.unwrap() == 84

    def test_ok_map_err(self) -> None:
        """Test that Ok.map_err() is no-op for Ok."""
        result: Result[int, str] = Ok(42)
        mapped = result.map_err(lambda e: e.upper())

        assert mapped.is_ok()
        assert mapped.unwrap() == 42

    def test_ok_and_then_ok(self) -> None:
        """Test that Ok.and_then() chains successful operations."""
        result: Result[int, str] = Ok(42)
        chained = result.and_then(lambda x: Ok(x * 2))

        assert chained.is_ok()
        assert chained.unwrap() == 84

    def test_ok_and_then_err(self) -> None:
        """Test that Ok.and_then() can produce an error."""
        result: Result[int, str] = Ok(42)
        chained = result.and_then(lambda x: Err("failed"))

        assert chained.is_err()
        assert chained.error == "failed"  # type: ignore

    def test_ok_convenience_function(self) -> None:
        """Test that ok() convenience function creates Ok."""
        result = ok(42)
        assert isinstance(result, Ok)
        assert result.unwrap() == 42


class TestErrResult:
    """Test suite for Err (error) results."""

    def test_err_is_err(self) -> None:
        """Test that Err.is_err() returns True."""
        result: Result[int, str] = Err("failed")
        assert result.is_ok() is False
        assert result.is_err() is True

    def test_err_unwrap_raises(self) -> None:
        """Test that Err.unwrap() raises ValueError."""
        result: Result[int, str] = Err("failed")

        with pytest.raises(ValueError, match="Called unwrap on Err"):
            result.unwrap()

    def test_err_unwrap_or(self) -> None:
        """Test that Err.unwrap_or() returns the default."""
        result: Result[int, str] = Err("failed")
        assert result.unwrap_or(42) == 42

    def test_err_unwrap_or_else(self) -> None:
        """Test that Err.unwrap_or_else() calls function with error."""
        result: Result[int, str] = Err("failed")
        assert result.unwrap_or_else(lambda e: len(e)) == 6

    def test_err_map(self) -> None:
        """Test that Err.map() is no-op for Err."""
        result: Result[int, str] = Err("failed")
        mapped = result.map(lambda x: x * 2)

        assert mapped.is_err()
        assert mapped.error == "failed"  # type: ignore

    def test_err_map_err(self) -> None:
        """Test that Err.map_err() transforms the error."""
        result: Result[int, str] = Err("failed")
        mapped = result.map_err(lambda e: e.upper())

        assert mapped.is_err()
        assert mapped.error == "FAILED"  # type: ignore

    def test_err_and_then(self) -> None:
        """Test that Err.and_then() is no-op for Err."""
        result: Result[int, str] = Err("failed")
        chained = result.and_then(lambda x: Ok(x * 2))

        assert chained.is_err()
        assert chained.error == "failed"  # type: ignore

    def test_err_convenience_function(self) -> None:
        """Test that err() convenience function creates Err."""
        result = err("failed")
        assert isinstance(result, Err)
        assert result.error == "failed"


class TestResultChaining:
    """Test suite for chaining Result operations."""

    def test_chain_success(self) -> None:
        """Test chaining successful operations."""

        def divide(a: int, b: int) -> Result[float, str]:
            if b == 0:
                return err("Division by zero")
            return ok(a / b)

        def sqrt(x: float) -> Result[float, str]:
            if x < 0:
                return err("Cannot sqrt negative")
            return ok(x**0.5)

        # 16 / 4 = 4, sqrt(4) = 2
        result = divide(16, 4).and_then(sqrt)

        assert result.is_ok()
        assert result.unwrap() == 2.0

    def test_chain_early_failure(self) -> None:
        """Test that early failure short-circuits chain."""

        def divide(a: int, b: int) -> Result[float, str]:
            if b == 0:
                return err("Division by zero")
            return ok(a / b)

        def sqrt(x: float) -> Result[float, str]:
            if x < 0:
                return err("Cannot sqrt negative")
            return ok(x**0.5)

        # Division fails, sqrt never called
        result = divide(16, 0).and_then(sqrt)

        assert result.is_err()
        assert result.error == "Division by zero"  # type: ignore

    def test_chain_late_failure(self) -> None:
        """Test that later operation can fail."""

        def divide(a: int, b: int) -> Result[float, str]:
            if b == 0:
                return err("Division by zero")
            return ok(a / b)

        def sqrt(x: float) -> Result[float, str]:
            if x < 0:
                return err("Cannot sqrt negative")
            return ok(x**0.5)

        # -16 / 4 = -4, sqrt(-4) fails
        result = divide(-16, 4).and_then(sqrt)

        assert result.is_err()
        assert result.error == "Cannot sqrt negative"  # type: ignore

    def test_map_chain(self) -> None:
        """Test chaining with map operations."""
        result = ok(5).map(lambda x: x * 2).map(lambda x: x + 3).map(lambda x: x / 2)

        assert result.is_ok()
        assert result.unwrap() == 6.5  # (5 * 2 + 3) / 2 = 6.5


class TestResultPatternMatching:
    """Test suite for pattern matching with Results."""

    def test_pattern_match_ok(self) -> None:
        """Test pattern matching on Ok result."""
        result: Result[int, str] = ok(42)

        match result:
            case Ok(value):
                assert value == 42
            case Err(error):
                pytest.fail("Should not match Err")

    def test_pattern_match_err(self) -> None:
        """Test pattern matching on Err result."""
        result: Result[int, str] = err("failed")

        match result:
            case Ok(value):
                pytest.fail("Should not match Ok")
            case Err(error):
                assert error == "failed"

    def test_conditional_handling(self) -> None:
        """Test conditional handling of Results."""

        def process(result: Result[int, str]) -> int:
            if result.is_ok():
                return result.unwrap() * 2
            return 0

        assert process(ok(21)) == 42
        assert process(err("failed")) == 0


class TestResultWithComplexTypes:
    """Test suite for Results with complex types."""

    def test_result_with_dict(self) -> None:
        """Test Result containing dictionary."""
        result: Result[dict[str, int], str] = ok({"a": 1, "b": 2})

        assert result.is_ok()
        assert result.unwrap() == {"a": 1, "b": 2}

    def test_result_with_list(self) -> None:
        """Test Result containing list."""
        result: Result[list[int], str] = ok([1, 2, 3])

        assert result.is_ok()
        assert result.unwrap() == [1, 2, 3]

    def test_result_with_none(self) -> None:
        """Test Result containing None."""
        result: Result[None, str] = ok(None)

        assert result.is_ok()
        assert result.unwrap() is None

    def test_result_with_custom_error(self) -> None:
        """Test Result with custom error type."""
        from dataclasses import dataclass

        @dataclass
        class CustomError:
            code: int
            message: str

        result: Result[int, CustomError] = err(CustomError(404, "Not found"))

        assert result.is_err()
        assert result.error.code == 404  # type: ignore
        assert result.error.message == "Not found"  # type: ignore


class TestResultRepresentation:
    """Test suite for Result string representations."""

    def test_ok_repr(self) -> None:
        """Test Ok string representation."""
        result = ok(42)
        assert repr(result) == "Ok(value=42)"

    def test_err_repr(self) -> None:
        """Test Err string representation."""
        result = err("failed")
        assert repr(result) == "Err(error='failed')"

    def test_ok_str_conversion(self) -> None:
        """Test Ok string conversion."""
        result = ok("hello")
        assert str(result) == "Ok(value='hello')"

    def test_err_str_conversion(self) -> None:
        """Test Err string conversion."""
        result = err("something went wrong")
        assert str(result) == "Err(error='something went wrong')"
