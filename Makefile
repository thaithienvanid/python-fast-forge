.PHONY: help install dev test lint format clean docker-up docker-down migrate security audit validate
.DEFAULT_GOAL := help

# ===================================
# Configuration
# ===================================
PYTHON := python3
UV := uv
PYTEST := $(UV) run pytest
RUFF := $(UV) run ruff
MYPY := $(UV) run mypy
BANDIT := $(UV) run bandit
ALEMBIC := $(UV) run alembic

# Source directories
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs

# Docker Compose profiles
PROFILE_INFRA := infra
PROFILE_APP := app
PROFILE_TELEMETRY := telemetry

# ===================================
# Help & Documentation
# ===================================
help:  ## Show this help message
	@echo '╔════════════════════════════════════════════════════════════╗'
	@echo '║  Python FastAPI Boilerplate - Makefile Commands           ║'
	@echo '╚════════════════════════════════════════════════════════════╝'
	@echo ''
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ''

# ===================================
# Installation & Setup
# ===================================
install:  ## Install production dependencies only
	$(UV) sync --no-dev

install-dev:  ## Install all dependencies (dev, test, security)
	$(UV) sync --all-groups

install-minimal:  ## Install minimal dependencies (core + dev tools)
	$(UV) sync --group dev

setup:  ## Initial project setup (env, deps, hooks)
	@echo "🚀 Setting up Python FastAPI Boilerplate..."
	@if [ ! -f .env ]; then \
		cp .env.example .env && echo "✓ Created .env file"; \
	fi
	@$(UV) sync --all-groups
	@$(UV) run pre-commit install
	@echo "✓ Setup complete! Edit .env and run: make docker-up && make migrate"

setup-ci:  ## Setup for CI environment
	$(UV) sync --group dev --group test

# ===================================
# Development
# ===================================
run:  ## Run the FastAPI application
	$(UV) run python main.py

run-reload:  ## Run with auto-reload (development mode)
	$(UV) run uvicorn src.presentation.api:app --reload --host 0.0.0.0 --port 8000

worker:  ## Run the Temporal worker
	$(UV) run python worker.py

dev-all:  ## Run API and worker concurrently
	@echo "🚀 Starting API and worker..."
	@(trap 'kill 0' SIGINT; $(UV) run python main.py & $(UV) run python worker.py & wait)

shell:  ## Open Python REPL with app context
	$(UV) run python -i -c "from src.infrastructure.container import Container; container = Container(); print('Container loaded. Access via: container')"

ipython:  ## Open IPython REPL with app context (requires ipython)
	$(UV) run ipython -i -c "from src.infrastructure.container import Container; container = Container()"

# ===================================
# Testing
# ===================================
test:  ## Run all tests with coverage
	$(PYTEST)

test-unit:  ## Run unit tests only
	$(PYTEST) $(TEST_DIR)/unit/ -v

test-integration:  ## Run integration tests only
	$(PYTEST) $(TEST_DIR)/integration/ -v

test-fast:  ## Run tests without coverage (faster)
	$(PYTEST) -q --tb=short --no-cov

test-cov:  ## Run tests with detailed HTML coverage report
	$(PYTEST) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing
	@echo "✓ Coverage report: htmlcov/index.html"

test-parallel:  ## Run tests in parallel (pytest-xdist)
	$(PYTEST) -n auto

test-watch:  ## Run tests in watch mode (requires pytest-watch)
	$(UV) run ptw --runner "pytest --tb=short"

test-failed:  ## Re-run only failed tests
	$(PYTEST) --lf

test-verbose:  ## Run tests with verbose output
	$(PYTEST) -vv

test-markers:  ## Show all available test markers
	$(PYTEST) --markers

test-slowest:  ## Show 20 slowest tests
	$(PYTEST) --durations=20

test-benchmark:  ## Run performance benchmark tests
	$(PYTEST) -m benchmark --benchmark-only

