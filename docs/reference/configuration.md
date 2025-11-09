# Configuration Reference

Complete reference for all environment variables and configuration options.

## Configuration File

Configuration is managed via environment variables. Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

## Application Settings

### APP_NAME
- **Type:** String
- **Default:** `python-fast-forge`
- **Description:** Application name used in logs and monitoring
- **Example:** `my-awesome-api`

### APP_VERSION
- **Type:** String (Semantic Versioning)
- **Default:** `0.1.0`
- **Description:** Application version for API docs and monitoring
- **Example:** `1.2.3`

### APP_ENV
- **Type:** Enum (`development` | `staging` | `production`)
- **Default:** `development`
- **Description:** Environment name affects logging, error handling
- **Production:** Set to `production` for production deployments

### DEBUG
- **Type:** Boolean
- **Default:** `True`
- **Description:** Enable debug mode (detailed errors, auto-reload)
- **Production:** **MUST** be `False` in production (security risk)

### LOG_LEVEL
- **Type:** Enum (`DEBUG` | `INFO` | `WARNING` | `ERROR` | `CRITICAL`)
- **Default:** `INFO`
- **Description:** Minimum log level to output
- **Development:** `DEBUG` for verbose logging
- **Production:** `INFO` or `WARNING`

##Server Settings

### HOST
- **Type:** IP Address
- **Default:** `0.0.0.0`
- **Description:** Host to bind the server
- **Note:** `0.0.0.0` allows external connections (required for Docker)

### PORT
- **Type:** Integer (1-65535)
- **Default:** `8000`
- **Description:** Port to bind the server
- **Example:** `8080`, `3000`

### WORKERS
- **Type:** Integer (1+)
- **Default:** `1`
- **Description:** Number of worker processes (Uvicorn)
- **Production:** Set to `(2 × CPU cores) + 1`
- **Example:** For 4 cores: `9` workers

### RELOAD
- **Type:** Boolean
- **Default:** `True`
- **Description:** Auto-reload on code changes (Uvicorn)
- **Production:** **MUST** be `False` (performance impact)

## Database Settings

### DATABASE_URL
- **Type:** Connection String
- **Default:** `postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db`
- **Format:** `postgresql+asyncpg://user:password@host:port/database`
- **Description:** PostgreSQL connection string with async driver
- **Production Example:**
  ```
  postgresql+asyncpg://prod_user:secure_password@db.example.com:5432/production_db
  ```
- **Note:** Use `asyncpg` driver for async support

### DATABASE_ECHO
- **Type:** Boolean
- **Default:** `False`
- **Description:** Log all SQL statements (SQLAlchemy)
- **Development:** `True` for debugging queries
- **Production:** `False` (performance and security)

### DATABASE_POOL_SIZE
- **Type:** Integer (1+)
- **Default:** `5`
- **Description:** Number of connections in the connection pool
- **Production:** Increase based on load (e.g., `20`)

### DATABASE_MAX_OVERFLOW
- **Type:** Integer (0+)
- **Default:** `10`
- **Description:** Max connections beyond pool_size
- **Total connections:** `POOL_SIZE + MAX_OVERFLOW`

## CORS Settings

### CORS_ORIGINS
- **Type:** JSON Array of URLs
- **Default:** `["http://localhost:3000","http://localhost:8000"]`
- **Description:** Allowed origins for CORS requests
- **Production Example:**
  ```json
  ["https://app.example.com","https://admin.example.com"]
  ```
- **Security:** Never use `["*"]` in production

### CORS_ALLOW_CREDENTIALS
- **Type:** Boolean
- **Default:** `True`
- **Description:** Allow cookies/auth headers in CORS requests
- **Note:** Required if using authentication with CORS

### CORS_ALLOW_METHODS
- **Type:** JSON Array
- **Default:** `["*"]`
- **Description:** Allowed HTTP methods
- **Production:** Restrict to needed methods: `["GET","POST","PUT","DELETE"]`

### CORS_ALLOW_HEADERS
- **Type:** JSON Array
- **Default:** `["*"]`
- **Description:** Allowed request headers
- **Production:** Restrict to needed headers: `["Content-Type","Authorization","X-Tenant-Token"]`

## Rate Limiting

### RATE_LIMIT_ENABLED
- **Type:** Boolean
- **Default:** `True`
- **Description:** Enable rate limiting middleware
- **Production:** `True` (protect against abuse)

### RATE_LIMIT_PER_MINUTE
- **Type:** Integer (1+)
- **Default:** `60`
- **Description:** Max requests per minute per IP
- **Example:** `100` for higher limits, `10` for stricter limits

## Security Settings

### SECRET_KEY
- **Type:** String (32+ characters)
- **Default:** `None`
- **Description:** Secret key for API signature authentication (X-API-Signature header validation)
- **Production:** **MUST** set to random string if using API signature authentication
- **Generate:**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **⚠️ CRITICAL:** Never commit to Git. Use secrets manager.
- **Note:** Not used for JWT tokens - see JWT_PRIVATE_KEY/JWT_PUBLIC_KEY below

