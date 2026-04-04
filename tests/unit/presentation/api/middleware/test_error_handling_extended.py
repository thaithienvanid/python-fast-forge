"""Extended unit tests for error_handling middleware.

Covers missing lines in src/presentation/api/middleware/error_handling.py:
- Lines 49-73: domain_exception_handler (EntityNotFoundError, ValidationError,
               BusinessRuleViolationError, generic DomainException)
- Lines 91-105: validation_exception_handler (RequestValidationError)
- Lines 126-148: integrity_error_handler (unique/duplicate vs generic)
- Lines 168-182: sqlalchemy_error_handler
- Lines 202-217: generic_exception_handler
- Lines 233-252: setup_exception_handlers (registration)

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- Mock Request objects
- pytest.mark.parametrize for status code variations
- Verify correct HTTP status codes and error codes
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.domain.exceptions import (
    BusinessRuleViolationError,
    DomainException,
    EntityNotFoundError,
    ValidationError,
)
from src.presentation.api.middleware.error_handling import (
    domain_exception_handler,
    generic_exception_handler,
    integrity_error_handler,
    setup_exception_handlers,
    sqlalchemy_error_handler,
    validation_exception_handler,
)


# ============================================================================
# Shared Fixtures
# ============================================================================


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    request = MagicMock()
    request.url.path = "/api/v1/users"
    return request


# ============================================================================
# domain_exception_handler Tests
# ============================================================================


class TestDomainExceptionHandler:
    """Tests for domain_exception_handler covering lines 49-73."""

    async def test_returns_404_for_entity_not_found(self, mock_request):
        """Test returns 404 Not Found for EntityNotFoundError.

        Arrange: EntityNotFoundError raised
        Act: Call domain_exception_handler
        Assert: Response status 404, error code ENTITY_NOT_FOUND (lines 58-59)
        """
        # Arrange
        exc = EntityNotFoundError("User not found")

        # Act
        response = await domain_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        body = response.body
        import json

        data = json.loads(body)
        assert data["error"]["code"] == "ENTITY_NOT_FOUND"
        assert "User not found" in data["error"]["message"]

    async def test_returns_422_for_validation_error(self, mock_request):
        """Test returns 422 Unprocessable Entity for ValidationError.

        Arrange: ValidationError raised
        Act: Call domain_exception_handler
        Assert: Response status 422, error code VALIDATION_ERROR (lines 60-61)
        """
        # Arrange
        exc = ValidationError("Email is invalid")

        # Act
        response = await domain_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        import json

        data = json.loads(response.body)
        assert data["error"]["code"] == "VALIDATION_ERROR"

    async def test_returns_409_for_business_rule_violation(self, mock_request):
        """Test returns 409 Conflict for BusinessRuleViolationError.

        Arrange: BusinessRuleViolationError raised
        Act: Call domain_exception_handler
        Assert: Response status 409, error code BUSINESS_RULE_VIOLATION (lines 62-63)
        """
        # Arrange
        exc = BusinessRuleViolationError("Cannot exceed limit")

        # Act
        response = await domain_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        import json

        data = json.loads(response.body)
        assert data["error"]["code"] == "BUSINESS_RULE_VIOLATION"

    async def test_returns_400_for_generic_domain_exception(self, mock_request):
        """Test returns 400 Bad Request for generic DomainException.

        Arrange: Generic DomainException (not a subclass)
        Act: Call domain_exception_handler
        Assert: Response status 400, error code DOMAIN_ERROR (lines 57, 65-75)
        """
        # Arrange
        exc = DomainException("Something went wrong")

        # Act
        response = await domain_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        import json

        data = json.loads(response.body)
        assert data["error"]["code"] == "DOMAIN_ERROR"

    async def test_includes_error_details_in_response(self, mock_request):
        """Test includes error details in the response body.

        Arrange: Exception with details
        Act: Call domain_exception_handler
        Assert: Response includes details field (lines 65-70)
        """
        # Arrange
        exc = EntityNotFoundError("User not found", details={"user_id": "123"})

        # Act
        response = await domain_exception_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["details"] == {"user_id": "123"}

    async def test_logs_warning_for_domain_exception(self, mock_request):
        """Test logs warning when handling domain exceptions.

        Arrange: EntityNotFoundError raised
        Act: Call domain_exception_handler
        Assert: logger.warning called (lines 49-55)
        """
        # Arrange
        exc = EntityNotFoundError("Not found")

        # Act
        with patch("src.presentation.api.middleware.error_handling.logger") as mock_logger:
            await domain_exception_handler(mock_request, exc)

        # Assert
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "domain_exception"

    @pytest.mark.parametrize(
        ("exc_class", "expected_status"),
        [
            (EntityNotFoundError, status.HTTP_404_NOT_FOUND),
            (ValidationError, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (BusinessRuleViolationError, status.HTTP_409_CONFLICT),
            (DomainException, status.HTTP_400_BAD_REQUEST),
        ],
        ids=["not_found", "validation", "business_rule", "generic"],
    )
    async def test_status_codes_for_all_domain_exception_types(
        self, mock_request, exc_class, expected_status
    ):
        """Test correct HTTP status code for each domain exception type.

        Parametrized test covering all domain exception subclasses.
        """
        # Arrange
        exc = exc_class("Test message")

        # Act
        response = await domain_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == expected_status


# ============================================================================
# validation_exception_handler Tests
# ============================================================================


class TestValidationExceptionHandler:
    """Tests for validation_exception_handler covering lines 91-105."""

    async def test_returns_422_for_request_validation_error(self, mock_request):
        """Test returns 422 for RequestValidationError.

        Arrange: RequestValidationError with error details
        Act: Call validation_exception_handler
        Assert: Response status 422 (lines 104-108)
        """
        # Arrange
        from pydantic import BaseModel

        class TestModel(BaseModel):
            email: str

        try:
            TestModel(email=123)  # invalid type
        except Exception:  # noqa: S110
            pass

        exc = MagicMock(spec=RequestValidationError)
        exc.errors = MagicMock(
            return_value=[{"loc": ["body", "email"], "msg": "Invalid", "type": "type_error"}]
        )

        # Act
        response = await validation_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_includes_validation_errors_in_response(self, mock_request):
        """Test includes validation error details in response.

        Arrange: RequestValidationError with specific errors
        Act: Call validation_exception_handler
        Assert: Error details included in response body (lines 97-103)
        """
        # Arrange
        errors = [
            {"loc": ["body", "email"], "msg": "not a valid email", "type": "value_error.email"}
        ]
        exc = MagicMock(spec=RequestValidationError)
        exc.errors = MagicMock(return_value=errors)

        # Act
        response = await validation_exception_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Request validation failed"
        assert data["error"]["details"] == errors

    async def test_logs_warning_for_validation_error(self, mock_request):
        """Test logs warning when handling validation errors.

        Arrange: RequestValidationError
        Act: Call validation_exception_handler
        Assert: logger.warning called (lines 91-95)
        """
        # Arrange
        exc = MagicMock(spec=RequestValidationError)
        exc.errors = MagicMock(return_value=[])

        # Act
        with patch("src.presentation.api.middleware.error_handling.logger") as mock_logger:
            await validation_exception_handler(mock_request, exc)

        # Assert
        mock_logger.warning.assert_called_once()
        assert mock_logger.warning.call_args[0][0] == "validation_error"


# ============================================================================
# integrity_error_handler Tests
# ============================================================================


class TestIntegrityErrorHandler:
    """Tests for integrity_error_handler covering lines 126-148."""

    async def test_returns_409_for_integrity_error(self, mock_request):
        """Test returns 409 Conflict for IntegrityError.

        Arrange: Generic IntegrityError
        Act: Call integrity_error_handler
        Assert: Response status 409 (lines 148-151)
        """
        # Arrange
        orig = MagicMock()
        orig.__str__ = MagicMock(return_value="some constraint error")
        exc = IntegrityError("statement", {}, orig)

        # Act
        response = await integrity_error_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_returns_resource_exists_for_unique_violation(self, mock_request):
        """Test returns 'Resource already exists' message for unique constraint violation.

        Arrange: IntegrityError with 'duplicate' in message
        Act: Call integrity_error_handler
        Assert: Message is 'Resource already exists' (lines 136-138)
        """
        # Arrange
        orig = MagicMock()
        orig.__str__ = MagicMock(return_value="duplicate key value violates unique constraint")
        exc = IntegrityError("statement", {}, orig)

        # Act
        response = await integrity_error_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["message"] == "Resource already exists"
        assert data["error"]["code"] == "INTEGRITY_ERROR"
        assert "already exists" in data["error"]["details"]

    async def test_returns_unique_message_for_unique_keyword(self, mock_request):
        """Test recognizes 'unique' keyword in error message.

        Arrange: IntegrityError with 'unique' in message
        Act: Call integrity_error_handler
        Assert: Returns resource-already-exists message (line 136)
        """
        # Arrange
        orig = MagicMock()
        orig.__str__ = MagicMock(return_value="UNIQUE constraint failed: users.email")
        exc = IntegrityError("statement", {}, orig)

        # Act
        response = await integrity_error_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["message"] == "Resource already exists"

    async def test_returns_generic_message_for_non_unique_constraint(self, mock_request):
        """Test returns generic message for non-duplicate integrity violations.

        Arrange: IntegrityError with foreign key error
        Act: Call integrity_error_handler
        Assert: Returns generic 'Database constraint violation' (lines 134, 139-148)
        """
        # Arrange
        orig = MagicMock()
        orig.__str__ = MagicMock(return_value="foreign key constraint violation")
        exc = IntegrityError("statement", {}, orig)

        # Act
        response = await integrity_error_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["message"] == "Database constraint violation"
        assert data["error"]["details"] is None

    async def test_logs_error_for_integrity_error(self, mock_request):
        """Test logs error when handling integrity errors.

        Arrange: IntegrityError
        Act: Call integrity_error_handler
        Assert: logger.error called (lines 126-129)
        """
        # Arrange
        orig = MagicMock()
        orig.__str__ = MagicMock(return_value="constraint violation")
        exc = IntegrityError("statement", {}, orig)

        # Act
        with patch("src.presentation.api.middleware.error_handling.logger") as mock_logger:
            await integrity_error_handler(mock_request, exc)

        # Assert
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args[0][0] == "database_integrity_error"


# ============================================================================
# sqlalchemy_error_handler Tests
# ============================================================================


class TestSQLAlchemyErrorHandler:
    """Tests for sqlalchemy_error_handler covering lines 168-182."""

    async def test_returns_500_for_database_error(self, mock_request):
        """Test returns 500 Internal Server Error for SQLAlchemyError.

        Arrange: Generic SQLAlchemyError
        Act: Call sqlalchemy_error_handler
        Assert: Response status 500 (lines 182-185)
        """
        # Arrange
        exc = SQLAlchemyError("Connection pool exhausted")

        # Act
        response = await sqlalchemy_error_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_returns_database_error_code(self, mock_request):
        """Test returns DATABASE_ERROR code in response.

        Arrange: SQLAlchemyError
        Act: Call sqlalchemy_error_handler
        Assert: Error code is DATABASE_ERROR (lines 173-180)
        """
        # Arrange
        exc = SQLAlchemyError("Timeout")

        # Act
        response = await sqlalchemy_error_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["code"] == "DATABASE_ERROR"
        assert "processing your request" in data["error"]["message"]
        assert data["error"]["details"] is None

    async def test_logs_error_for_database_error(self, mock_request):
        """Test logs error when handling SQLAlchemy errors.

        Arrange: SQLAlchemyError
        Act: Call sqlalchemy_error_handler
        Assert: logger.error called (lines 168-172)
        """
        # Arrange
        exc = SQLAlchemyError("DB connection failed")

        # Act
        with patch("src.presentation.api.middleware.error_handling.logger") as mock_logger:
            await sqlalchemy_error_handler(mock_request, exc)

        # Assert
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args[0][0] == "database_error"


# ============================================================================
# generic_exception_handler Tests
# ============================================================================


class TestGenericExceptionHandler:
    """Tests for generic_exception_handler covering lines 202-217."""

    async def test_returns_500_for_unhandled_exception(self, mock_request):
        """Test returns 500 Internal Server Error for any unhandled exception.

        Arrange: Generic Exception
        Act: Call generic_exception_handler
        Assert: Response status 500 (lines 216-220)
        """
        # Arrange
        exc = RuntimeError("Unexpected failure")

        # Act
        response = await generic_exception_handler(mock_request, exc)

        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    async def test_returns_internal_server_error_code(self, mock_request):
        """Test returns INTERNAL_SERVER_ERROR code in response.

        Arrange: Any Exception
        Act: Call generic_exception_handler
        Assert: Error code is INTERNAL_SERVER_ERROR (lines 209-215)
        """
        # Arrange
        exc = ValueError("Some unexpected error")

        # Act
        response = await generic_exception_handler(mock_request, exc)

        # Assert
        import json

        data = json.loads(response.body)
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "unexpected error" in data["error"]["message"]
        assert data["error"]["details"] is None

    async def test_logs_exception_for_unhandled_error(self, mock_request):
        """Test logs exception when handling unhandled errors.

        Arrange: Generic Exception
        Act: Call generic_exception_handler
        Assert: logger.exception called (lines 202-207)
        """
        # Arrange
        exc = RuntimeError("Critical failure")

        # Act
        with patch("src.presentation.api.middleware.error_handling.logger") as mock_logger:
            await generic_exception_handler(mock_request, exc)

        # Assert
        mock_logger.exception.assert_called_once()
        call_args = mock_logger.exception.call_args
        assert call_args[0][0] == "unhandled_exception"

    async def test_includes_exception_type_in_log(self, mock_request):
        """Test includes exception type name in the log entry.

        Arrange: TypeError exception
        Act: Call generic_exception_handler
        Assert: exception_type in log call kwargs (lines 203-207)
        """
        # Arrange
        exc = TypeError("type error")

        # Act
        with patch("src.presentation.api.middleware.error_handling.logger") as mock_logger:
            await generic_exception_handler(mock_request, exc)

        # Assert
        call_kwargs = mock_logger.exception.call_args[1]
        assert call_kwargs["exception_type"] == "TypeError"


# ============================================================================
# setup_exception_handlers Tests
# ============================================================================


class TestSetupExceptionHandlers:
    """Tests for setup_exception_handlers covering lines 233-252."""

    def test_registers_domain_exception_handler(self):
        """Test registers DomainException handler on FastAPI app.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: DomainException handler registered (lines 233-237)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        # Check that DomainException was registered
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert DomainException in registered_exception_types

    def test_registers_entity_not_found_handler(self):
        """Test registers EntityNotFoundError handler on FastAPI app.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: EntityNotFoundError handler registered (line 235)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert EntityNotFoundError in registered_exception_types

    def test_registers_validation_error_handler(self):
        """Test registers ValidationError handler on FastAPI app.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: ValidationError handler registered (line 236)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert ValidationError in registered_exception_types

    def test_registers_request_validation_handler(self):
        """Test registers RequestValidationError handler on FastAPI app.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: RequestValidationError handler registered (line 241)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert RequestValidationError in registered_exception_types

    def test_registers_integrity_error_handler(self):
        """Test registers IntegrityError handler on FastAPI app.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: IntegrityError handler registered (line 246)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert IntegrityError in registered_exception_types

    def test_registers_sqlalchemy_error_handler(self):
        """Test registers SQLAlchemyError handler on FastAPI app.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: SQLAlchemyError handler registered (line 247)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert SQLAlchemyError in registered_exception_types

    def test_registers_generic_exception_handler(self):
        """Test registers generic Exception catch-all handler.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: Exception handler registered (line 251)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert
        registered_exception_types = [
            call_args[0][0] for call_args in app.add_exception_handler.call_args_list
        ]
        assert Exception in registered_exception_types

    def test_registers_all_handlers_total_count(self):
        """Test registers the expected total number of exception handlers.

        Arrange: FastAPI app
        Act: Call setup_exception_handlers
        Assert: Correct number of handlers registered (9 total)
        """
        # Arrange
        app = FastAPI()
        app.add_exception_handler = MagicMock()

        # Act
        setup_exception_handlers(app)

        # Assert - 4 domain + 2 validation + 2 database + 1 generic = 9
        assert app.add_exception_handler.call_count == 9
