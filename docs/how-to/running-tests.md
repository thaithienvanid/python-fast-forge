# Running Tests

This guide explains how to run different types of tests in the project, including those that require external dependencies like PostgreSQL and Redis.

## Table of Contents

- [Quick Start](#quick-start)
- [Running All Tests](#running-all-tests)
- [Running Specific Test Categories](#running-specific-test-categories)
- [Tests Requiring External Services](#tests-requiring-external-services)
  - [Migration Tests (PostgreSQL)](#migration-tests-postgresql)
  - [Rate Limiting Tests (Redis)](#rate-limiting-tests-redis)
- [Test Coverage](#test-coverage)
- [Troubleshooting](#troubleshooting)

## Quick Start

Run all tests that don't require external services:

```bash
# Using make
make test

# Or directly with pytest
uv run pytest
```

## Running All Tests

```bash
# Run all tests including unit and integration tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run with test output (print statements visible)
uv run pytest tests/ -v -s
```

## Running Specific Test Categories

```bash
# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run specific test file
uv run pytest tests/unit/test_pagination.py

# Run specific test class
uv run pytest tests/unit/test_pagination.py::TestPaginationValidation

# Run specific test method
uv run pytest tests/unit/test_pagination.py::TestPaginationValidation::test_valid_page_size
```

## Tests Requiring External Services

Some tests are skipped by default because they require external services like PostgreSQL or Redis. Here's how to run them:

### Migration Tests (PostgreSQL)

Migration tests verify that Alembic migrations can be applied and reversed correctly. These require a PostgreSQL test database.

#### Setup

1. **Create test database:**
   ```bash
   createdb test_migrations_db
   ```

2. **Verify connection:**
   ```bash
   psql -d test_migrations_db -c "SELECT version();"
   ```

#### Running Migration Tests

```bash
# Run all migration tests (skipped tests will still be skipped)
uv run pytest tests/integration/test_migrations.py -v

# Run only tests that don't require database
uv run pytest tests/integration/test_migrations.py::TestMigrationBestPractices -v

# Run specific migration test (requires removing @pytest.mark.skip decorator)
uv run pytest tests/integration/test_migrations.py::TestMigrationUpgradeDowngrade::test_upgrades_to_head_and_downgrades_to_base -v

# Run all non-skipped tests
uv run pytest tests/integration/test_migrations.py -v -k "not skip"
```

#### Enabling Skipped Tests

To enable migration tests that are skipped by default:

1. Open `tests/integration/test_migrations.py`
2. Remove or comment out the `@pytest.mark.skip` decorator from the test methods you want to run
3. Run the tests as shown above

#### Cleanup

```bash
# Drop test database when done
dropdb test_migrations_db
```

#### Complete Workflow

```bash
# 1. Setup
createdb test_migrations_db

# 2. Run tests
uv run pytest tests/integration/test_migrations.py -v

# 3. Cleanup
dropdb test_migrations_db
```

### Rate Limiting Tests (Redis)

Rate limiting tests verify that rate limiting works correctly with Redis as the storage backend. These require a running Redis server.

#### Setup

1. **Start Redis server:**
   ```bash
   # Using Docker
   docker run -d -p 6379:6379 redis:latest

   # Or using Homebrew (macOS)
   brew services start redis

   # Or manually
   redis-server
   ```

2. **Verify Redis is running:**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

#### Running Rate Limiting Tests

```bash
# Run all rate limiting tests (skipped tests will still be skipped)
uv run pytest tests/integration/test_rate_limiting.py -v

# Run tests that don't require Redis
uv run pytest tests/integration/test_rate_limiting.py::TestGetClientIdentifier -v
uv run pytest tests/integration/test_rate_limiting.py::TestGetLimiter -v
uv run pytest tests/integration/test_rate_limiting.py::TestSetupRateLimiting -v
uv run pytest tests/integration/test_rate_limiting.py::TestRateLimitingConfiguration -v

# Run all non-skipped tests
uv run pytest tests/integration/test_rate_limiting.py -v -k "not skip"
```

#### Enabling Skipped Tests

To enable rate limiting tests that require Redis:

1. Open `tests/integration/test_rate_limiting.py`
2. Remove or comment out the `@pytest.mark.skip(reason="Requires Redis server running")` decorator from tests in `TestRateLimitingBehavior`
3. Ensure Redis is running (see Setup above)
4. Run the tests

#### Cleanup

```bash
# Stop Redis (Docker)
docker stop $(docker ps -q --filter ancestor=redis:latest)

# Stop Redis (Homebrew)
brew services stop redis
```

#### Complete Workflow

```bash
# 1. Setup
docker run -d -p 6379:6379 redis:latest
redis-cli ping  # Verify connection

# 2. Remove @pytest.mark.skip decorators from TestRateLimitingBehavior tests

# 3. Run tests
uv run pytest tests/integration/test_rate_limiting.py::TestRateLimitingBehavior -v

# 4. Cleanup
docker stop $(docker ps -q --filter ancestor=redis:latest)
```

## Test Coverage

Generate test coverage reports:

```bash
# Run tests with coverage
uv run pytest --cov=src tests/

# Generate HTML coverage report
uv run pytest --cov=src --cov-report=html tests/

# Open coverage report in browser
open htmlcov/index.html
```

## Troubleshooting

### PostgreSQL Connection Issues

If migration tests fail to connect to PostgreSQL:

1. Check PostgreSQL is running:
   ```bash
   pg_isready
   ```

2. Verify database exists:
   ```bash
   psql -l | grep test_migrations_db
   ```

3. Check connection string in test:
   ```python
   # Default: postgresql+asyncpg://postgres:postgres@localhost:5432/test_migrations_db
   # Adjust username/password if needed
   ```

### Redis Connection Issues

If rate limiting tests fail to connect to Redis:

1. Check Redis is running:
   ```bash
   redis-cli ping
   ```

2. Check Redis connection details:
   ```bash
   redis-cli INFO server
   ```

3. Verify Redis URL in tests:
   ```python
   # Default: redis://localhost:6379/0
   ```

### Test Isolation Issues

If tests interfere with each other:

1. **For Redis tests:** The `clear_redis_before_behavior_test` fixture automatically clears Redis between tests
2. **For database tests:** Each test should use transactions that are rolled back
3. **Run tests in isolation:**
   ```bash
   uv run pytest tests/integration/test_rate_limiting.py::TestRateLimitingBehavior::test_allows_requests_within_limit -v
   ```

### Import Errors

If you get import errors:

```bash
# Ensure dependencies are installed
uv sync

# Run tests from project root
cd /path/to/python-fast-forge
uv run pytest
```

## Additional Resources

- [Testing Reference](../reference/testing.md) - Comprehensive testing documentation
- [Debugging Guide](./debugging.md) - Tips for debugging tests
- [pytest Documentation](https://docs.pytest.org/) - Official pytest docs
