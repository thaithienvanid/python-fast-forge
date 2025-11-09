# Testing Guide

Complete guide to testing in this project.

## Test Statistics

> **Last Updated**: 2025-01-11
> **Status**: ✅ All tests passing (CI verified)

### Overall Coverage
- **Total Tests**: 1,082 (858 unit + 224 integration)
- **Overall Coverage**: 83.34% (target: 90%)
- **Passing Rate**: 98.8% (1,069 passed, 13 skipped)

### Coverage by Module

| Module | Tests | Coverage | Status |
|--------|-------|----------|--------|
| Tenant Authentication (`tenant_auth.py`) | 21 | 87.69% | ✅ |
| API Dependencies (`dependencies.py`) | 24 | 97.87% | ✅ |
| Tenant Claims Model (`tenant_claims.py`) | - | 78.05% | ✅ |
| Pagination (`pagination.py`) | 89 | 97.96% | ✅ |
| User Use Cases (`user_usecases.py`) | 156 | 67.60% | 🟡 |
| User Endpoints (`users.py`) | 78 | 87.27% | ✅ |
| Base Repository (`base_repository.py`) | 23 | 35.97% | 🟡 |
| Cached Base Repository (`cached_base_repository.py`) | 23 | 91.53% | ✅ |
| Cached User Repository (`cached_user_repository.py`) | 21 | 87.10% | ✅ |
| Cache Layer (`redis_cache.py`) | 31 | 95.68% | ✅ |

### Test Types Distribution
- **Unit Tests**: 858 (79.3%) - Fast, isolated business logic
- **Integration Tests**: 224 (20.7%) - API endpoints with real database
- **Property-Based Tests**: 47 - Hypothesis for edge cases and invariants

### Test Categories
```
Tenant Authentication:    45 tests (token creation, validation, expiration, rotation)
User Management:         266 tests (CRUD operations, validation, use cases)
Repository Layer:         67 tests (base, cached base, cached user repositories)
API Endpoints:            78 tests (HTTP requests, response validation)
Configuration:            26 tests (settings, environment variables, validation)
Pagination:               89 tests (boundary conditions, validation)
Filtering:               124 tests (FilterSet, char filters, array filters, number filters)
Serialization:            54 tests (JSON, sanitization, encoding)
Exceptions:               12 tests (error handling, custom exceptions)
Property-Based:           47 tests (invariants, edge cases with Hypothesis)
Cache Layer:              31 tests (Redis cache, compression, metrics)
Security:                178 tests (headers, API signatures, rate limiting)
```

## Overview

This project uses a comprehensive testing strategy with multiple test types:

- **Unit Tests** - Test business logic in isolation (use cases, utilities)
- **Integration Tests** - Test API endpoints with real database
- **Property-Based Tests** - Test invariants with random data (Hypothesis)

## Test Structure

```
tests/
├── unit/                      # Unit tests (fast, isolated)
│   ├── test_user_usecases.py  # Use case tests
│   ├── test_tenant_auth.py    # Tenant JWT authentication (21 tests)
│   ├── test_dependencies.py   # API dependencies (24 tests)
│   ├── test_log_sanitization.py
│   └── test_serialization.py
│
├── integration/               # Integration tests (API + DB)
│   ├── test_user_endpoints.py # API endpoint tests
│   ├── test_health.py
│   └── test_migrations.py
│
├── factories.py               # Test data factories
├── strategies.py              # Hypothesis strategies
├── conftest.py                # Pytest fixtures
└── README.md                  # Test documentation
```

## Running Tests

### All Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=src --cov-report=html

# Parallel execution (faster)
pytest -n auto
```

### Specific Test Types

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific file
pytest tests/unit/test_user_usecases.py

# Specific test
pytest tests/unit/test_user_usecases.py::TestCreateUserUseCase::test_creates_user_success
```

### Test Markers

```bash
# Slow tests only
pytest -m slow

# Skip slow tests
pytest -m "not slow"

# Run property-based tests
pytest -m hypothesis
```

## Writing Unit Tests

Unit tests focus on testing business logic (use cases) in isolation with mocked dependencies.

### AAA Pattern

All tests follow the **Arrange-Act-Assert (AAA)** pattern:

```python
async def test_creates_user_with_valid_data():
    """Test creating user with valid data.

    Arrange: Mock repository, prepare use case and input data
    Act: Execute use case
    Assert: Verify user was created with correct data
    """
    # Arrange - Set up test data and mocks
    mock_repo = Mock(spec=IUserRepository)
    mock_repo.get_by_email.return_value = None  # No existing user
    mock_repo.add.return_value = User(id=uuid4(), email="test@example.com")

    use_case = CreateUserUseCase(mock_repo)

    # Act - Execute the operation being tested
    user = await use_case.execute(
        email="test@example.com",
        username="testuser",
        full_name="Test User"
    )

    # Assert - Verify expected outcomes
    assert user.email == "test@example.com"
    assert user.username == "testuser"
    mock_repo.add.assert_called_once()
```

