#!/bin/bash
# Initialize the development environment

set -e

echo "🚀 Setting up Python FastAPI Boilerplate development environment..."

# Check Python version (requires 3.12+)
echo "📌 Checking Python version..."
python --version
PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "⚠️  Please restart your terminal and run this script again"
    exit 0
fi

# Install dependencies with uv
echo "📦 Installing dependencies with uv..."
uv sync --dev

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration"
fi

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
uv run pre-commit install

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "🐳 Docker is available"
    echo "   Services: PostgreSQL, Redis, Mailpit, Temporal"
else
    echo "⚠️  Docker not found. You'll need to set up services manually."
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Update .env with your configuration"
echo "  2. Start infrastructure services:"
echo "     docker-compose --profile infra up -d"
echo "     (PostgreSQL, Redis, Mailpit, Temporal)"
echo "  3. Run 'make migrate' to apply database migrations"
echo "  4. Run 'uv run python main.py' to start the API server"
echo "  5. Run 'uv run python worker.py' to start the Temporal worker"
echo "  6. Visit http://localhost:8000/docs for API documentation"
echo "  7. Visit http://localhost:8080 for Temporal UI"
echo ""
echo "Or run everything in Docker:"
echo "  docker-compose --profile infra --profile app up -d"
echo ""