# ===================================
# Code Quality - Linting
# ===================================
lint:  ## Run all linters (ruff + mypy)
	@echo "→ Running Ruff linter..."
	@$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	@echo "→ Running MyPy type checker..."
	@$(MYPY) $(SRC_DIR)

lint-fix:  ## Run linters and auto-fix issues
	@echo "→ Running Ruff with auto-fix..."
	@$(RUFF) check --fix $(SRC_DIR) $(TEST_DIR)
	@echo "→ Running MyPy type checker..."
	@$(MYPY) $(SRC_DIR)

ruff-check:  ## Run ruff linter only
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)

ruff-fix:  ## Run ruff and fix auto-fixable issues
	$(RUFF) check --fix $(SRC_DIR) $(TEST_DIR)

mypy:  ## Run mypy type checker only
	$(MYPY) $(SRC_DIR)

# ===================================
# Code Quality - Formatting
# ===================================
format:  ## Format code with Ruff
	$(RUFF) format $(SRC_DIR) $(TEST_DIR)
	$(RUFF) check --fix --select I $(SRC_DIR) $(TEST_DIR)

format-check:  ## Check formatting without changes
	$(RUFF) format --check $(SRC_DIR) $(TEST_DIR)

# ===================================
# Security & Auditing
# ===================================
security:  ## Run security checks (bandit + pip-audit)
	@echo "→ Running Bandit security scanner..."
	@$(BANDIT) -c pyproject.toml -r $(SRC_DIR)
	@echo "→ Running pip-audit for vulnerable dependencies..."
	@$(UV) run pip-audit

security-full:  ## Full security scan (strict mode)
	@echo "→ Running comprehensive security scan..."
	@$(BANDIT) -c pyproject.toml -r $(SRC_DIR) -f json -o bandit-report.json
	@$(BANDIT) -c pyproject.toml -r $(SRC_DIR) -f screen
	@$(UV) run pip-audit --strict
	@$(UV) run safety check --json

audit:  ## Audit dependencies for vulnerabilities
	@echo "→ Auditing dependencies..."
	@$(UV) run pip-audit
	@$(UV) run safety check

# ===================================
# Pre-commit Hooks
# ===================================
pre-commit-install:  ## Install pre-commit hooks
	$(UV) run pre-commit install --install-hooks

pre-commit-run:  ## Run pre-commit on all files
	$(UV) run pre-commit run --all-files

pre-commit-update:  ## Update pre-commit hooks
	$(UV) run pre-commit autoupdate

# ===================================
# Database Management
# ===================================
migrate:  ## Run database migrations (upgrade to head)
	$(ALEMBIC) upgrade head

migrate-create:  ## Create new migration (usage: make migrate-create m="description")
	@if [ -z "$(m)" ]; then \
		echo "❌ Error: Please provide message with m=\"description\""; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(m)"

migrate-downgrade:  ## Rollback last migration
	$(ALEMBIC) downgrade -1

migrate-history:  ## Show migration history
	$(ALEMBIC) history

migrate-current:  ## Show current migration version
	$(ALEMBIC) current

migrate-reset:  ## Reset database (WARNING: destroys all data)
	@echo "⚠️  WARNING: This will destroy all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(ALEMBIC) downgrade base && $(ALEMBIC) upgrade head; \
	fi

db-shell:  ## Open PostgreSQL shell
	docker compose exec db psql -U postgres -d fastapi_db

db-backup:  ## Backup database (usage: make db-backup file=backup.sql)
	@if [ -z "$(file)" ]; then \
		file="backup_$$(date +%Y%m%d_%H%M%S).sql"; \
	fi
	docker compose exec -T db pg_dump -U postgres fastapi_db > $(file)
	@echo "✓ Database backed up to: $(file)"

db-restore:  ## Restore database (usage: make db-restore file=backup.sql)
	@if [ -z "$(file)" ]; then \
		echo "❌ Error: Please provide file=backup.sql"; \
		exit 1; \
	fi
	cat $(file) | docker compose exec -T db psql -U postgres fastapi_db

# ===================================
# Docker Management - Infrastructure
# ===================================
docker-build:  ## Build all Docker images
	docker compose build

