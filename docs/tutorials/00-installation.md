# Tutorial: Complete Installation Guide

> **Learn how to set up the FastAPI boilerplate from scratch**

**Time:** 15 minutes
**Difficulty:** Beginner
**Prerequisites:** Basic command line knowledge

## What You'll Learn

By the end of this tutorial, you will:
- Install all required dependencies
- Set up the development environment
- Start all infrastructure services
- Run your first API request
- Understand the project structure

## Step 1: Install Prerequisites

### Python 3.12+

**macOS:**
```bash
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and run the installer.

**Verify installation:**
```bash
python3.12 --version
# Should output: Python 3.12.x
```

### Docker Desktop

Download and install Docker Desktop:
- **macOS/Windows:** [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux:** [Docker Engine](https://docs.docker.com/engine/install/)

**Verify installation:**
```bash
docker --version
docker-compose --version
```

### Git

**macOS:**
```bash
brew install git
```

**Ubuntu/Debian:**
```bash
sudo apt install git
```

**Windows:**
Download from [git-scm.com](https://git-scm.com/download/win)

**Verify installation:**
```bash
git --version
```

## Step 2: Clone the Repository

```bash
# Clone to your local machine
git clone https://github.com/thaithienvanid/python-fast-forge.git

# Navigate into the directory
cd python-fast-forge

# Verify you're in the right place
ls -la
# Should see: README.md, src/, tests/, docker-compose.yml, etc.
```

## Step 3: Install UV Package Manager

UV is a blazingly fast Python package manager (10-100x faster than pip).

```bash
# Install UV globally
pip install uv

# Verify installation
uv --version
```

**Why UV?**
- 10-100x faster than pip
- Better dependency resolution
- Built-in virtual environment management
- Deterministic installs with uv.lock

## Step 4: Install Python Dependencies

```bash
# Install all dependencies (runtime, dev, test, security)
uv sync --all-groups

# This creates a virtual environment and installs:
# - Runtime dependencies (FastAPI, SQLAlchemy, etc.)
# - Development tools (Ruff, MyPy, pre-commit)
# - Testing tools (Pytest, coverage, etc.)
# - Security tools (Bandit, Safety, etc.)
```

**What gets installed:**
- **Runtime:** FastAPI, SQLAlchemy, Pydantic, Redis, Temporal
- **Development:** Ruff (linter), MyPy (type checker), pre-commit
- **Testing:** Pytest, coverage, hypothesis, pytest-asyncio
- **Security:** Bandit, safety checks

**Verify installation:**
```bash
# Check Python packages
uv pip list | head -20

# Test that FastAPI is installed
uv run python -c "import fastapi; print(fastapi.__version__)"
```

## Step 5: Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# View the file (optional)
cat .env
```

**What's in `.env`:**
```bash
# Database configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db

# Redis configuration
REDIS_URL=redis://localhost:6379/0

# API configuration
API_V1_PREFIX=/api/v1
DEBUG=true
LOG_LEVEL=INFO

# Security (change in production!)
SECRET_KEY=your-secret-key-here

# Temporal workflow configuration
TEMPORAL_HOST=localhost:7233
```

**Important:** For production, you **must** change `SECRET_KEY` and other sensitive values.

## Step 6: Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, Temporal, and Mailpit
docker-compose --profile infra up -d

# Verify services are running
docker-compose ps
```

**Expected output:**
```
NAME                    STATUS    PORTS
postgres                Up        0.0.0.0:5432->5432/tcp
redis                   Up        0.0.0.0:6379->6379/tcp
temporal                Up        0.0.0.0:7233->7233/tcp
temporal-ui             Up        0.0.0.0:8080->8080/tcp
mailpit                 Up        0.0.0.0:8025->8025/tcp
```

**What each service does:**
- **PostgreSQL**: Primary database for storing data
- **Redis**: Cache and rate limiting
- **Temporal**: Workflow orchestration for background jobs
- **Temporal UI**: Web interface for monitoring workflows
- **Mailpit**: Email testing (catches all emails in dev)

## Step 7: Run Database Migrations

```bash
# Apply all migrations to create database schema
make migrate

# Expected output:
# Migrating to version 20251111120000 (1 migration)
#   -- ok (10.5ms)
```

**What this does:**
- Creates all database tables
- Sets up indexes and constraints
- Applies schema from SQLAlchemy models

**Verify database setup:**
```bash
# Connect to PostgreSQL (password: postgres)
docker exec -it postgres psql -U postgres -d fastapi_db

# Inside psql, list tables
\dt

