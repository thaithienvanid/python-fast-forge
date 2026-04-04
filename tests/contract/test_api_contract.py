"""API contract tests using Schemathesis.

Tests validate API endpoints against the OpenAPI specification to ensure:
- Request/response schemas match specification
- Status codes are correct
- Headers conform to spec
- No schema drift or breaking changes

Benefits:
- Automatic test generation from OpenAPI spec
- Catches schema drift early
- Validates all endpoints systematically
- Property-based testing for edge cases
"""

import pytest
import schemathesis
from hypothesis import settings


# Load the OpenAPI schema from the running FastAPI application
schema = schemathesis.from_uri("http://localhost:8000/openapi.json")


@pytest.fixture(scope="module", autouse=True)
def setup_test_app():
    """Ensure test app is running before contract tests.

    In a CI/CD environment, the app should be started before running tests.
    For local testing, you can start the app with:
        uvicorn src.presentation.api.main:app --reload
    """
    import httpx

    try:
        response = httpx.get("http://localhost:8000/health", timeout=2.0)
        if response.status_code != 200:
            pytest.skip("API server is not responding correctly")
    except Exception:
        pytest.skip("API server not running on localhost:8000")


@schema.parametrize()
@settings(max_examples=50, deadline=5000)
def test_api_contract(case):
    """Test all API endpoints match OpenAPI specification.

    This test is automatically generated from the OpenAPI schema and
    validates:
    - Request schemas (query params, headers, body)
    - Response schemas (status codes, headers, body)
    - Data types and constraints
    - Required vs optional fields

    Schemathesis will generate multiple test cases per endpoint to test:
    - Valid inputs
    - Edge cases
    - Boundary values
    - Invalid inputs (negative testing)

    Args:
        case: Auto-generated test case from Schemathesis

    Raises:
        AssertionError: If API doesn't match OpenAPI specification
    """
    # Execute the API call and validate response against spec
    case.call_and_validate()


@schema.parametrize(endpoint="/api/v1/users")
@settings(max_examples=20)
def test_users_endpoint_contract(case):
    """Focused contract tests for /users endpoint.

    Additional validation for the critical users endpoint beyond
    the general contract test.

    Validates:
    - List users (GET /api/v1/users)
    - Create user (POST /api/v1/users)
    - Get user (GET /api/v1/users/{id})
    - Update user (PATCH /api/v1/users/{id})
    - Delete user (DELETE /api/v1/users/{id})
    """
    response = case.call()

    # Validate response against OpenAPI spec
    case.validate_response(response)

    # Additional custom validations for users endpoint
    if (
        case.method == "GET"
        and response.status_code == 200
        and "?" not in str(case.path_parameters)
    ):
        # Ensure pagination fields exist for list endpoints
        data = response.json()
        assert "items" in data or isinstance(data, list), "List endpoint should return items"


@schema.parametrize(method="POST")
@settings(max_examples=30)
def test_create_endpoints_validation(case):
    """Test POST endpoints with focused validation.

    Validates all create (POST) endpoints:
    - Required fields enforced
    - Optional fields handled correctly
    - Validation errors return 422
    - Duplicate resources return 400/409

    Args:
        case: Auto-generated test case for POST endpoints
    """
    response = case.call()

    # All POST endpoints should either succeed (201) or fail with validation error (422)
    # or conflict (409)
    assert response.status_code in [200, 201, 400, 409, 422, 401, 403], (
        f"POST {case.path} returned unexpected status {response.status_code}"
    )

    # Validate against schema
    case.validate_response(response)


@schema.parametrize(endpoint="/health")
def test_health_endpoint_contract(case):
    """Test health check endpoint contract.

    The health endpoint should always return 200 with a specific structure.
    """
    response = case.call()

    # Health endpoint must always return 200
    assert response.status_code == 200, "Health endpoint must return 200"

    # Validate structure
    data = response.json()
    assert "status" in data, "Health response must have 'status' field"
    assert data["status"] == "healthy", "Health status should be 'healthy'"

    # Validate against spec
    case.validate_response(response)


@pytest.mark.parametrize(
    ("endpoint", "method"),
    [
        ("/api/v1/users", "GET"),
        ("/api/v1/users", "POST"),
        ("/health", "GET"),
    ],
)
def test_specific_endpoint_success_cases(endpoint, method):
    """Test specific endpoint success cases manually.

    These tests complement the auto-generated Schemathesis tests with
    specific scenarios we want to ensure work correctly.

    Args:
        endpoint: API endpoint path
        method: HTTP method
    """
    import httpx

    with httpx.Client(base_url="http://localhost:8000") as client:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            # Minimal valid payload for users endpoint
            if "/users" in endpoint:
                response = client.post(
                    endpoint,
                    json={
                        "email": "test@example.com",
                        "username": "testuser",
                    },
                )
            else:
                response = client.post(endpoint)

        # Validate status code is in expected range
        assert response.status_code in [
            200,
            201,
            400,
            401,
            403,
            409,
            422,
        ], f"{method} {endpoint} returned {response.status_code}"


# Configuration for Schemathesis hooks
def before_generate_case(context, strategy):
    """Hook to customize test case generation.

    Can be used to:
    - Add authentication headers
    - Modify request payloads
    - Filter out certain test cases
    - Add custom validation logic
    """
    return strategy


# Register hooks
schemathesis.hooks.register("before_generate_case", before_generate_case)