### JWT_ALGORITHM
- **Type:** String
- **Default:** `ES256`
- **Description:** JWT signing algorithm for X-Tenant-Token
- **Options:** `ES256`, `ES384`, `ES512` (Elliptic Curve), `HS256`, `HS384`, `HS512` (HMAC)
- **Recommended:** `ES256` for production (asymmetric cryptography)

### JWT_PRIVATE_KEY
- **Type:** String (base64-encoded PEM)
- **Default:** `None`
- **Description:** EC private key in base64-encoded PEM format for JWT signing
- **Production:** Required for ES256 algorithm
- **Generate:**
  ```bash
  # Generate EC private key
  openssl ecparam -genkey -name prime256v1 -noout -out private_key.pem
  # Encode to base64
  base64 -w 0 private_key.pem
  ```

### JWT_PRIVATE_KEY_PATH
- **Type:** String (file path)
- **Default:** `None`
- **Description:** Path to EC private key file (PEM format) for JWT signing
- **Alternative:** Use JWT_PRIVATE_KEY (base64) instead of file path
- **Development:** Auto-generates ephemeral key if not provided

### JWT_PUBLIC_KEY
- **Type:** String (base64-encoded PEM)
- **Default:** `None`
- **Description:** EC public key in base64-encoded PEM format for JWT verification
- **Note:** Can be derived from private key if not provided

### JWT_PUBLIC_KEY_PATH
- **Type:** String (file path)
- **Default:** `None`
- **Description:** Path to EC public key file (PEM format) for JWT verification
- **Alternative:** Use JWT_PUBLIC_KEY (base64) instead of file path

### ACCESS_TOKEN_EXPIRE_MINUTES
- **Type:** Integer (1+)
- **Default:** `30`
- **Description:** JWT token expiration time in minutes (for X-Tenant-Token)
- **Short-lived:** `15` minutes (more secure)
- **Long-lived:** `1440` (24 hours)
- **Note:** Shorter expiration = better security, more frequent token refreshes

## API Settings

### API_V1_PREFIX
- **Type:** String (path)
- **Default:** `/api/v1`
- **Description:** Prefix for API v1 endpoints
- **Example:** All endpoints: `/api/v1/users`, `/api/v1/tasks`

### DOCS_URL
- **Type:** String (path) or `None`
- **Default:** `/docs`
- **Description:** Swagger UI documentation URL
- **Production:** Set to `None` to disable public docs
- **Example:** `/api/docs` or `None`

### REDOC_URL
- **Type:** String (path) or `None`
- **Default:** `/redoc`
- **Description:** ReDoc documentation URL
- **Production:** Set to `None` to disable

### OPENAPI_URL
- **Type:** String (path) or `None`
- **Default:** `/openapi.json`
- **Description:** OpenAPI schema JSON endpoint
- **Production:** Set to `None` to disable schema exposure

## OpenTelemetry (Observability)

### OTEL_ENABLED
- **Type:** Boolean
- **Default:** `True`
- **Description:** Enable OpenTelemetry tracing
- **Production:** `True` for monitoring

### OTEL_SERVICE_NAME
- **Type:** String
- **Default:** `fastapi-boilerplate`
- **Description:** Service name in traces
- **Example:** `user-service`, `api-gateway`

### OTEL_EXPORTER_OTLP_ENDPOINT
- **Type:** URL
- **Default:** `http://localhost:4317`
- **Description:** OTLP collector endpoint (gRPC)
- **Production Example:** `https://otel-collector.example.com:4317`
- **Note:** Use gRPC endpoint (port 4317), not HTTP (4318)

### OTEL_EXPORTER_OTLP_INSECURE
- **Type:** Boolean
- **Default:** `True`
- **Description:** Use insecure gRPC connection (no TLS)
- **Production:** `False` (use TLS)

### OTEL_TRACE_SAMPLE_RATE
- **Type:** Float (0.0-1.0)
- **Default:** `1.0`
- **Description:** Fraction of traces to sample
- **Development:** `1.0` (100% of traces)
- **Production:** `0.1` (10% of traces) for high-traffic apps

## Redis (Caching)

### REDIS_URL
- **Type:** Connection String
- **Default:** `redis://localhost:6379/0`
- **Format:** `redis://[user:password@]host:port/database`
- **Description:** Redis connection URL
- **Production Example:**
  ```
  redis://:secure_password@redis.example.com:6379/0
  ```
- **With TLS:**
  ```
  rediss://:password@redis.example.com:6380/0
  ```

### REDIS_MAX_CONNECTIONS
- **Type:** Integer (1+)
- **Default:** `10`
- **Description:** Max connections in Redis connection pool
- **Production:** Increase based on load (e.g., `50`)

## Cache Settings

### CACHE_ENABLED
- **Type:** Boolean
- **Default:** `True`
- **Description:** Enable Redis caching for repositories
- **Production:** `True` (improves performance)

### CACHE_TTL
- **Type:** Integer (seconds)
- **Default:** `300` (5 minutes)
- **Description:** Default cache time-to-live
- **Short TTL:** `60` (1 minute) for frequently changing data
- **Long TTL:** `3600` (1 hour) for static data

