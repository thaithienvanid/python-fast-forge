"""Domain-specific exceptions for business logic errors.

This module defines the exception hierarchy for domain errors, providing
consistent error handling across the application layer.
"""

from typing import Any


class DomainException(Exception):
    """Base exception for all domain-related errors.

    Provides a consistent interface for domain exceptions with error codes
    and optional contextual details.

    Attributes:
        code: Machine-readable error code
        message: Human-readable error message
        details: Optional additional error context (dict or list)
    """

    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | list[Any] | None = None) -> None:
        """Initialize domain exception.

        Args:
            message: Human-readable error description
            details: Optional additional context about the error
        """
        self.message = message
        self.details = details
        super().__init__(self.message)


class EntityNotFoundError(DomainException):
    """Raised when a requested entity does not exist.

    Use this exception when database queries return no results for
    requested entities (e.g., user not found, order not found).
    """

    code = "ENTITY_NOT_FOUND"


class ValidationError(DomainException):
    """Raised when input data fails business validation rules.

    Use this exception for domain-level validation failures, such as
    invalid business logic constraints or data format issues.
    """

    code = "VALIDATION_ERROR"


class BusinessRuleViolationError(DomainException):
    """Raised when an operation violates business rules.

    Use this exception when an operation is syntactically valid but
    violates business logic constraints (e.g., insufficient inventory,
    duplicate unique constraints, workflow violations).
    """

    code = "BUSINESS_RULE_VIOLATION"
