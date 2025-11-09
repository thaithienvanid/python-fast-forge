"""Tests for domain exceptions.

Test Organization:
- TestDomainException: Base exception behavior
- TestEntityNotFoundError: Entity not found exception
- TestValidationError: Validation error exception
- TestBusinessRuleViolationError: Business rule violation exception
- TestExceptionCodes: Exception code verification
- TestExceptionPropertyBased: Property-based tests with Hypothesis
- TestExceptionCatching: Exception raising and catching
- TestExceptionEdgeCases: Edge cases and boundary conditions
"""

import pytest
from hypothesis import given

from src.domain.exceptions import (
    BusinessRuleViolationError,
    DomainException,
    EntityNotFoundError,
    ValidationError,
)
from tests.strategies import error_details_strategy, error_message_strategy


# ============================================================================
# Base Exception Tests
# ============================================================================


class TestDomainException:
    """Test base DomainException behavior."""

    def test_creates_exception_with_message_only(self) -> None:
        """Test creating exception with message only.

        Arrange: Message string
        Act: Create DomainException with message
        Assert: Exception has correct message and no details
        """
        # Arrange
        message = "Something went wrong"

        # Act
        exception = DomainException(message)

        # Assert
        assert exception.message == message
        assert str(exception) == message
        assert exception.details is None

    def test_creates_exception_with_message_and_dict_details(self) -> None:
        """Test creating exception with message and dictionary details.

        Arrange: Message and details dictionary
        Act: Create DomainException with message and details
        Assert: Exception has correct message and details
        """
        # Arrange
        message = "Validation failed"
        details = {"field": "email", "reason": "Invalid format"}

        # Act
        exception = DomainException(message, details=details)

        # Assert
        assert exception.message == message
        assert exception.details == details
        assert exception.details["field"] == "email"
        assert exception.details["reason"] == "Invalid format"

    def test_creates_exception_with_message_and_list_details(self) -> None:
        """Test creating exception with message and list details.

        Arrange: Message and details list
        Act: Create DomainException with message and details
        Assert: Exception has correct message and details
        """
        # Arrange
        message = "Multiple validation errors"
        details = ["Email is required", "Username is too short"]

        # Act
        exception = DomainException(message, details=details)

        # Assert
        assert exception.message == message
        assert exception.details == details
        assert len(exception.details) == 2

    def test_exception_has_correct_code(self) -> None:
        """Test that DomainException has correct error code.

        Arrange: None
        Act: Create DomainException
        Assert: Exception has DOMAIN_ERROR code
        """
        # Arrange
        message = "Test error"

        # Act
        exception = DomainException(message)

        # Assert
        assert exception.code == "DOMAIN_ERROR"


# ============================================================================
# Specific Exception Tests
# ============================================================================


class TestEntityNotFoundError:
    """Test EntityNotFoundError behavior."""

    def test_creates_entity_not_found_error(self) -> None:
        """Test creating EntityNotFoundError.

        Arrange: Message for not found error
        Act: Create EntityNotFoundError
        Assert: Exception has correct message and inherits from DomainException
        """
        # Arrange
        message = "User not found"

        # Act
        exception = EntityNotFoundError(message)

        # Assert
        assert exception.message == message
        assert str(exception) == message
        assert isinstance(exception, DomainException)

    def test_entity_not_found_error_with_details(self) -> None:
        """Test EntityNotFoundError with details.

        Arrange: Message and details with entity information
        Act: Create EntityNotFoundError with details
        Assert: Exception has correct message and details
        """
        # Arrange
        message = "User not found"
        details = {"entity_type": "User", "entity_id": "123"}

        # Act
        exception = EntityNotFoundError(message, details=details)

        # Assert
        assert exception.message == message
        assert exception.details == details

    def test_entity_not_found_error_has_correct_code(self) -> None:
        """Test EntityNotFoundError has correct error code.

        Arrange: None
        Act: Create EntityNotFoundError
        Assert: Exception has ENTITY_NOT_FOUND code
        """
        # Arrange
        message = "Entity not found"

        # Act
        exception = EntityNotFoundError(message)

        # Assert
        assert exception.code == "ENTITY_NOT_FOUND"


