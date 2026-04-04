"""Decorators for cross-cutting concerns in use cases.

This module provides reusable decorators that handle common patterns across
use cases, following the DRY (Don't Repeat Yourself) principle.

Design Patterns:
    - Decorator Pattern: Add behavior without modifying core logic
    - Aspect-Oriented Programming: Cross-cutting concerns (error handling, logging)

SOLID Principles:
    - Single Responsibility: Each decorator has one concern
    - Open/Closed: Add new decorators without modifying use cases
    - Dependency Inversion: Decorators depend on abstractions

Benefits:
    - Eliminates code duplication
    - Consistent error handling across all use cases
    - Easier to maintain and test
    - Clear separation of concerns
"""

import functools
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, cast

from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import ValidationError
from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)

# Type variables for generic decorator
P = ParamSpec("P")
T = TypeVar("T")


def handle_integrity_errors[**P, T](func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Decorator to handle database integrity constraint violations.

    Converts SQLAlchemy IntegrityError into domain ValidationError with
    user-friendly messages. Eliminates duplicate error handling code across
    use cases.

    Args:
        func: Use case execute method to wrap

    Returns:
        Wrapped function with integrity error handling

    Raises:
        ValidationError: When database constraint is violated

    Design Pattern:
        Decorator pattern for cross-cutting concern (error handling)

    Example:
        ```python
        class CreateUserUseCase:
            @handle_integrity_errors
            async def execute(self, command: CreateUserCommand) -> User:
                # Clean business logic - no error handling needed
                user = User(email=command.email, username=command.username)
                return await self._repository.create(user)


        # Usage:
        try:
            user = await create_user_use_case.execute(command)
        except ValidationError as e:
            # Gets user-friendly message like:
            # "User with email test@example.com already exists"
            print(e.message)
        ```

    Constraint Violations Handled:
        - Email uniqueness (ix_users_email)
        - Username uniqueness (ix_users_username)
        - Other unique constraints (generic message)

    Benefits:
        - Eliminates 20+ lines of duplicate code per use case
        - Consistent error messages across application
        - Single place to update constraint violation logic
        - Testable in isolation
    """

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await func(*args, **kwargs)

        except IntegrityError as e:
            # Extract constraint violation details from database error
            error_msg = str(e.orig).lower() if hasattr(e, "orig") else str(e).lower()

            # Parse error message to identify which constraint was violated
            if "email" in error_msg or "ix_users_email" in error_msg:
                # Extract email from kwargs/args if available
                email = _extract_field_value(args, kwargs, "email") or "this email"
                raise ValidationError(f"User with email {email} already exists") from e

            if "username" in error_msg or "ix_users_username" in error_msg:
                # Extract username from kwargs/args if available
                username = _extract_field_value(args, kwargs, "username") or "this username"
                raise ValidationError(f"User with username {username} already exists") from e

            # Generic constraint violation
            logger.warning(
                "integrity_constraint_violation",
                error=error_msg,
                message="Database constraint violated - unrecognized constraint",
            )
            raise ValidationError("Operation failed due to data constraint violation") from e

    return wrapper


def log_use_case_execution(
    use_case_name: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to log use case execution for observability.

    Logs use case start, success, and failure for debugging and monitoring.

    Args:
        use_case_name: Optional custom name (defaults to function name)

    Returns:
        Decorator function

    Design Pattern:
        Decorator pattern for cross-cutting concern (logging)

    Example:
        ```python
        class CreateUserUseCase:
            @log_use_case_execution("CreateUser")
            async def execute(self, command: CreateUserCommand) -> User:
                user = User(...)
                return await self._repository.create(user)


        # Logs:
        # INFO: use_case_started use_case="CreateUser"
        # INFO: use_case_completed use_case="CreateUser" duration=0.234s
        ```

    Benefits:
        - Automatic execution tracking
        - Performance monitoring (duration)
        - Error tracking
        - No manual logging in use cases
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import time  # noqa: PLC0415

            name = use_case_name or func.__name__

            logger.info("use_case_started", use_case=name)
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(
                    "use_case_completed",
                    use_case=name,
                    duration=f"{duration:.3f}s",
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                logger.error(
                    "use_case_failed",
                    use_case=name,
                    duration=f"{duration:.3f}s",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        return wrapper

    return decorator


def validate_tenant_isolation[**P, T](func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Decorator to enforce tenant isolation in multi-tenant use cases.

    Verifies that operations only access data belonging to the correct tenant.
    Prevents cross-tenant data leakage in multi-tenant applications.

    Args:
        func: Use case execute method to wrap

    Returns:
        Wrapped function with tenant validation

    Raises:
        EntityNotFoundError: When entity doesn't belong to tenant

    Design Pattern:
        Decorator pattern for security cross-cutting concern

    Example:
        ```python
        class GetUserUseCase:
            @validate_tenant_isolation
            async def execute(self, user_id: UUID, tenant_id: UUID | None = None) -> User:
                user = await self._repository.get_by_id(user_id)
                # Tenant validation happens automatically in decorator
                return user
        ```

    Security Benefits:
        - Prevents tenant data leakage
        - Consistent security enforcement
        - Single point of tenant validation logic
    """
    from uuid import UUID  # noqa: PLC0415

    from src.domain.exceptions import EntityNotFoundError  # noqa: PLC0415

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Execute the use case
        result = await func(*args, **kwargs)

        # Extract tenant_id from kwargs or args (if provided)
        expected_tenant_id: UUID | None = cast("UUID | None", kwargs.get("tenant_id"))
        if expected_tenant_id is None:
            # Try to find tenant_id in command/query objects in args
            for arg in args:
                if hasattr(arg, "tenant_id"):
                    expected_tenant_id = arg.tenant_id
                    break

        # If no tenant_id provided, skip validation (no multi-tenancy)
        if expected_tenant_id is None:
            return result

        # Validate result has tenant_id (single entity or list of entities)
        if isinstance(result, list):
            # Validate all entities in list
            for entity in result:
                if hasattr(entity, "tenant_id"):
                    entity_tenant_id = entity.tenant_id
                    if entity_tenant_id is not None and entity_tenant_id != expected_tenant_id:
                        # Security: Return 404 instead of 403 to prevent tenant enumeration
                        logger.warning(
                            "tenant_isolation_violation",
                            expected_tenant=str(expected_tenant_id),
                            entity_tenant=str(entity_tenant_id),
                            entity_type=type(entity).__name__,
                            message="Cross-tenant access attempt detected",
                        )
                        raise EntityNotFoundError(
                            "Entity not found",
                            details={"entity_type": type(entity).__name__},
                        )
        # Validate single entity
        elif hasattr(result, "tenant_id"):
            entity_tenant_id = result.tenant_id
            if entity_tenant_id is not None and entity_tenant_id != expected_tenant_id:
                # Security: Return 404 instead of 403 to prevent tenant enumeration
                logger.warning(
                    "tenant_isolation_violation",
                    expected_tenant=str(expected_tenant_id),
                    entity_tenant=str(entity_tenant_id),
                    entity_type=type(result).__name__,
                    message="Cross-tenant access attempt detected",
                )
                raise EntityNotFoundError(
                    "Entity not found",
                    details={"entity_type": type(result).__name__},
                )

        return result

    return wrapper


def _extract_field_value(
    args: tuple[Any, ...], kwargs: dict[str, Any], field_name: str
) -> str | None:
    """Extract field value from function arguments.

    Helper function to extract specific field values from function arguments
    for better error messages in decorators.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        field_name: Name of field to extract

    Returns:
        Field value if found, None otherwise

    Example:
        ```python
        # Function call:
        await create_user(email="test@example.com", username="testuser")

        # Extract:
        email = _extract_field_value(args, kwargs, "email")
        # Returns: "test@example.com"
        ```
    """
    # Check kwargs first
    if field_name in kwargs:
        return str(kwargs[field_name])

    # Check args - try to find command object with attribute
    for arg in args:
        if hasattr(arg, field_name):
            value = getattr(arg, field_name)
            return str(value) if value is not None else None

    return None


__all__ = [
    "handle_integrity_errors",
    "log_use_case_execution",
    "validate_tenant_isolation",
]
