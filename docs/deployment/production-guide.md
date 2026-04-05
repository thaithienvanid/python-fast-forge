# Production Deployment Guide

Comprehensive guide for deploying python-fast-forge to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Configuration](#configuration)
5. [Database Migration](#database-migration)
6. [Deployment Methods](#deployment-methods)
7. [Post-Deployment Verification](#post-deployment-verification)
8. [Monitoring & Alerting](#monitoring--alerting)
9. [Rollback Procedures](#rollback-procedures)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum Hardware:**
- CPU: 2 cores (4 cores recommended)
- RAM: 2GB (4GB recommended)
- Disk: 20GB SSD
- Network: 100 Mbps

**Software:**
- Python 3.12+ (3.13/3.14 supported)
- PostgreSQL 14+ (15+ recommended)
- Redis 7.0+
- Docker 24.0+ and Docker Compose 2.20+ (for containerized deployment)

### Required Services

1. **Database (PostgreSQL)**
   - Version: 14+ (production-ready with WAL streaming)
   - Backup solution configured
   - Connection pooling (PgBouncer recommended)

2. **Cache (Redis)**
   - Version: 7.0+
   - Persistence enabled (AOF or RDB)
   - Memory limit configured

3. **Reverse Proxy**
   - Nginx or Traefik
   - SSL/TLS certificates
   - Rate limiting configured

4. **Monitoring (Optional but Recommended)**
   - Prometheus + Grafana
   - Jaeger or Tempo (for distributed tracing)
   - Sentry (for error tracking)

---

## Pre-Deployment Checklist

### Security Checklist

- [ ] **JWT Keys Generated**
  ```bash
  # Generate ES256 key pair
  openssl ecparam -genkey -name prime256v1 -noout -out private-key.pem
  openssl ec -in private-key.pem -pubout -out public-key.pem

  # Base64 encode for environment variables
  cat private-key.pem | base64 -w 0 > private-key-base64.txt
  cat public-key.pem | base64 -w 0 > public-key-base64.txt
  ```

- [ ] **Secrets Managed Securely**
  - Use secrets manager (AWS Secrets Manager, Vault, etc.)
  - Never commit secrets to Git
  - Rotate secrets regularly

- [ ] **CORS Origins Configured**
  - Production domains only
  - HTTPS enforced
  - No wildcards in production

- [ ] **Rate Limiting Enabled**
  - Set appropriate limits
  - Configure Redis for rate limit storage

### Database Checklist

- [ ] **Backup Strategy**
  - Automated daily backups
  - Point-in-time recovery (PITR) enabled
  - Backup retention policy defined
  - Restore procedure tested

- [ ] **Connection Pool**
  - Pool size: 10-20 (adjust based on load)
  - Max overflow: 20
  - Connection timeout: 30s

- [ ] **Indexes Optimized**
  ```sql
  -- Verify critical indexes exist
  SELECT * FROM pg_indexes WHERE schemaname = 'public';

  -- Check for missing indexes (slow queries)
  SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;
  ```

### Application Checklist

- [ ] **Environment Variables Set**
  - APP_ENV=production
  - DEBUG=false
  - All required secrets configured

- [ ] **Dependencies Updated**
  ```bash
  # Update to latest security patches
  pip install --upgrade -r requirements.txt
  ```

- [ ] **Tests Passing**
  ```bash
  pytest tests/ -v --cov
  ```

- [ ] **Static Analysis Clean**
  ```bash
  ruff check .
  mypy src/
  ```

---

## Infrastructure Setup

### Option 1: Docker Compose (Recommended for Small/Medium Scale)

**docker-compose.prod.yml:**
```yaml
version: '3.9'

services:
  api:
    image: python-fast-forge:latest
    restart: always
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/prod_db
      - REDIS_URL=redis://redis:6379/0
      - JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
      - OTEL_ENABLED=true
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  postgres:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_DB: prod_db
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

**Deployment Commands:**
```bash
# Build production image
docker build -t python-fast-forge:latest -f Dockerfile.prod .

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f api

# Scale API service
docker compose -f docker-compose.prod.yml up -d --scale api=3
```

### Option 2: Kubernetes (Recommended for Large Scale)

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-deployment
  labels:
    app: fastapi
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi
  template:
    metadata:
      labels:
        app: fastapi
    spec:
      containers:
      - name: api
        image: python-fast-forge:latest
        ports:
        - containerPort: 8000
        env:
        - name: APP_ENV
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: JWT_PRIVATE_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: jwt-private-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: fastapi-service
spec:
  selector:
    app: fastapi
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-deployment
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Deployment Commands:**
```bash
# Create secrets
kubectl create secret generic app-secrets \
  --from-literal=database-url="${DATABASE_URL}" \
  --from-literal=jwt-private-key="${JWT_PRIVATE_KEY}"

# Apply deployment
kubectl apply -f deployment.yaml

# Check status
kubectl get pods -l app=fastapi
kubectl logs -f deployment/fastapi-deployment

# Scale manually
kubectl scale deployment fastapi-deployment --replicas=5
```

---

## Configuration

### Environment Variables (Production)

Create `.env.production` file:

```bash
# Application
APP_NAME=python-fast-forge
APP_VERSION=0.1.0
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4  # (CPU cores * 2) + 1

# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres-host:5432/prod_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_ECHO=false

# Redis/Cache
REDIS_URL=redis://redis-host:6379/0
REDIS_MAX_CONNECTIONS=50
CACHE_ENABLED=true
CACHE_TTL=300

# Security - JWT
JWT_ALGORITHM=ES256
JWT_PRIVATE_KEY=<base64-encoded-private-key>
JWT_PUBLIC_KEY=<base64-encoded-public-key>
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Security - API Signature
SECRET_KEY=<your-secret-key-here>

# CORS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOW_CREDENTIALS=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# OpenTelemetry
OTEL_ENABLED=true
OTEL_SERVICE_NAME=python-fast-forge-prod
OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo:4317
OTEL_TRACE_SAMPLE_RATE=0.1  # Sample 10% of traces in production

# Temporal Workflow Engine
TEMPORAL_HOST=temporal:7233
TEMPORAL_NAMESPACE=production
TEMPORAL_TASK_QUEUE=fastapi-tasks-prod

# External Services
EMAIL_API_KEY=<your-email-api-key>
```

### Nginx Configuration

**nginx.conf:**
```nginx
upstream fastapi_backend {
    least_conn;
    server api1:8000 max_fails=3 fail_timeout=30s;
    server api2:8000 max_fails=3 fail_timeout=30s;
    server api3:8000 max_fails=3 fail_timeout=30s;
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Logging
    access_log /var/log/nginx/fastapi_access.log combined;
    error_log /var/log/nginx/fastapi_error.log warn;

    # API endpoints
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Auth endpoints (stricter rate limiting)
    location /api/v1/auth/ {
        limit_req zone=auth_limit burst=5 nodelay;

        proxy_pass http://fastapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check (no rate limiting)
    location /health {
        proxy_pass http://fastapi_backend;
        access_log off;
    }

    # Static files (if any)
    location /static/ {
        alias /app/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## Database Migration

### Pre-Migration Backup

```bash
# Create full backup before migration
pg_dump -h postgres-host -U username -d database_name -F c -f backup_pre_migration_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list backup_pre_migration_*.dump | head -20
```

### Run Migrations

```bash
# Using Alembic
alembic upgrade head

# Verify migration
alembic current
alembic history
```

### Post-Migration Verification

```sql
-- Check table structure
\d+ users

-- Verify data integrity
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM users WHERE deleted_at IS NULL;

-- Check indexes
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

---

## Deployment Methods

### Zero-Downtime Deployment (Blue-Green)

```bash
# 1. Deploy new version (green) alongside current (blue)
docker compose -f docker-compose.prod.yml up -d --scale api=6  # 3 blue + 3 green

# 2. Health check new instances
for i in {1..10}; do
    curl -f http://green-api:8000/health && echo "Healthy" || echo "Unhealthy"
    sleep 2
done

# 3. Switch traffic to green
nginx -s reload  # After updating upstream config

# 4. Monitor for errors
docker compose -f docker-compose.prod.yml logs --tail=100 -f api

# 5. If successful, remove blue instances
docker compose -f docker-compose.prod.yml up -d --scale api=3  # Only green
```

### Rolling Deployment

```bash
# Kubernetes automatically handles rolling updates
kubectl set image deployment/fastapi-deployment api=python-fast-forge:v1.2.0

# Monitor rollout
kubectl rollout status deployment/fastapi-deployment

# Check rollout history
kubectl rollout history deployment/fastapi-deployment
```

---

## Post-Deployment Verification

### Health Checks

```bash
# 1. Application health
curl https://yourdomain.com/health
# Expected: {"status": "healthy"}

# 2. Database connectivity
curl https://yourdomain.com/api/v1/users?limit=1
# Expected: 200 OK with user data

# 3. Redis connectivity
# Check cache hit (should increase over time)
docker exec redis redis-cli INFO stats | grep keyspace_hits

# 4. Authentication
curl -X POST https://yourdomain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass"}'
# Expected: 200 OK with JWT token
```

### Performance Verification

```bash
# Load test with Apache Bench
ab -n 1000 -c 10 https://yourdomain.com/health

# Expected metrics:
# - Requests per second: > 100
# - Time per request (mean): < 100ms
# - Failed requests: 0

# Load test API endpoints
ab -n 100 -c 5 -H "Authorization: Bearer <token>" \
  https://yourdomain.com/api/v1/users
```

### Monitoring Verification

```bash
# Check metrics endpoint
curl https://yourdomain.com/metrics

# Verify logs are flowing
tail -f /var/log/nginx/fastapi_access.log

# Check error tracking (Sentry)
# Login to Sentry dashboard and verify events are being captured
```

---

## Monitoring & Alerting

### Key Metrics to Monitor

**Application Metrics:**
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- Active connections
- Memory usage
- CPU usage

**Database Metrics:**
- Connection pool usage
- Query latency
- Cache hit rate
- Slow queries (> 1s)
- Lock waits
- Replication lag

**Redis Metrics:**
- Memory usage
- Cache hit/miss ratio
- Evicted keys
- Connected clients
- Commands processed/sec

### Prometheus Queries

```promql
# API latency p95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Database connection pool utilization
database_connections_active / database_connections_max

# Redis memory usage
redis_memory_used_bytes / redis_memory_max_bytes
```

### Alert Rules

```yaml
groups:
- name: fastapi_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate detected"

  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
    for: 5m
    annotations:
      summary: "API latency p95 > 1s"

  - alert: DatabaseConnectionPoolExhausted
    expr: database_connections_active / database_connections_max > 0.9
    for: 5m
    annotations:
      summary: "Database connection pool > 90% utilized"
```

---

## Rollback Procedures

### Application Rollback

**Docker Compose:**
```bash
# Rollback to previous image
docker compose -f docker-compose.prod.yml down
docker tag python-fast-forge:v1.1.0 python-fast-forge:latest
docker compose -f docker-compose.prod.yml up -d

# Verify
curl https://yourdomain.com/health
```

**Kubernetes:**
```bash
# Rollback to previous revision
kubectl rollout undo deployment/fastapi-deployment

# Rollback to specific revision
kubectl rollout undo deployment/fastapi-deployment --to-revision=2

# Check status
kubectl rollout status deployment/fastapi-deployment
```

### Database Rollback

```bash
# Rollback last migration
alembic downgrade -1

# Restore from backup (if necessary)
pg_restore -h postgres-host -U username -d database_name -c backup_file.dump
```

---

## Troubleshooting

### Common Issues

**1. Application won't start**
```bash
# Check logs
docker compose logs api
kubectl logs -f deployment/fastapi-deployment

# Common causes:
# - Missing environment variables
# - Database connection failure
# - Port already in use
```

**2. High latency**
```bash
# Check database connection pool
# Check slow query log
SELECT * FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 seconds';

# Check Redis performance
redis-cli --latency

# Check system resources
top
free -h
df -h
```

**3. Memory leaks**
```bash
# Monitor memory usage over time
docker stats

# Check for connection leaks
# Database connections
SELECT count(*) FROM pg_stat_activity;

# Redis connections
redis-cli CLIENT LIST | wc -l
```

### Emergency Contacts

- **On-Call Engineer:** [phone/slack]
- **Database Admin:** [contact]
- **DevOps Lead:** [contact]
- **Security Team:** [contact]

### Incident Response

1. **Severity Assessment**
   - P0: Complete outage
   - P1: Partial outage
   - P2: Performance degradation
   - P3: Minor issue

2. **Immediate Actions**
   - Check health endpoints
   - Review recent deployments
   - Check error logs
   - Verify external dependencies

3. **Communication**
   - Update status page
   - Notify stakeholders
   - Create incident channel

4. **Resolution**
   - Implement fix or rollback
   - Verify resolution
   - Document root cause
   - Create postmortem

---

## Additional Resources

- [Operational Runbook](../operations/runbook.md)
- [API Versioning Strategy](../explanation/api-versioning.md)
- [Security Best Practices](../security/best-practices.md)
- [Performance Tuning Guide](../performance/tuning.md)