class TestValidationError:
    """Test ValidationError behavior."""

    def test_creates_validation_error(self) -> None:
        """Test creating ValidationError.

        Arrange: Validation error message
        Act: Create ValidationError
        Assert: Exception has correct message and inherits from DomainException
        """
        # Arrange
        message = "Invalid email format"

        # Act
        exception = ValidationError(message)

        # Assert
        assert exception.message == message
        assert str(exception) == message
        assert isinstance(exception, DomainException)

    def test_validation_error_with_field_details(self) -> None:
        """Test ValidationError with field validation details.

        Arrange: Message and field-level validation details
        Act: Create ValidationError with details
        Assert: Exception has correct message and field details
        """
        # Arrange
        message = "Validation failed"
        details = {
            "field": "email",
            "value": "invalid-email",
            "constraint": "must be valid email address",
        }

        # Act
        exception = ValidationError(message, details=details)

        # Assert
        assert exception.message == message
        assert exception.details["field"] == "email"
        assert exception.details["constraint"] == "must be valid email address"

    def test_validation_error_has_correct_code(self) -> None:
        """Test ValidationError has correct error code.

        Arrange: None
        Act: Create ValidationError
        Assert: Exception has VALIDATION_ERROR code
        """
        # Arrange
        message = "Validation failed"

        # Act
        exception = ValidationError(message)

        # Assert
        assert exception.code == "VALIDATION_ERROR"


class TestBusinessRuleViolationError:
    """Test BusinessRuleViolationError behavior."""

    def test_creates_business_rule_violation_error(self) -> None:
        """Test creating BusinessRuleViolationError.

        Arrange: Business rule violation message
        Act: Create BusinessRuleViolationError
        Assert: Exception has correct message and inherits from DomainException
        """
        # Arrange
        message = "Cannot delete active user"

        # Act
        exception = BusinessRuleViolationError(message)

        # Assert
        assert exception.message == message
        assert str(exception) == message
        assert isinstance(exception, DomainException)

    def test_business_rule_violation_with_rule_details(self) -> None:
        """Test BusinessRuleViolationError with rule violation details.

        Arrange: Message and business rule details
        Act: Create BusinessRuleViolationError with details
        Assert: Exception has correct message and rule details
        """
        # Arrange
        message = "Cannot delete active user"
        details = {
            "rule": "active_user_protection",
            "user_id": "123",
            "is_active": True,
        }

        # Act
        exception = BusinessRuleViolationError(message, details=details)

        # Assert
        assert exception.message == message
        assert exception.details["rule"] == "active_user_protection"
        assert exception.details["is_active"] is True

    def test_business_rule_violation_has_correct_code(self) -> None:
        """Test BusinessRuleViolationError has correct error code.

        Arrange: None
        Act: Create BusinessRuleViolationError
        Assert: Exception has BUSINESS_RULE_VIOLATION code
        """
        # Arrange
        message = "Business rule violated"

        # Act
        exception = BusinessRuleViolationError(message)

        # Assert
        assert exception.code == "BUSINESS_RULE_VIOLATION"


# ============================================================================
# Exception Code Tests
# ============================================================================


class TestExceptionCodes:
    """Test exception error codes are unique and correct."""

    def test_all_exception_codes_are_unique(self) -> None:
        """Test that all exception codes are unique.

        Arrange: All exception classes
        Act: Get all exception codes
        Assert: All codes are unique
        """
        # Arrange
        exception_classes = [
            DomainException,
            EntityNotFoundError,
            ValidationError,
            BusinessRuleViolationError,
        ]

        # Act
        codes = [exc.code for exc in exception_classes]

        # Assert
        assert len(codes) == len(set(codes)), "Exception codes must be unique"

    def test_exception_codes_follow_naming_convention(self) -> None:
        """Test that exception codes follow UPPER_SNAKE_CASE convention.

        Arrange: All exception classes
        Act: Get all exception codes
        Assert: All codes are uppercase with underscores
        """
        # Arrange
        exception_classes = [
            DomainException,
            EntityNotFoundError,
            ValidationError,
            BusinessRuleViolationError,
        ]

        # Act & Assert
        for exc_class in exception_classes:
            code = exc_class.code
            assert code.isupper(), f"{exc_class.__name__}.code must be uppercase"
            assert " " not in code, f"{exc_class.__name__}.code must not contain spaces"


