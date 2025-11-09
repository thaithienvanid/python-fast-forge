# Deployment Guide

Deploy your FastAPI application to production.

## Prerequisites

- Docker and Docker Compose installed
- Domain name configured
- SSL certificates (Let's Encrypt or commercial)
- Production database (PostgreSQL)
- Production secrets management

## Quick Deployment Checklist

- [ ] Configure environment variables
- [ ] Set up production database
- [ ] Configure SSL/TLS certificates
- [ ] Set up secrets management
- [ ] Configure CORS and security headers
- [ ] Set up logging and monitoring
- [ ] Configure backup strategy
- [ ] Test deployment
- [ ] Set up health checks
- [ ] Configure CI/CD pipeline

---

## 1. Production Environment Setup

### Environment Variables

Create production `.env` file:

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:password@prod-db.example.com:5432/app_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Security
SECRET_KEY=your-super-secret-key-min-32-characters
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
BACKEND_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]

# API
API_V1_STR=/api/v1
PROJECT_NAME="Your Production App"

# Email (Production SMTP)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
EMAILS_FROM_EMAIL=noreply@yourdomain.com
EMAILS_FROM_NAME="Your App"

# Temporal (Production)
TEMPORAL_HOST=prod-temporal.example.com:7233
TEMPORAL_NAMESPACE=production

# OpenTelemetry
OTEL_SERVICE_NAME=your-app-production
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-otel-collector:4317
```

### Security Checklist

**DO ✅:**
- Use strong, randomly generated secrets (32+ characters)
- Store secrets in environment variables, never in code
- Use HTTPS everywhere (enforce SSL/TLS)
- Enable CORS only for trusted domains
- Use database connection pooling
- Enable rate limiting
- Use secure session cookies
- Keep dependencies up to date

**DON'T ❌:**
- Don't commit secrets to git
- Don't use DEBUG=true in production
- Don't expose internal error details
- Don't use default passwords
- Don't allow * in CORS origins

---

## 2. Docker Production Setup

### Production Dockerfile

```dockerfile
# Dockerfile.production
FROM python:3.12-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ src/
COPY atlas.hcl .
COPY migrations/ migrations/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Production Docker Compose

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.production
    env_file:
      - .env.production
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  postgres:
    image: postgres:16-alpine
    env_file:
      - .env.production
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped

  temporal:
    image: temporalio/auto-setup:latest
    env_file:
      - .env.production
    ports:
      - "7233:7233"
    depends_on:
      - postgres
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

## 3. Nginx Configuration

### SSL/TLS Setup

```nginx
# nginx/nginx.conf
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    keepalive_timeout 65;
    client_max_body_size 10M;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        # SSL certificates
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # API routes
        location /api/ {
            limit_req zone=api burst=20 nodelay;

            proxy_pass http://api:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check
        location /health {
            proxy_pass http://api:8000/health;
            access_log off;
        }

        # Static files (if any)
        location /static/ {
            alias /app/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

---

## 4. Database Migration

### Run Migrations in Production

```bash
# Backup database first
docker compose exec postgres pg_dump -U postgres app_db > backup_$(date +%Y%m%d).sql

# Run migrations
make migrate

# Verify migration
docker compose exec db psql -U forge_user -d forge_db -c "SELECT version, executed_at FROM atlas_schema_revisions ORDER BY executed_at DESC LIMIT 1;"
```

### Rollback Strategy

```bash
# Rollback one migration
atlas migrate down --env production

# Rollback to specific version
atlas migrate down --env production --to-version <version>

# Restore from backup if needed
docker compose exec -T postgres psql -U postgres app_db < backup_20240101.sql
```

---

## 5. Monitoring and Logging

### Structured Logging

Already configured with structlog. View logs:

```bash
# Follow logs
docker compose logs -f api

# Export logs to file
docker compose logs api > logs_$(date +%Y%m%d).log
```

### Health Checks

```bash
# API health
curl https://yourdomain.com/health

# Database health
docker compose exec postgres pg_isready

# Redis health
docker compose exec redis redis-cli ping
```

### Monitoring with Prometheus (Optional)

```yaml
# Add to docker-compose.production.yml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped
```

---

## 6. Secrets Management

### Using Environment Variables

```bash
# Set production secrets
export DATABASE_URL="postgresql+asyncpg://..."
export SECRET_KEY="..."
```

### Using Docker Secrets

```yaml
# docker-compose.production.yml
services:
  api:
    secrets:
      - db_password
      - jwt_secret

