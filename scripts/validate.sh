#!/bin/bash
# Quick validation script to check project structure and code quality

set -e

echo "🔍 Validating Python FastAPI Boilerplate..."
echo ""

# Check Python version
echo "✓ Checking Python version..."
PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "  Python version: $PYTHON_VERSION"
if [ "$(printf '%s\n' "3.12" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.12" ]; then
    echo "  ⚠️  Python 3.12+ recommended (found $PYTHON_VERSION)"
fi

# Check Python files compile
echo "✓ Checking Python syntax..."
python3 -m py_compile main.py worker.py 2>&1 || echo "  ⚠️  Syntax errors found"

# Check required files exist
echo "✓ Checking required files..."
required_files=(
    "README.md"
    "GETTING-STARTED.md"
    "CHANGELOG.md"
    "pyproject.toml"
    "Dockerfile"
    "docker-compose.yml"
    "atlas.hcl"
    ".env.example"
    "Makefile"
    "main.py"
    "worker.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "  ❌ Missing: $file"
        exit 1
    fi
done

# Check required directories
echo "✓ Checking directory structure..."
required_dirs=(
    "src/domain"
    "src/app/usecases"
    "src/app/tasks"
    "src/infrastructure/cache"
    "src/infrastructure/persistence"
    "src/infrastructure/repositories"
    "src/presentation/api"
    "src/presentation/schemas"
    "src/utils"
    "tests/unit"
    "tests/integration"
    "docs"
    "migrations"
)

for dir in "${required_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "  ❌ Missing directory: $dir"
        exit 1
    fi
done

# Check code quality (if tools available)
if command -v uv &> /dev/null; then
    echo "✓ Running code quality checks..."

    echo "  - Ruff linting..."
    uv run ruff check src tests || echo "    ⚠️  Linting issues found"

    echo "  - Ruff formatting..."
    uv run ruff format --check src tests || echo "    ⚠️  Formatting issues found"

    echo "  - MyPy type checking..."
    uv run mypy src --config-file pyproject.toml || echo "    ⚠️  Type errors found"
fi

# Count files
echo ""
echo "📊 Statistics:"
echo "  Python files: $(find src tests -name "*.py" | wc -l)"
echo "  Test files: $(find tests -name "test_*.py" | wc -l)"
echo "  Documentation files: $(find docs -name "*.md" | wc -l)"
echo "  Domain models: $(find src/domain/models -name "*.py" ! -name "__init__.py" | wc -l)"
echo "  Use cases: $(find src/app/usecases -name "*.py" ! -name "__init__.py" | wc -l)"
echo "  API endpoints: $(find src/presentation/api/v1/endpoints -name "*.py" ! -name "__init__.py" | wc -l)"

echo ""
echo "✅ Validation complete! Project structure looks good."
echo ""
echo "Next steps:"
echo "  1. Install dependencies: uv sync --dev"
echo "  2. Copy .env: cp .env.example .env"
echo "  3. Start services: docker-compose --profile infra up -d"
echo "  4. Run migrations: make migrate"
echo "  5. Run tests: uv run pytest tests/"
echo "  6. Start API: uv run python main.py"
echo "  7. Start worker: uv run python worker.py"
echo ""