### Mocking Repositories

Mock repository dependencies to test use cases in isolation:

```python
@pytest.fixture
def mock_user_repository():
    """Mock user repository for testing."""
    repo = Mock(spec=IUserRepository)
    repo.get_by_id.return_value = None
    repo.get_by_email.return_value = None
    repo.get_by_username.return_value = None
    repo.add.return_value = None
    repo.update.return_value = None
    repo.delete.return_value = None
    return repo


async def test_get_user_success(mock_user_repository):
    """Test getting user by ID successfully."""
    # Arrange
    expected_user = User(id=uuid4(), email="test@example.com", username="test")
    mock_user_repository.get_by_id.return_value = expected_user

    use_case = GetUserUseCase(mock_user_repository)

    # Act
    user = await use_case.execute(user_id=expected_user.id)

    # Assert
    assert user == expected_user
    mock_user_repository.get_by_id.assert_called_once_with(expected_user.id)
```

### Testing Exceptions

Test that use cases raise appropriate exceptions:

```python
async def test_raises_error_when_user_not_found(mock_user_repository):
    """Test that EntityNotFoundError is raised when user doesn't exist.

    Arrange: Mock repository returns None
    Act: Execute use case
    Assert: EntityNotFoundError is raised
    """
    # Arrange
    mock_user_repository.get_by_id.return_value = None
    use_case = GetUserUseCase(mock_user_repository)

    # Act & Assert
    with pytest.raises(EntityNotFoundError) as exc_info:
        await use_case.execute(user_id=uuid4())

    assert "not found" in str(exc_info.value)
```

### Parametrized Tests

Test multiple scenarios with one test function:

```python
@pytest.mark.parametrize(
    "email,expected_error",
    [
        ("invalid-email", "Invalid email format"),
        ("", "Email cannot be empty"),
        ("test@", "Invalid domain"),
        ("@example.com", "Invalid local part"),
    ],
)
async def test_rejects_invalid_email(email, expected_error, mock_user_repository):
    """Test that invalid emails are rejected with appropriate errors.

    Arrange: Use case with mock repository
    Act: Execute with invalid email
    Assert: ValidationError is raised with expected message
    """
    # Arrange
    use_case = CreateUserUseCase(mock_user_repository)

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        await use_case.execute(email=email, username="test", full_name="Test")

    assert expected_error in str(exc_info.value)
```

### Testing Tenant Authentication

