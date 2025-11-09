# Contributing to Python FastAPI Boilerplate

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/python-fast-forge.git
cd python-fast-forge
```

2. **Install uv (fast Python package manager)**

```bash
# Install uv if you haven't already
pip install uv
```

3. **Install development dependencies**

```bash
# Install all dependencies including dev dependencies
uv sync --dev
```

4. **Set up pre-commit hooks** (optional but recommended)

```bash
uv run pre-commit install
```

## Development Workflow

1. **Create a branch** for your feature or bugfix

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bugfix-name
```

2. **Make your changes** following the coding standards

3. **Write or update tests** for your changes

```bash
uv run pytest tests/
```

4. **Run linters and formatters**

```bash
make format
make lint
```

5. **Commit your changes** with clear, descriptive messages

```bash
git add .
git commit -m "feat: add new feature description"
```

6. **Push to your fork**

```bash
git push origin feature/your-feature-name
```

7. **Create a Pull Request** from your fork to the main repository

## Coding Standards

### Python Style

- Follow PEP 8 style guide
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use **Ruff** for code formatting and linting (replaces Black, isort, flake8)
  - Format: `uv run ruff format`
  - Lint: `uv run ruff check --fix`
  - See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for complete tooling guide

### Code Organization

- Follow clean architecture principles
- Keep layers separated (domain, application, infrastructure, presentation)
- Domain layer should have no external dependencies
- Use dependency injection for coupling concerns

### Naming Conventions

- Classes: `PascalCase`
- Functions/Methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Documentation

- Write docstrings for all public classes and functions
- Use Google-style docstrings
- Keep comments concise and meaningful
- Update README.md if adding new features

### Testing

- Write tests for all new features
- Maintain or improve code coverage → [detailed stats](docs/reference/testing.md#test-statistics)
- Use descriptive test names: `test_should_do_something_when_condition`
- Follow AAA pattern (Arrange, Act, Assert)

## Commit Messages

Follow conventional commits specification:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add tenant isolation middleware
fix: resolve database connection timeout
docs: update API documentation
test: add tests for health check endpoint
```

## Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new functionality
3. **Ensure all tests pass**: `make test`
4. **Run linters**: `make lint`
5. **Update CHANGELOG** if applicable
6. **Request review** from maintainers

### PR Guidelines

- Keep PRs focused on a single feature or fix
- Write clear PR descriptions
- Reference related issues
- Respond to review feedback promptly
- Keep your branch up to date with main

## Code Review

All submissions require review. We look for:

- Code quality and readability
- Test coverage
- Documentation completeness
- Adherence to project standards
- Performance considerations
- Security implications

## Testing Guidelines

### Unit Tests

- Test individual components in isolation
- Mock external dependencies
- Cover edge cases and error scenarios

### Integration Tests

- Test component interactions
- Use test database for data layer tests
- Clean up test data after tests

### Running Tests

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run with coverage report
make test-cov

# Run specific test file
uv run pytest tests/test_specific.py

# Run tests matching pattern
uv run pytest -k "test_pattern"
```

## Important Project Notes

### No User Authentication System

**This project does NOT include user authentication features.** The User model contains only basic fields:
- `id`, `email`, `username`, `full_name`, `is_active`, `tenant_id`, `created_at`, `updated_at`
- No password fields or authentication logic exists
- If you need authentication, you must implement it yourself

### Tenant Isolation Status

**The X-Tenant-Token JWT validation is NOT YET IMPLEMENTED:**
- The tenant isolation middleware accepts `X-Tenant-Token` header
- JWT validation currently returns HTTP 501 (Not Implemented)
- Multi-tenant data isolation is prepared but JWT verification is pending
- Do not assume JWT validation is working - it will return 501 errors

### Database Migrations

Migration files use hash-based revision IDs:
- Format: `2024_MM_DD-{hash}_{slug}.py`
- Example: `2024_11_07-a1b2c3d4e5f6_initial_user_model.py`
- Generated automatically by Alembic with `uv run alembic revision --autogenerate -m "description"`

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions/classes
- Update API documentation if endpoints change
- Include examples where helpful

## Questions?

Feel free to:
- Open an issue for bugs or feature requests
- Start a discussion for questions
- Contact maintainers for guidance

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help create a welcoming environment

Thank you for contributing!