## Temporal (Background Jobs)

### TEMPORAL_HOST
- **Type:** Host:Port
- **Default:** `localhost:7233`
- **Description:** Temporal server address
- **Production Example:** `temporal.example.com:7233`

### TEMPORAL_NAMESPACE
- **Type:** String
- **Default:** `default`
- **Description:** Temporal namespace (tenant isolation)
- **Production:** Use separate namespaces: `production`, `staging`

### TEMPORAL_TASK_QUEUE
- **Type:** String
- **Default:** `fastapi-tasks`
- **Description:** Task queue name for workers
- **Example:** `user-service-tasks`, `email-queue`

## External Services

### EMAIL_API_KEY
- **Type:** String
- **Default:** `your-email-api-key-change-this`
- **Description:** API key for email service (e.g., SendGrid, Mailgun)
- **Production:** Get from email provider dashboard
- **⚠️ CRITICAL:** Never commit to Git

## Environment-Specific Configurations

### Development (.env.development)

```bash
APP_ENV=development
DEBUG=True
LOG_LEVEL=DEBUG
DATABASE_ECHO=True
RELOAD=True
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
OTEL_TRACE_SAMPLE_RATE=1.0
```

### Staging (.env.staging)

```bash
APP_ENV=staging
DEBUG=False
LOG_LEVEL=INFO
DATABASE_ECHO=False
RELOAD=False
WORKERS=4
CORS_ORIGINS=["https://staging.example.com"]
SECRET_KEY=<generated-secret>
OTEL_TRACE_SAMPLE_RATE=0.5
```

### Production (.env.production)

```bash
APP_ENV=production
DEBUG=False
LOG_LEVEL=WARNING
DATABASE_ECHO=False
RELOAD=False
WORKERS=9
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
CORS_ORIGINS=["https://app.example.com"]
CORS_ALLOW_METHODS=["GET","POST","PUT","DELETE"]
CORS_ALLOW_HEADERS=["Content-Type","Authorization","X-Tenant-Token"]
SECRET_KEY=<generated-secret>
DOCS_URL=None
REDOC_URL=None
OPENAPI_URL=None
OTEL_EXPORTER_OTLP_INSECURE=False
OTEL_TRACE_SAMPLE_RATE=0.1
REDIS_MAX_CONNECTIONS=50
```

## Configuration Loading

Configuration is loaded via `pydantic-settings`:

```python
# src/infrastructure/config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "python-fast-forge"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    database_url: str
    redis_url: str

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

## Security Best Practices

### ✅ DO

1. **Use secrets manager** in production (AWS Secrets Manager, HashiCorp Vault)
2. **Generate strong SECRET_KEY** using `secrets.token_urlsafe(32)`
3. **Disable debug mode** (`DEBUG=False`) in production
4. **Restrict CORS** origins to specific domains
5. **Use TLS** for database and Redis connections
6. **Rotate secrets** regularly (SECRET_KEY, DATABASE_URL)
7. **Use environment-specific** .env files (.env.production, .env.staging)

### ❌ DON'T

1. **Never commit** .env files to Git (add to .gitignore)
2. **Never use default** SECRET_KEY in production
3. **Never expose** docs in production (DOCS_URL=None)
4. **Never log** sensitive data (DATABASE_URL, SECRET_KEY)
5. **Never use** `DEBUG=True` in production
6. **Never allow** `CORS_ORIGINS=["*"]` in production

## Configuration Validation

The application validates configuration on startup:

```python
# Validates required variables
if not settings.secret_key or settings.secret_key == "your-secret-key-change-this-in-production":
    raise ValueError("SECRET_KEY must be set to a secure value")

# Validates production settings
if settings.app_env == "production":
    if settings.debug:
        raise ValueError("DEBUG must be False in production")
    if settings.docs_url or settings.redoc_url:
        raise ValueError("API docs should be disabled in production")
```

## Docker Configuration

When using Docker Compose, override `.env` for containers:

```yaml
# docker-compose.yml
services:
  api:
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/fastapi_db
      - REDIS_URL=redis://redis:6379/0
      - TEMPORAL_HOST=temporal:7233
```

**Note:** Use service names (`db`, `redis`) instead of `localhost` in Docker.

## Troubleshooting

**Problem:** Configuration not loading

**Solution:**
1. Check `.env` file exists in project root
2. Check variable names match (case-insensitive)
3. Restart application

**Problem:** Database connection fails

**Solution:**
1. Verify `DATABASE_URL` format
2. Check database is running: `docker-compose ps`
3. Test connection: `docker-compose exec db psql -U postgres`

**Problem:** "SECRET_KEY must be set"

**Solution:** Generate new key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to `.env`:
```
SECRET_KEY=<generated-key>
```

## Further Reading

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/usage/settings/)
- [12-Factor App Config](https://12factor.net/config)
- [How to Deploy](../how-to/deployment.md)
- [Security Best Practices](../explanation/security.md)