secrets:
  db_password:
    external: true
  jwt_secret:
    external: true
```

Create secrets:

```bash
echo "your-db-password" | docker secret create db_password -
echo "your-jwt-secret" | docker secret create jwt_secret -
```

### Using AWS Secrets Manager (Optional)

```python
# src/app/core/config.py
import boto3
import json

def load_secrets():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    secret = client.get_secret_value(SecretId='prod/app/secrets')
    return json.loads(secret['SecretString'])
```

---

## 7. Backup Strategy

### Database Backups

```bash
# Daily backup script
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups
RETENTION_DAYS=30

# Create backup
docker compose exec -T postgres pg_dump -U postgres app_db | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Remove old backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

Schedule with cron:

```bash
# Run daily at 2 AM
0 2 * * * /path/to/backup.sh >> /var/log/backup.log 2>&1
```

### Restore from Backup

```bash
# Stop API
docker compose stop api

# Restore database
gunzip -c backup_20240101.sql.gz | docker compose exec -T postgres psql -U postgres app_db

# Start API
docker compose start api
```

---

## 8. CI/CD Pipeline

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v5

      - name: Run tests
        run: |
          docker compose -f docker-compose.test.yml up --abort-on-container-exit

      - name: Build Docker image
        run: |
          docker build -f Dockerfile.production -t myapp:${{ github.sha }} .

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker tag myapp:${{ github.sha }} myregistry/myapp:latest
          docker push myregistry/myapp:latest

      - name: Deploy to production
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /app
            docker compose pull
            docker compose up -d
            make migrate
```

---

## 9. Zero-Downtime Deployment

### Blue-Green Deployment

```bash
# Start new version (green)
docker compose -f docker-compose.production.yml up -d --scale api=2

# Wait for health check
sleep 30

# Stop old version (blue)
docker compose -f docker-compose.production.yml up -d --scale api=1
```

### Rolling Updates

```yaml
# docker-compose.production.yml
services:
  api:
    deploy:
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
```

---

## 10. Troubleshooting Production Issues

### Check Service Status

```bash
# All services
docker compose ps

# Restart specific service
docker compose restart api

# View resource usage
docker stats
```

### View Logs

```bash
# Last 100 lines
docker compose logs --tail=100 api

# Follow logs
docker compose logs -f api

# Filter by error level
docker compose logs api | grep ERROR
```

### Database Connection Issues

```bash
# Test database connection
docker compose exec postgres psql -U postgres -d app_db -c "SELECT 1"

# Check connection pool
docker compose exec api python -c "from src.app.core.database import engine; print(engine.pool.status())"
```

---

## 11. Performance Optimization

### Uvicorn Workers

Adjust number of workers based on CPU cores:

```dockerfile
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Formula: `workers = (2 × CPU_cores) + 1`

### Database Connection Pool

```python
# src/app/core/database.py
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # Max connections in pool
    max_overflow=10,        # Additional connections allowed
    pool_timeout=30,        # Seconds to wait for connection
    pool_recycle=3600,      # Recycle connections after 1 hour
)
```

### Caching with Redis

```python
# src/app/core/cache.py
from redis import asyncio as aioredis

redis_client = aioredis.from_url(
    REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)
```

---

## 12. Post-Deployment Checklist

- [ ] All services running (`docker compose ps`)
- [ ] Health checks passing (`curl https://yourdomain.com/health`)
- [ ] Database migrations applied (check `atlas_schema_revisions` table)
- [ ] SSL certificate valid (check browser)
- [ ] Logs are clean (`docker compose logs`)
- [ ] Monitoring is working (Prometheus/Grafana)
- [ ] Backups are running (check cron)
- [ ] Rate limiting is working (test with multiple requests)
- [ ] CORS is configured correctly (test from frontend)
- [ ] Error tracking is working (Sentry/etc)

---

## Next Steps

- Set up [Monitoring and Alerting](https://prometheus.io)
- Configure [Error Tracking](https://sentry.io)
- Review [Security Best Practices](../reference/configuration.md#security)
- Learn [Debugging in Production](debugging.md)
- Read [Architecture Guide](../reference/architecture.md)
