# Getting Started

> **Get your FastAPI application running in 5 minutes**

This guide will help you set up and run the FastAPI boilerplate quickly. For more detailed tutorials, see [docs/tutorials/](./docs/tutorials/).

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.12 or higher** - [Download](https://www.python.org/downloads/)
- **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop)
- **Git** - [Download](https://git-scm.com/downloads)

**Verify installations:**
```bash
python --version  # Should be 3.12+
docker --version  # Any recent version
git --version     # Any recent version
```

## ⚡ Quick Start (5 Minutes)

### Step 1: Clone & Install (2 min)

```bash
# Clone the repository
git clone https://github.com/thaithienvanid/python-fast-forge.git
cd python-fast-forge

# Install UV (10-100x faster than pip)
pip install uv

# Install all dependencies
uv sync --all-groups
```

**What this does:**
- Clones the repository to your machine
- Installs UV, a fast Python package manager
- Installs all dependencies (runtime, dev, test, security tools)

### Step 2: Configure Environment (30 sec)

```bash
# Copy example environment file
cp .env.example .env

# (Optional) Edit .env if needed
# nano .env  # or use your preferred editor
```

**What's in `.env`:**
- Database connection settings
- Redis configuration
- API keys (for development)
- Feature flags

### Step 3: Start Services (1 min)

```bash
# Start infrastructure services
docker-compose --profile infra up -d

# Wait ~10 seconds for services to start
sleep 10

# Run database migrations
uv run alembic upgrade head
```

**Services started:**
- PostgreSQL (database) on port 5432
- Redis (cache) on port 6379
- Temporal (workflows) on port 7233
- Mailpit (email testing) on port 8025

### Step 4: Run the API (30 sec)

```bash
# Start the API server
uv run python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 5: Test It! (1 min)

**In your browser, visit:**
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

**Or use curl:**
```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"0.1.0"}

# List users (will be empty initially)
curl http://localhost:8000/api/v1/users

# Create a user
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "username": "alice",
    "full_name": "Alice Smith"
  }'
```

## 🎉 Success!

You now have a running FastAPI application with:
- ✅ REST API with auto-generated docs
- ✅ PostgreSQL database
- ✅ Redis caching
- ✅ Temporal workflows
- ✅ Email testing (Mailpit)

## 🚀 Next Steps

### Explore the API

1. **Open Swagger UI**: http://localhost:8000/docs
2. **Try the endpoints**:
   - `GET /health` - Health check
   - `GET /api/v1/users` - List users
   - `POST /api/v1/users` - Create user
   - `GET /api/v1/users/{id}` - Get user by ID

### View Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **API Docs** | http://localhost:8000/docs | None |
| **Mailpit** | http://localhost:8025 | None |
| **Temporal UI** | http://localhost:8080 | None |
| **PostgreSQL** | localhost:5432 | user: `postgres`, pass: `postgres`, db: `fastapi_db` |
| **Redis** | localhost:6379 | No password (dev mode) |

### Learn More

- **[Build Your First Endpoint](./docs/tutorials/01-first-api.md)** - Add a new API endpoint
- **[Add Database Model](./docs/tutorials/02-database-model.md)** - Create a new entity
- **[Background Jobs](./docs/tutorials/03-background-jobs.md)** - Add async tasks
- **[Architecture Guide](./docs/reference/architecture.md)** - Understand the structure

## 🔧 Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest tests/unit/test_user_model.py
```

### Code Quality

```bash
# Install pre-commit hooks (runs on git commit)
uv run pre-commit install

# Run linting
make lint

# Run type checking
make type-check

# Format code
make format
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "Add user table"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

## 🐛 Troubleshooting

### Port Already in Use

**Problem:** `Address already in use: 0.0.0.0:8000`

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or use a different port
PORT=8001 uv run python main.py
```

### Database Connection Failed

**Problem:** `Connection refused` or `could not connect to server`

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# If not running, start it
docker-compose --profile infra up -d

# Wait 10 seconds and try again
sleep 10
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Reinstall dependencies
uv sync --all-groups

# Ensure you're in the project root
pwd  # Should show .../python-fast-forge
```

### Tests Failing

**Problem:** Tests fail with database errors

**Solution:**
```bash
# Ensure test database is running
docker-compose --profile infra up -d

# Run migrations
uv run alembic upgrade head

# Clear test cache and rerun
rm -rf .pytest_cache
make test
```

## 🛑 Stopping Services

```bash
# Stop the API (Ctrl+C in the terminal running it)

# Stop Docker services
docker-compose --profile infra down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose --profile infra down -v
```

## 📚 Additional Resources

- **[Full Installation Guide](./docs/tutorials/00-installation.md)** - Detailed setup
- **[How-To Guides](./docs/how-to/)** - Common tasks
- **[API Reference](./docs/reference/api.md)** - All endpoints
- **[Architecture](./docs/reference/architecture.md)** - System design
- **[Contributing](./CONTRIBUTING.md)** - How to contribute

## 💡 Tips

1. **Use Makefile commands**: Run `make help` to see all available commands
2. **Enable auto-reload**: API automatically reloads when you edit code
3. **Check logs**: Use `docker-compose logs -f` to view service logs
4. **Database GUI**: Connect with tools like DBeaver, pgAdmin, or TablePlus

## ❓ Need Help?

- **Documentation**: [Full docs](./docs/)
- **Issues**: [GitHub Issues](https://github.com/thaithienvanid/python-fast-forge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thaithienvanid/python-fast-forge/discussions)

---

**Ready to build?** → [Build Your First API](./docs/tutorials/01-first-api.md)