docker-build-api:  ## Build API image only
	docker compose build api

docker-build-worker:  ## Build worker image only
	docker compose build worker

docker-up:  ## Start all Docker services (infra + app)
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) up -d

docker-up-infra:  ## Start infrastructure services only (db, redis, temporal, mailpit)
	docker compose --profile $(PROFILE_INFRA) up -d

docker-up-telemetry:  ## Start telemetry stack (jaeger, prometheus, grafana)
	docker compose --profile $(PROFILE_TELEMETRY) up -d

docker-up-all:  ## Start all services including telemetry
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) --profile $(PROFILE_TELEMETRY) up -d

docker-down:  ## Stop all Docker services
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) --profile $(PROFILE_TELEMETRY) down

docker-down-volumes:  ## Stop and remove volumes (WARNING: destroys data)
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) --profile $(PROFILE_TELEMETRY) down -v

docker-restart:  ## Restart all Docker services
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) restart

docker-logs:  ## Show logs from all services
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) logs -f

docker-logs-api:  ## Show API logs only
	docker compose logs -f api

docker-logs-worker:  ## Show worker logs only
	docker compose logs -f worker

docker-ps:  ## Show running containers
	docker compose ps

docker-stats:  ## Show container resource usage
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) stats

docker-clean:  ## Remove stopped containers and unused images
	docker compose --profile $(PROFILE_INFRA) --profile $(PROFILE_APP) --profile $(PROFILE_TELEMETRY) down
	docker system prune -f

# ===================================
# Service Access
# ===================================
redis-cli:  ## Open Redis CLI
	docker compose exec redis redis-cli

redis-monitor:  ## Monitor Redis commands in real-time
	docker compose exec redis redis-cli MONITOR

temporal-ui:  ## Open Temporal Web UI (http://localhost:8080)
	@echo "🌐 Opening Temporal UI at http://localhost:8080"
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:8080 || \
	command -v open >/dev/null 2>&1 && open http://localhost:8080 || \
	echo "Please open http://localhost:8080 in your browser"

jaeger-ui:  ## Open Jaeger tracing UI (http://localhost:16686)
	@echo "🌐 Opening Jaeger UI at http://localhost:16686"
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:16686 || \
	command -v open >/dev/null 2>&1 && open http://localhost:16686 || \
	echo "Please open http://localhost:16686 in your browser"

grafana-ui:  ## Open Grafana UI (http://localhost:3000)
	@echo "🌐 Opening Grafana UI at http://localhost:3000"
	@echo "   Default credentials: admin / admin"
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:3000 || \
	command -v open >/dev/null 2>&1 && open http://localhost:3000 || \
	echo "Please open http://localhost:3000 in your browser"

mailpit-ui:  ## Open Mailpit UI (http://localhost:8025)
	@echo "🌐 Opening Mailpit UI at http://localhost:8025"
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:8025 || \
	command -v open >/dev/null 2>&1 && open http://localhost:8025 || \
	echo "Please open http://localhost:8025 in your browser"

# ===================================
# Cleanup
# ===================================
clean:  ## Clean up generated files and caches
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage 2>/dev/null || true
	@rm -f coverage.xml 2>/dev/null || true
	@rm -f bandit-report.json 2>/dev/null || true
	@echo "✓ Cleanup complete"

clean-all: clean docker-clean  ## Clean everything (files + docker)
	@echo "✓ Full cleanup complete"

