# Debugging Guide

Learn how to debug common issues in your FastAPI application.

## Prerequisites

- Application running in development mode
- Basic understanding of Python debugging
- Familiarity with logging and observability tools

## Quick Reference

| Issue Type | Tool | Command |
|------------|------|---------|
| API errors | Logs | `docker compose logs -f api` |
| Database issues | PostgreSQL logs | `docker compose logs -f postgres` |
| Background jobs | Temporal UI | http://localhost:8233 |
| Email issues | Mailpit | http://localhost:8025 |
| Performance | OpenTelemetry | Check spans in logs |

---

## 1. Debug API Endpoint Issues

### Enable Debug Mode

Ensure development mode is enabled in `.env`:

```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

Restart services:

```bash
docker compose restart api
```

### View Real-Time Logs

```bash
# Follow all API logs
docker compose logs -f api

# Filter by log level
docker compose logs -f api | grep ERROR

# Filter by request ID
docker compose logs -f api | grep "request_id=abc123"
```

### Add Debug Logging

Add temporary debug statements in your code:

```python
# src/app/usecases/user_usecases.py
import structlog

logger = structlog.get_logger()

class GetUserUseCase:
    async def execute(self, user_id: str, tenant_id: str) -> User:
        logger.debug(
            "get_user_usecase.start",
            user_id=user_id,
            tenant_id=tenant_id
        )

        user = await self.repository.get_by_id(user_id, tenant_id)

        logger.debug(
            "get_user_usecase.complete",
            user_found=user is not None
        )

        return user
```

### Use Python Debugger (pdb)

Add breakpoint in code:

```python
# src/app/usecases/user_usecases.py
async def execute(self, user_id: str, tenant_id: str) -> User:
    import pdb; pdb.set_trace()  # Breakpoint here
    user = await self.repository.get_by_id(user_id, tenant_id)
    return user
```

Attach to running container:

```bash
docker compose exec api bash
```

---

## 2. Debug Database Issues

### Check Database Connection

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres -d app_db

# List all tables
\dt

# Check specific table
SELECT * FROM users LIMIT 5;

# Check tenant data
SELECT * FROM users WHERE tenant_id = 'tenant_123';
```

### View Database Logs

```bash
# Follow PostgreSQL logs
docker compose logs -f postgres

# Check for connection errors
docker compose logs postgres | grep ERROR
```

### Debug Query Performance

Enable query logging in SQLAlchemy:

```python
# src/app/core/database.py
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Enable SQL query logging
    pool_pre_ping=True,
)
```

View queries in logs:

```bash
docker compose logs -f api | grep "SELECT"
```

### Common Database Issues

**Issue: "relation does not exist"**

Solution: Run migrations

```bash
make migrate
```

**Issue: "connection refused"**

Solution: Check database is running

```bash
docker compose ps postgres
docker compose up -d postgres
```

**Issue: "duplicate key value"**

Solution: Check for unique constraint violations

```sql
-- Find duplicate emails
SELECT email, COUNT(*)
FROM users
GROUP BY email
HAVING COUNT(*) > 1;
```

---

## 3. Debug Background Jobs (Temporal)

### Access Temporal UI

Open http://localhost:8233 in your browser.

### View Workflow Execution

1. Navigate to "Workflows" tab
2. Search by workflow ID or type
3. Click workflow to see execution history
4. Check "Event History" for details

### Debug Workflow Code

Add logging to workflows:

```python
# src/app/workflows/user_workflows.py
import structlog

logger = structlog.get_logger()

@workflow.defn
class UserWorkflow:
    @workflow.run
    async def run(self, user_id: str) -> dict:
        logger.info("workflow.start", user_id=user_id)

        try:
            result = await workflow.execute_activity(
                process_user,
                user_id,
                start_to_close_timeout=timedelta(minutes=5),
            )
            logger.info("workflow.success", result=result)
            return result
        except Exception as e:
            logger.error("workflow.error", error=str(e))
            raise
```

### View Temporal Worker Logs

```bash
# Follow worker logs (if using separate worker container)
docker compose logs -f temporal-worker

# Or follow main API logs (worker runs in API container)
docker compose logs -f api | grep "workflow"
```

### Common Temporal Issues

**Issue: "workflow not found"**

Solution: Ensure Temporal service is running

```bash
docker compose ps temporal
docker compose up -d temporal
```

**Issue: "activity timeout"**

Solution: Increase timeout in workflow definition

```python
result = await workflow.execute_activity(
    long_running_activity,
    start_to_close_timeout=timedelta(minutes=10),  # Increase timeout
)
```

---

## 4. Debug Multi-Tenancy Issues

### Check Tenant Isolation

Verify tenant_id is present:

```python
# Add logging to repository
class UserRepository:
    async def get_by_id(self, user_id: str, tenant_id: str) -> User:
        logger.debug("repository.get_by_id",
                    user_id=user_id,
                    tenant_id=tenant_id)
        # Query includes tenant_id filter
        query = select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id
        )
```

### Test Tenant Isolation