The tenant authentication system has comprehensive test coverage for token creation, validation, expiration, rotation, and error handling. See [Test Statistics](#test-statistics) for detailed coverage metrics.

**Example: Testing Token Creation and Validation**

```python
from uuid import uuid4
from datetime import timedelta
from src.utils.tenant_auth import create_tenant_token, decode_tenant_token

def test_creates_valid_tenant_token():
    """Test creating and decoding a valid tenant token.

    Arrange: Generate tenant ID
    Act: Create token and decode it
    Assert: Decoded claims match original tenant ID
    """
    # Arrange
    tenant_id = uuid4()

    # Act
    token = create_tenant_token(tenant_id)
    claims = decode_tenant_token(token)

    # Assert
    assert claims.tenant_id == tenant_id
    assert claims.exp is not None
    assert claims.type == "tenant_access"
```

**Example: Testing Token Expiration**

```python
from jose import JWTError

def test_raises_error_for_expired_token():
    """Test that expired tokens raise JWTError.

    Arrange: Create token with negative expiration
    Act: Attempt to decode expired token
    Assert: JWTError is raised
    """
    # Arrange
    tenant_id = uuid4()
    token = create_tenant_token(
        tenant_id,
        expires_delta=timedelta(seconds=-1)
    )

    # Act & Assert
    with pytest.raises(JWTError):
        decode_tenant_token(token)
```

**Example: Testing API Dependency with Tenant Tokens**

```python
from src.presentation.api.dependencies import get_tenant_id
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_extracts_tenant_id_from_valid_token():
    """Test get_tenant_id extracts UUID from valid token.

    Arrange: Create valid tenant token
    Act: Call get_tenant_id dependency
    Assert: Returns correct tenant UUID
    """
    # Arrange
    tenant_id = uuid4()
    token = create_tenant_token(tenant_id)

    # Act
    result = await get_tenant_id(x_tenant_token=token)

    # Assert
    assert result == tenant_id

@pytest.mark.asyncio
async def test_raises_401_for_expired_token():
    """Test get_tenant_id raises 401 for expired tokens.

    Arrange: Create expired token
    Act: Call get_tenant_id dependency
    Assert: HTTPException with 401 status
    """
    # Arrange
    tenant_id = uuid4()
    token = create_tenant_token(
        tenant_id,
        expires_delta=timedelta(seconds=-1)
    )

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_tenant_id(x_tenant_token=token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "TENANT_TOKEN_EXPIRED"
```

**Running Tenant Authentication Tests:**

```bash
# Run all tenant auth tests
pytest tests/unit/test_tenant_auth.py tests/unit/test_dependencies.py -v

# Run with coverage
pytest tests/unit/test_tenant_auth.py tests/unit/test_dependencies.py \
    --cov=src.utils.tenant_auth \
    --cov=src.domain.tenant_claims \
    --cov=src.presentation.api.dependencies \
    --cov-report=term-missing

# Run specific test categories
pytest tests/unit/test_tenant_auth.py::TestCreateTenantToken -v  # Token creation
pytest tests/unit/test_tenant_auth.py::TestDecodeTenantToken -v  # Token validation
pytest tests/unit/test_dependencies.py::TestGetTenantIdWithValidToken -v  # API integration
```

## Writing Integration Tests

Integration tests verify that API endpoints work correctly with a real database.

### Test Client Fixture

Use the `client` fixture to make HTTP requests:

```python
async def test_create_user_endpoint(client: TestClient):
    """Test POST /api/v1/users endpoint.

    Arrange: Valid user data
    Act: POST request to /api/v1/users
    Assert: Returns 201 with user data
    """
    # Arrange
    user_data = {
        "email": "newuser@example.com",
        "username": "newuser",
        "full_name": "New User"
    }

    # Act
    response = client.post("/api/v1/users", json=user_data)

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["username"] == user_data["username"]
    assert "id" in data
    assert "created_at" in data
```

### Database Cleanup

Each test runs in a transaction that's rolled back after the test:

```python
@pytest.fixture(scope="function")
async def client(db_session):
    """Test client with database session."""
    # Transaction starts
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    # Transaction rolled back automatically
```

### Testing with Multi-Tenancy

Test tenant isolation by providing `X-Tenant-Token` JWT header:

```python
async def test_tenant_isolation(client: TestClient):
    """Test that users are isolated by tenant.

    Arrange: Create user for tenant A
    Act: Try to access with tenant B token
    Assert: Returns 404 Not Found
    """
    # Arrange - Create user for tenant A
    tenant_a = uuid4()
    user_data = {"email": "user@example.com", "username": "user"}

    # Generate JWT token for tenant A
    token_a = create_jwt_token({"tenant_id": str(tenant_a)})

    response = client.post(
        "/api/v1/users",
        json=user_data,
        headers={"X-Tenant-Token": token_a}
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    # Act - Try to get user with tenant B
    tenant_b = uuid4()
    token_b = create_jwt_token({"tenant_id": str(tenant_b)})
    response = client.get(
        f"/api/v1/users/{user_id}",
        headers={"X-Tenant-Token": token_b}
    )

    # Assert - User not found (tenant isolation)
    assert response.status_code == 404
```

### Testing Error Responses

Verify error responses match expected format:

```python
async def test_returns_422_for_invalid_data(client: TestClient):
    """Test that invalid data returns 422 with error details.

    Arrange: Invalid user data (missing required field)
    Act: POST /api/v1/users
    Assert: Returns 422 with validation error details
    """
    # Arrange
    invalid_data = {
        "username": "testuser"
        # Missing required 'email' field
    }

    # Act
    response = client.post("/api/v1/users", json=invalid_data)

    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    error = response.json()
    assert "detail" in error
    assert any("email" in str(e) for e in error["detail"])
```

## Property-Based Testing

Use Hypothesis to test invariants with random data:

```python
from hypothesis import given, strategies as st
from tests.strategies import user_strategy

@given(user_strategy())
async def test_user_roundtrip_serialization(user_data):
    """Test that user data can be serialized and deserialized.

    Property: For any valid user data, serialization followed by
    deserialization should produce equivalent data.

    Arrange: Random user data from strategy
    Act: Serialize to JSON and deserialize
    Assert: Deserialized data matches original
    """
    # Arrange (provided by hypothesis)
    schema = UserCreate(**user_data)

    # Act
    json_data = schema.model_dump_json()
    deserialized = UserCreate.model_validate_json(json_data)

    # Assert - Roundtrip preserves data
    assert deserialized.email == schema.email
    assert deserialized.username == schema.username
```

### Custom Strategies

Define reusable strategies for generating test data:

```python
# tests/strategies.py
from hypothesis import strategies as st

def user_strategy():
    """Generate valid user data."""
    return st.fixed_dictionaries({
        "email": st.emails(),
        "username": st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=3,
            max_size=50
        ),
        "full_name": st.text(min_size=1, max_size=200),
    })
```

## Test Fixtures

### Common Fixtures (conftest.py)

```python
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session():
    """Provide database session for tests."""
    async with async_session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def client(db_session):
    """Test client with database."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Test Data Factories

Use factories to create test data consistently:

```python
# tests/factories.py
from uuid import uuid4

def user_factory(**overrides):
    """Create test user data."""
    defaults = {
        "id": uuid4(),
        "email": f"user_{uuid4().hex[:8]}@example.com",
        "username": f"user_{uuid4().hex[:8]}",
        "full_name": "Test User",
        "is_active": True,
        "tenant_id": None,
    }
    return {**defaults, **overrides}


# Usage in tests
def test_with_factory():
    user = user_factory(email="custom@example.com")
    assert user["email"] == "custom@example.com"
```

## Best Practices

### ✅ DO

1. **Follow AAA pattern** - Clear Arrange, Act, Assert sections
2. **Test one thing** - Each test should verify one behavior
3. **Use descriptive names** - `test_creates_user_with_valid_data` not `test_create`
4. **Write docstrings** - Explain what/why, include AAA breakdown
5. **Mock external dependencies** - Database, external APIs, etc.
6. **Test edge cases** - Empty inputs, null values, boundaries
7. **Use parametrize** - Test multiple scenarios efficiently
8. **Keep tests fast** - Unit tests < 1ms, integration tests < 100ms
9. **Clean up after tests** - Use fixtures, transactions, teardown
10. **Test error paths** - Not just happy path

### ❌ DON'T

1. **Don't test framework code** - FastAPI, SQLAlchemy already tested
2. **Don't test implementation details** - Test behavior, not internals
3. **Don't share state** - Each test should be independent
4. **Don't skip assertions** - Every test needs assertions
5. **Don't write flaky tests** - Tests should be deterministic
6. **Don't hard-code IDs** - Use `uuid4()` for test data
7. **Don't test multiple things** - Split into separate tests
8. **Don't ignore test failures** - Fix immediately
9. **Don't write slow tests** - Optimize or mark as slow
10. **Don't skip test documentation** - Docstrings are required

## Test Organization

### Grouping with Classes

Organize related tests into classes:

```python
class TestUserCreateEndpoint:
    """Tests for POST /api/v1/users endpoint."""

    async def test_creates_user_with_valid_data(self, client):
        """Test creating user with all required fields."""
        # ...

    async def test_rejects_duplicate_email(self, client):
        """Test that duplicate email is rejected."""
        # ...

    @pytest.mark.parametrize("invalid_email", [...])
    async def test_rejects_invalid_email_format(self, client, invalid_email):
        """Test various invalid email formats."""
        # ...
```

### Test Markers

Use markers to categorize tests:

```python
@pytest.mark.slow
async def test_bulk_user_creation():
    """Test creating 1000 users (slow test)."""
    # ...

@pytest.mark.hypothesis
@given(user_strategy())
async def test_user_property(user_data):
    """Property-based test for user validation."""
    # ...
```

## Coverage

### Generate Coverage Report

```bash
# HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=src --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=src --cov-fail-under=80
```

### Coverage Goals

- **Overall:** 80%+ code coverage
- **Use Cases:** 90%+ (critical business logic)
- **API Endpoints:** 85%+ (integration tests)
- **Utilities:** 90%+ (pure functions)

## Debugging Tests

### Run Single Test

```bash
# Verbose output
pytest -v tests/unit/test_user_usecases.py::test_creates_user

# Show print statements
pytest -s tests/unit/test_user_usecases.py

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb
```

### Print Debugging

```python
async def test_example(client):
    response = client.post("/api/v1/users", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 201
```

### Using pytest-pdb

```python
async def test_with_debugger(client):
    response = client.post("/api/v1/users", json=data)

    # Drop into debugger
    import pdb; pdb.set_trace()

    assert response.status_code == 201
```

## Continuous Integration

Tests run automatically on every commit:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          docker-compose up -d
          docker-compose exec api pytest --cov=src
```

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Test-Driven Development](https://testdriven.io/)
- [Architecture Reference](../reference/architecture.md)