# ===================================
# CI/CD Simulation
# ===================================
ci:  ## Run full CI pipeline locally (format + lint + type-check + test + security)
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Running CI Pipeline Locally                               ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "→ Step 1/6: Code formatting check..."
	@$(RUFF) format --check $(SRC_DIR) $(TEST_DIR)
	@echo "✓ Formatting check passed"
	@echo ""
	@echo "→ Step 2/6: Import sorting check..."
	@$(RUFF) check --select I $(SRC_DIR) $(TEST_DIR)
	@echo "✓ Import sorting passed"
	@echo ""
	@echo "→ Step 3/6: Linting..."
	@$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	@echo "✓ Linting passed"
	@echo ""
	@echo "→ Step 4/6: Type checking..."
	@$(MYPY) $(SRC_DIR)
	@echo "✓ Type checking passed"
	@echo ""
	@echo "→ Step 5/6: Running tests..."
	@$(PYTEST) --tb=short
	@echo "✓ All tests passed"
	@echo ""
	@echo "→ Step 6/6: Security scan..."
	@$(BANDIT) -c pyproject.toml -r $(SRC_DIR) -q
	@echo "✓ Security scan passed"
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  ✓ CI Pipeline Complete - All Checks Passed               ║"
	@echo "╚════════════════════════════════════════════════════════════╝"

ci-fast:  ## Run fast CI checks (no tests, no security)
	@echo "→ Fast CI checks..."
	@$(RUFF) format --check $(SRC_DIR) $(TEST_DIR)
	@$(RUFF) check $(SRC_DIR) $(TEST_DIR)
	@$(MYPY) $(SRC_DIR)
	@echo "✓ Fast CI checks passed"

# ===================================
# Validation & Project Info
# ===================================
validate:  ## Validate project structure and configuration
	@bash scripts/validate.sh

info:  ## Show project information and statistics
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  Python FastAPI Boilerplate - Project Info                ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📦 Versions:"
	@echo "  Python:      $$(python --version 2>&1 | cut -d' ' -f2)"
	@echo "  UV:          $$(uv --version 2>&1 | cut -d' ' -f2)"
	@echo "  Project:     $$(grep '^version' pyproject.toml | cut -d'"' -f2)"
	@echo ""
	@echo "📊 Code Statistics:"
	@echo "  Python files:       $$(find $(SRC_DIR) $(TEST_DIR) -name '*.py' 2>/dev/null | wc -l | xargs)"
	@echo "  Source files:       $$(find $(SRC_DIR) -name '*.py' 2>/dev/null | wc -l | xargs)"
	@echo "  Test files:         $$(find $(TEST_DIR) -name 'test_*.py' 2>/dev/null | wc -l | xargs)"
	@echo "  Lines of code:      $$(find $(SRC_DIR) -name '*.py' -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $$1}')"
	@echo ""
	@echo "🏗️  Architecture:"
	@echo "  Domain models:      $$(find $(SRC_DIR)/domain/models -name '*.py' ! -name '__init__.py' 2>/dev/null | wc -l | xargs)"
	@echo "  Use cases:          $$(find $(SRC_DIR)/app/usecases -name '*.py' ! -name '__init__.py' 2>/dev/null | wc -l | xargs)"
	@echo "  Repositories:       $$(find $(SRC_DIR)/infrastructure/repositories -name '*_repository.py' 2>/dev/null | wc -l | xargs)"
	@echo "  API endpoints:      $$(find $(SRC_DIR)/presentation/api -name '*.py' ! -name '__init__.py' 2>/dev/null | wc -l | xargs)"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  Markdown files:     $$(find $(DOCS_DIR) -name '*.md' 2>/dev/null | wc -l | xargs)"
	@echo ""

deps-tree:  ## Show dependency tree
	$(UV) tree

deps-outdated:  ## Check for outdated dependencies
	$(UV) pip list --outdated

# ===================================
# Documentation
# ===================================
docs-serve:  ## Serve documentation locally (requires mkdocs)
	$(UV) run mkdocs serve

docs-build:  ## Build documentation (requires mkdocs)
	$(UV) run mkdocs build

docs-deploy:  ## Deploy documentation to GitHub Pages (requires mkdocs)
	$(UV) run mkdocs gh-deploy

# ===================================
# Quick Shortcuts
# ===================================
up: docker-up-infra  ## Quick: Start infrastructure
down: docker-down    ## Quick: Stop all services
restart: docker-restart  ## Quick: Restart services
logs: docker-logs    ## Quick: Show logs
check: lint test     ## Quick: Run linting and tests
fix: format lint-fix ## Quick: Format and fix linting issues