```bash
# Create users in different tenants (using JWT tokens)
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJ0ZW5hbnRfMSJ9.signature" \
  -d '{"email": "user1@tenant1.com", "username": "user1"}'

curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJ0ZW5hbnRfMiJ9.signature" \
  -d '{"email": "user1@tenant2.com", "username": "user1"}'

# Verify isolation - should only see tenant_1 users
curl -X GET http://localhost:8000/api/v1/users \
  -H "X-Tenant-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJ0ZW5hbnRfMSJ9.signature"
```

### Debug Missing Tenant ID

Check middleware is applying tenant_id:

```bash
# View logs for tenant_id extraction
docker compose logs -f api | grep "tenant_id"
```

---

## 5. Debug Performance Issues

### Enable OpenTelemetry Tracing

Already enabled by default. View traces in logs:

```bash
docker compose logs -f api | grep "trace_id"
```

### Identify Slow Endpoints

Add timing logs:

```python
import time

@router.get("/users")
async def list_users():
    start_time = time.time()

    users = await use_case.execute()

    duration = time.time() - start_time
    logger.info("endpoint.duration",
               endpoint="/users",
               duration_seconds=duration)

    return users
```

### Profile Database Queries

Use SQLAlchemy query profiling:

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - conn.info['query_start_time'].pop(-1)
    logger.info("query.duration", duration=total_time, query=statement[:100])
```

### Check Connection Pool

Monitor database connection pool:

```python
# View pool status
from src.app.core.database import engine

print(f"Pool size: {engine.pool.size()}")
print(f"Checked out: {engine.pool.checkedout()}")
```

---

## 6. Debug Authentication Issues

### Test JWT Token

```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}' \
  | jq -r '.access_token')

# Use token
curl -X GET http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN"
```

### Decode JWT Token

Visit https://jwt.io and paste your token to inspect claims.

### Check Token Expiration

```python
import jwt
from datetime import datetime

token = "your.jwt.token.here"
decoded = jwt.decode(token, options={"verify_signature": False})
exp_timestamp = decoded['exp']
exp_datetime = datetime.fromtimestamp(exp_timestamp)

print(f"Token expires at: {exp_datetime}")
print(f"Is expired: {datetime.now() > exp_datetime}")
```

---

## 7. Debug Email Issues

### Access Mailpit UI

Open http://localhost:8025 in your browser to see all captured emails.

### Test Email Sending

```python
# Trigger email from code
from src.app.services.email_service import send_email

await send_email(
    to="test@example.com",
    subject="Test Email",
    body="This is a test email"
)
```

Check Mailpit UI for the email.

### View Email Logs

```bash
docker compose logs -f mailpit
```

---

## 8. Common Error Messages

### "Tenant ID is required"

**Cause:** Missing `X-Tenant-Token` header

**Solution:** Add JWT token header to request

```bash
curl -X GET http://localhost:8000/api/v1/users \
  -H "X-Tenant-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJ5b3VyLXRlbmFudC1pZCJ9.signature"
```

### "User not found"

**Cause:** User doesn't exist or wrong tenant

**Solution:**
1. Check user exists: `SELECT * FROM users WHERE id = 'user_id'`
2. Verify tenant_id matches: Check `tenant_id` column
3. Check logs for tenant isolation

### "Database connection failed"

**Cause:** PostgreSQL not running or wrong credentials

**Solution:**
```bash
# Check database is running
docker compose ps postgres

# Restart database
docker compose restart postgres

# Check credentials in .env
cat .env | grep DATABASE
```

### "Migration failed"

**Cause:** Database schema mismatch

**Solution:**
```bash
# View migration status
docker compose exec db psql -U forge_user -d forge_db -c "SELECT version, executed_at FROM atlas_schema_revisions ORDER BY executed_at DESC LIMIT 5;"

# View pending migrations
atlas migrate status --env local

# Run migrations
make migrate

# Rollback if needed
atlas migrate down --env local
```

---

## 9. Debugging Best Practices

### DO ✅

- Use structured logging (structlog) for searchable logs
- Include request_id in all logs for tracing
- Add temporary debug logs, remove before commit
- Use descriptive error messages
- Test with different tenant IDs
- Check logs before asking for help

### DON'T ❌

- Don't log sensitive data (passwords, tokens)
- Don't leave debug statements in production
- Don't ignore error logs
- Don't skip writing tests
- Don't debug in production

---

## 10. Getting Help

### Check Logs First

Always start by checking logs:

```bash
# API logs
docker compose logs -f api

# All services
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100
```

### Reproduce the Issue

Create a minimal test case:

```python
# tests/debug/test_reproduce_issue.py
def test_reproduce_bug():
    # Minimal code to reproduce the issue
    pass
```

### Gather Information

Include in bug reports:
1. Error message and stack trace
2. Steps to reproduce
3. Expected vs actual behavior
4. Environment (dev/staging/prod)
5. Relevant log entries
6. Request/response examples

---

## Next Steps

- Learn about [Testing](../reference/testing.md)
- Review [Architecture](../reference/architecture.md)
- Check [Configuration Reference](../reference/configuration.md)
- Read [Adding Endpoints](add-endpoint.md)