# ============================================================================
# Property-Based Tests
# ============================================================================


class TestExceptionPropertyBased:
    """Property-based tests using Hypothesis to find edge cases."""

    @given(message=error_message_strategy())
    def test_domain_exception_accepts_any_message(self, message: str) -> None:
        """Property: DomainException accepts any message string.

        This test runs 100+ times with different messages.

        Arrange: Random message from strategy
        Act: Create DomainException
        Assert: Exception stores message correctly
        """
        # Arrange & Act
        exception = DomainException(message)

        # Assert
        assert exception.message == message
        assert str(exception) == message

    @given(message=error_message_strategy(), details=error_details_strategy())
    def test_domain_exception_accepts_any_details(
        self, message: str, details: dict | list | None
    ) -> None:
        """Property: DomainException accepts dict, list, or None details.

        This test runs 100+ times with different detail types.

        Arrange: Random message and details from strategies
        Act: Create DomainException with details
        Assert: Exception stores details correctly
        """
        # Arrange & Act
        exception = DomainException(message, details=details)

        # Assert
        assert exception.message == message
        assert exception.details == details

    @given(message=error_message_strategy())
    def test_all_exception_types_accept_any_message(self, message: str) -> None:
        """Property: All exception types accept any message.

        This test runs 100+ times with different messages.

        Arrange: Random message and all exception classes
        Act: Create each exception type
        Assert: All exceptions store message correctly
        """
        # Arrange
        exception_classes = [
            DomainException,
            EntityNotFoundError,
            ValidationError,
            BusinessRuleViolationError,
        ]

        # Act & Assert
        for exc_class in exception_classes:
            exception = exc_class(message)
            assert exception.message == message
            assert str(exception) == message


# ============================================================================
# Exception Catching Tests
# ============================================================================


class TestExceptionCatching:
    """Test exception raising and catching behavior."""

    def test_can_raise_and_catch_domain_exception(self) -> None:
        """Test raising and catching DomainException.

        Arrange: Exception message
        Act: Raise DomainException
        Assert: Exception is caught with correct message
        """
        # Arrange
        message = "Domain error occurred"

        # Act & Assert
        with pytest.raises(DomainException) as exc_info:
            raise DomainException(message)

        assert exc_info.value.message == message
        assert str(exc_info.value) == message

    def test_can_raise_and_catch_entity_not_found_error(self) -> None:
        """Test raising and catching EntityNotFoundError.

        Arrange: Exception message
        Act: Raise EntityNotFoundError
        Assert: Exception is caught with correct message
        """
        # Arrange
        message = "Test entity not found"

        # Act & Assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            raise EntityNotFoundError(message)

        assert message in str(exc_info.value)

    def test_can_catch_specific_exception_as_base_exception(self) -> None:
        """Test catching specific exception as DomainException.

        Arrange: Specific exception (EntityNotFoundError)
        Act: Raise specific exception, catch as DomainException
        Assert: Exception is caught and message is correct
        """
        # Arrange
        message = "User not found"

        # Act & Assert
        with pytest.raises(DomainException) as exc_info:
            raise EntityNotFoundError(message)

        assert exc_info.value.message == message
        assert isinstance(exc_info.value, EntityNotFoundError)

    def test_exception_with_details_preserves_details_when_caught(self) -> None:
        """Test exception details are preserved when caught.

        Arrange: Exception with details
        Act: Raise exception with details
        Assert: Caught exception has same details
        """
        # Arrange
        message = "Validation failed"
        details = {"field": "email", "error": "invalid format"}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError(message, details=details)

        assert exc_info.value.details == details


# ============================================================================
# Exception Inheritance Tests
# ============================================================================