# You should see tables like:
# - users
# - atlas_schema_revisions
# Exit with: \q
```

## Step 8: Start the API Server

```bash
# Start the FastAPI server
uv run python main.py

# Expected output:
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**What's happening:**
- FastAPI starts with Uvicorn (ASGI server)
- Auto-reload is enabled (code changes trigger restart)
- API is available on port 8000
- OpenAPI docs generated automatically

## Step 9: Test Your Installation

**Open your browser and visit:**
- **API Root**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

**Or use curl:**
```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0"}

# Test API root
curl http://localhost:8000/

# Expected response:
# {"message":"Welcome to FastAPI Boilerplate","version":"0.1.0"}
```

## Step 10: (Optional) Start Temporal Worker

For background jobs, start the Temporal worker in a **separate terminal**:

```bash
# In a new terminal, navigate to project directory
cd python-fast-forge

# Start the worker
uv run python worker.py

# Expected output:
# INFO: Worker started successfully
# INFO: Listening for tasks on task queue: default
```

## Verify Complete Setup

Run this verification script:

```bash
# Create a test user
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "username": "alice",
    "full_name": "Alice Smith"
  }'

# Expected response (status 201):
# {
#   "id": "01234567-89ab-cdef-0123-456789abcdef",
#   "email": "alice@example.com",
#   "username": "alice",
#   "full_name": "Alice Smith",
#   "is_active": true,
#   "created_at": "2024-01-01T12:00:00Z"
# }

# List users
curl http://localhost:8000/api/v1/users

# Expected response:
# {
#   "items": [{"id": "...", "email": "alice@example.com", ...}],
#   "cursor": null
# }
```

## View Additional Services

Open these URLs in your browser:

| Service | URL | Description |
|---------|-----|-------------|
| **Mailpit** | http://localhost:8025 | View emails sent by the app |
| **Temporal UI** | http://localhost:8080 | Monitor background workflows |
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |

## Project Structure Overview

Now that everything is running, let's understand the structure:

```
python-fast-forge/
├── src/                    # All source code
│   ├── domain/            # Business entities and rules
│   ├── app/               # Use cases and application logic
│   ├── infrastructure/    # Database, cache, external services
│   ├── presentation/      # API routes and schemas
│   └── container.py       # Dependency injection setup
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── migrations/           # Database migrations (SQL)
├── docs/                 # Documentation
├── main.py               # API entry point
├── worker.py             # Temporal worker entry point
└── docker-compose.yml    # Dev environment setup
```

## Development Workflow

Now you're ready to develop! Here's the typical workflow:

```bash
# 1. Make code changes in src/

# 2. API auto-reloads (watch terminal for restart)

# 3. Test your changes
curl http://localhost:8000/your-new-endpoint

# 4. Run tests
uv run pytest

# 5. Check code quality
uv run ruff check .
uv run mypy src/
```

## Troubleshooting

### Port Already in Use

**Problem:** `Address already in use: 0.0.0.0:8000`

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux

# Kill the process
kill -9 <PID>

# Or use a different port
PORT=8001 uv run python main.py
```

### Database Connection Failed

**Problem:** `Connection refused` when connecting to database

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# If not running, start it
docker-compose --profile infra up -d

# Wait 10 seconds for startup
sleep 10

# Try again
make migrate
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Reinstall dependencies
uv sync --all-groups

# Verify you're in project root
pwd  # Should show: .../python-fast-forge
```

### Docker Issues

**Problem:** `Cannot connect to Docker daemon`

**Solution:**
```bash
# Start Docker Desktop (macOS/Windows)
# Or start Docker service (Linux)
sudo systemctl start docker

# Verify Docker is running
docker ps
```

## Next Steps

Congratulations! You have a fully working FastAPI application.

**Continue learning:**
1. **[Build Your First API Endpoint](./01-first-api.md)** - Add a new endpoint
2. **[Add a Database Model](./02-database-model.md)** - Create a new entity
3. **[Add Background Jobs](./03-background-jobs.md)** - Use Temporal workflows

**Reference documentation:**
- [Architecture Overview](../reference/architecture.md)
- [API Reference](../reference/api.md)
- [Configuration Guide](../reference/configuration.md)

## Summary

You've successfully:
- ✅ Installed Python 3.12+, Docker, and Git
- ✅ Cloned the repository
- ✅ Installed UV and all Python dependencies
- ✅ Configured environment variables
- ✅ Started PostgreSQL, Redis, Temporal, and Mailpit
- ✅ Ran database migrations
- ✅ Started the API server
- ✅ Tested the installation
- ✅ (Optional) Started Temporal worker

**Your development environment is ready!** 🎉
