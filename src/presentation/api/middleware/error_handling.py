"""Global exception handling middleware for FastAPI application.

This module provides centralized error handling, converting various exception
types into consistent JSON responses following the ErrorResponse schema. It
ensures proper HTTP status codes and error formatting across the application.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.domain.exceptions import (
    BusinessRuleViolationError,
    DomainException,
    EntityNotFoundError,
    ValidationError,
)
from src.infrastructure.logging.config import get_logger
from src.presentation.schemas.error import ErrorDetail, ErrorResponse


logger = get_logger(__name__)

# Type alias for cleaner function signatures
ExceptionHandler = Callable[[Request, Any], Awaitable[JSONResponse]]


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """Handle domain-layer exceptions with appropriate HTTP status codes.

    Maps domain exceptions to REST API responses:
    - EntityNotFoundError → 404 Not Found
    - ValidationError → 422 Unprocessable Entity
    - BusinessRuleViolationError → 409 Conflict
    - Generic DomainException → 400 Bad Request

    Args:
        request: Incoming HTTP request
        exc: Domain exception instance

    Returns:
        JSON response with error details
    """
    logger.warning(
        "domain_exception",
        exception_type=type(exc).__name__,
        code=exc.code,
        message=exc.message,
        path=request.url.path,
    )

    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, EntityNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    elif isinstance(exc, BusinessRuleViolationError):
        status_code = status.HTTP_409_CONFLICT

    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors from request parsing.

    Args:
        request: Incoming HTTP request
        exc: Request validation error with detailed error information

    Returns:
        JSON response with validation error details (422 status)
    """
    logger.warning(
        "validation_error",
        errors=exc.errors(),
        path=request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=exc.errors(),
        )
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_response.model_dump(),
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Handle database integrity constraint violations.

    Detects and handles constraint violations such as:
    - Unique constraint violations (duplicate records)
    - Foreign key constraint violations
    - Check constraint violations

    Args:
        request: Incoming HTTP request
        exc: SQLAlchemy integrity error

    Returns:
        JSON response with error details (409 status)
    """
    logger.error(
        "database_integrity_error",
        error=str(exc.orig),
        path=request.url.path,
    )

    error_msg = str(exc.orig).lower()
    details = None
    message = "Database constraint violation"

    if "duplicate" in error_msg or "unique" in error_msg:
        message = "Resource already exists"
        details = "A record with this value already exists"

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTEGRITY_ERROR",
            message=message,
            details=details,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_response.model_dump(),
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle generic SQLAlchemy database errors.

    Catches database errors that aren't integrity violations (timeouts,
    connection errors, etc.) and returns a generic error response to
    avoid leaking implementation details.

    Args:
        request: Incoming HTTP request
        exc: SQLAlchemy error

    Returns:
        JSON response with generic error message (500 status)
    """
    logger.error(
        "database_error",
        error=str(exc),
        path=request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="DATABASE_ERROR",
            message="An error occurred while processing your request",
            details=None,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions as last resort.

    Catches all unhandled exceptions to prevent raw error responses
    from reaching clients. Logs full exception details for debugging
    while returning a safe generic message.

    Args:
        request: Incoming HTTP request
        exc: Unhandled exception

    Returns:
        JSON response with generic error message (500 status)
    """
    logger.exception(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        error=str(exc),
        path=request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            details=None,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI application.

    Configures the application to handle various exception types with
    appropriate responses and logging.

    Args:
        app: FastAPI application instance
    """
    # Domain exceptions
    domain_handler: ExceptionHandler = domain_exception_handler
    app.add_exception_handler(DomainException, domain_handler)
    app.add_exception_handler(EntityNotFoundError, domain_handler)
    app.add_exception_handler(ValidationError, domain_handler)
    app.add_exception_handler(BusinessRuleViolationError, domain_handler)

    # Validation exceptions
    validation_handler: ExceptionHandler = validation_exception_handler
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(PydanticValidationError, validation_handler)

    # Database exceptions
    integrity_handler: ExceptionHandler = integrity_error_handler
    sqlalchemy_handler: ExceptionHandler = sqlalchemy_error_handler
    app.add_exception_handler(IntegrityError, integrity_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_handler)

    # Generic exception handler (catch-all)
    generic_handler: ExceptionHandler = generic_exception_handler
    app.add_exception_handler(Exception, generic_handler)