class TestExceptionInheritance:
    """Test exception inheritance chain."""

    def test_entity_not_found_error_inherits_from_domain_exception(self) -> None:
        """Test EntityNotFoundError inherits from DomainException.

        Arrange: EntityNotFoundError instance
        Act: Check isinstance
        Assert: Instance is both EntityNotFoundError and DomainException
        """
        # Arrange
        exception = EntityNotFoundError("test")

        # Act & Assert
        assert isinstance(exception, EntityNotFoundError)
        assert isinstance(exception, DomainException)
        assert isinstance(exception, Exception)

    def test_validation_error_inherits_from_domain_exception(self) -> None:
        """Test ValidationError inherits from DomainException.

        Arrange: ValidationError instance
        Act: Check isinstance
        Assert: Instance is both ValidationError and DomainException
        """
        # Arrange
        exception = ValidationError("test")

        # Act & Assert
        assert isinstance(exception, ValidationError)
        assert isinstance(exception, DomainException)
        assert isinstance(exception, Exception)

    def test_business_rule_violation_inherits_from_domain_exception(self) -> None:
        """Test BusinessRuleViolationError inherits from DomainException.

        Arrange: BusinessRuleViolationError instance
        Act: Check isinstance
        Assert: Instance is both BusinessRuleViolationError and DomainException
        """
        # Arrange
        exception = BusinessRuleViolationError("test")

        # Act & Assert
        assert isinstance(exception, BusinessRuleViolationError)
        assert isinstance(exception, DomainException)
        assert isinstance(exception, Exception)


# ============================================================================
# Edge Cases
# ============================================================================


class TestExceptionEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exception_with_empty_message(self) -> None:
        """Test creating exception with empty message.

        Arrange: Empty string message
        Act: Create DomainException
        Assert: Exception accepts empty message
        """
        # Arrange
        message = ""

        # Act
        exception = DomainException(message)

        # Assert
        assert exception.message == ""
        assert str(exception) == ""

    def test_exception_with_very_long_message(self) -> None:
        """Test creating exception with very long message.

        Arrange: Very long message (1000+ characters)
        Act: Create DomainException
        Assert: Exception stores full message
        """
        # Arrange
        message = "Error: " + "x" * 1000

        # Act
        exception = DomainException(message)

        # Assert
        assert exception.message == message
        assert len(exception.message) > 1000

    def test_exception_with_none_details_explicitly(self) -> None:
        """Test creating exception with explicit None details.

        Arrange: Message and None details
        Act: Create DomainException with details=None
        Assert: Exception has None details
        """
        # Arrange
        message = "Test error"

        # Act
        exception = DomainException(message, details=None)

        # Assert
        assert exception.details is None

    def test_exception_with_empty_dict_details(self) -> None:
        """Test creating exception with empty dictionary details.

        Arrange: Message and empty dict
        Act: Create DomainException with empty dict
        Assert: Exception has empty dict details
        """
        # Arrange
        message = "Test error"
        details = {}

        # Act
        exception = DomainException(message, details=details)

        # Assert
        assert exception.details == {}
        assert len(exception.details) == 0

    def test_exception_with_empty_list_details(self) -> None:
        """Test creating exception with empty list details.

        Arrange: Message and empty list
        Act: Create DomainException with empty list
        Assert: Exception has empty list details
        """
        # Arrange
        message = "Test error"
        details = []

        # Act
        exception = DomainException(message, details=details)

        # Assert
        assert exception.details == []
        assert len(exception.details) == 0

    def test_exception_with_nested_dict_details(self) -> None:
        """Test creating exception with nested dictionary details.

        Arrange: Message and nested dict details
        Act: Create DomainException with nested dict
        Assert: Exception preserves nested structure
        """
        # Arrange
        message = "Complex validation error"
        details = {
            "errors": {
                "field1": {"error": "required", "value": None},
                "field2": {"error": "invalid", "value": "bad"},
            }
        }

        # Act
        exception = DomainException(message, details=details)

        # Assert
        assert exception.details["errors"]["field1"]["error"] == "required"
        assert exception.details["errors"]["field2"]["value"] == "bad"

    def test_exception_with_unicode_message(self) -> None:
        """Test creating exception with unicode characters in message.

        Arrange: Message with unicode characters
        Act: Create DomainException
        Assert: Exception handles unicode correctly
        """
        # Arrange
        message = "Error: 用户未找到 (User not found) 🚫"

        # Act
        exception = DomainException(message)

        # Assert
        assert exception.message == message
        assert "用户未找到" in str(exception)
        assert "🚫" in str(exception)
