# Operational Runbook

## Overview

This runbook provides step-by-step procedures for common operational tasks, troubleshooting, and incident response for the Python FastAPI Boilerplate application.

**Target Audience:** DevOps engineers, SREs, on-call engineers

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Service Health Checks](#service-health-checks)
3. [Common Operations](#common-operations)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Incident Response](#incident-response)
6. [Performance Issues](#performance-issues)
7. [Database Operations](#database-operations)
8. [Cache Operations](#cache-operations)
9. [Monitoring & Alerts](#monitoring--alerts)
10. [Disaster Recovery](#disaster-recovery)

---

## System Architecture Overview

### Services

| Service | Port | Purpose | Dependencies |
|---------|------|---------|--------------|
| FastAPI | 8000 | Main API service | PostgreSQL, Redis, Temporal |
| PostgreSQL | 5432 | Primary database | None |
| Redis | 6379 | Cache & rate limiting | None |
| Temporal | 7233 | Workflow engine | PostgreSQL |
| Temporal Worker | - | Background jobs | Temporal, PostgreSQL |

### Critical Endpoints

- **Health Check:** `GET /health` - Overall system health
- **API Docs:** `GET /docs` - Swagger UI
- **Metrics:** `/metrics` - Prometheus metrics (if enabled)

---

## Service Health Checks

### Check API Health

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "timestamp": "2025-01-01T00:00:00Z"}

# Check with timeout
curl --max-time 5 http://localhost:8000/health
```

### Check Database Health

```bash
# Connect to database
docker compose exec postgres psql -U postgres -d fastapi_db

# Check connection count
SELECT count(*) FROM pg_stat_activity;

# Check database size
SELECT pg_size_pretty(pg_database_size('fastapi_db'));

# Check for long-running queries
SELECT pid, now() - query_start as duration, query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '5 minutes';
```

### Check Redis Health

```bash
# Connect to Redis
docker compose exec redis redis-cli

# Check connection
PING  # Should return PONG

# Get info
INFO

# Check memory usage
INFO memory

# Check connected clients
CLIENT LIST
```

### Check Temporal

```bash
# Temporal UI
open http://localhost:8080

# Check workflows
docker compose exec temporal tctl workflow list

# Check task queue
docker compose exec temporal tctl task-queue describe --task-queue fastapi-tasks
```

---

## Common Operations

### Deploying New Version

```bash
# 1. Pull latest code
git pull origin main

# 2. Run database migrations
make migrate env=production

# 3. Build new Docker image
docker compose build api

# 4. Rolling restart (zero downtime)
docker compose up -d --no-deps --build api

# 5. Verify health
curl http://localhost:8000/health

# 6. Check logs for errors
docker compose logs -f api | head -100
```

### Rolling Back Deployment

```bash
# 1. Identify previous version
git log --oneline | head -5

# 2. Checkout previous version
git checkout <previous-commit-hash>

# 3. Rollback database if needed
make migrate-downgrade env=production n=1

# 4. Rebuild and restart
docker compose up -d --no-deps --build api

# 5. Verify
curl http://localhost:8000/health
```

### Scaling Services

```bash
# Scale API workers
docker compose up -d --scale api=3

# Scale Temporal workers
docker compose up -d --scale temporal-worker=5

# Verify scaling
docker compose ps
```

### View Logs

```bash
# All logs
docker compose logs -f

# API logs only
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api

# Follow new logs
docker compose logs -f api

# Grep for errors
docker compose logs api | grep ERROR

# Export logs
docker compose logs api > api-logs-$(date +%Y%m%d).txt
```

---

## Troubleshooting Guide

### Issue: API Returns 502/503 Errors

**Symptoms:**
- Users getting 502 Bad Gateway or 503 Service Unavailable
- Health check failing

**Investigation:**
```bash
# Check if API is running
docker compose ps api

# Check API logs
docker compose logs --tail=100 api

# Check resource usage
docker stats api

# Check system resources
df -h  # Disk space
free -h  # Memory
```

**Solutions:**
1. **Out of Memory:**
   ```bash
   # Restart API
   docker compose restart api

   # Increase memory limit in docker-compose.yml
   # deploy:
   #   resources:
   #     limits:
   #       memory: 2G
   ```

2. **Database Connection Pool Exhausted:**
   ```bash
   # Check active connections
   docker compose exec postgres psql -U postgres -d fastapi_db \
     -c "SELECT count(*) FROM pg_stat_activity WHERE datname='fastapi_db';"

   # Kill idle connections
   docker compose exec postgres psql -U postgres -d fastapi_db \
     -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE datname='fastapi_db' AND state='idle'
         AND state_change < now() - interval '5 minutes';"
   ```

3. **Application Crash:**
   ```bash
   # Check exit code
   docker compose ps -a

   # Restart service
   docker compose restart api
   ```

---

### Issue: Slow API Response Times

**Symptoms:**
- API responses taking > 1 second
- Users complaining about slow page loads

**Investigation:**
```bash
# Run performance benchmarks
pytest tests/benchmarks/test_api_performance.py -v

# Check database query performance
pytest tests/benchmarks/test_database_performance.py -v

# Monitor real-time performance
while true; do
  time curl -s http://localhost:8000/api/v1/users > /dev/null
  sleep 1
done
```

**Solutions:**
1. **Database Slow Queries:**
   ```sql
   -- Find slow queries
   SELECT pid, now() - query_start as duration, query
   FROM pg_stat_activity
   WHERE state = 'active'
   ORDER BY duration DESC
   LIMIT 10;

   -- Check index usage
   SELECT schemaname, tablename, indexname, idx_scan
   FROM pg_stat_user_indexes
   WHERE idx_scan = 0;
   ```

2. **Cache Not Working:**
   ```bash
   # Check Redis connection
   docker compose exec redis redis-cli PING

   # Check cache hit rate
   docker compose exec redis redis-cli INFO stats | grep keyspace

   # Check cache enabled
   grep CACHE_ENABLED .env
   ```

3. **Too Many Database Connections:**
   ```bash
   # Increase pool size in .env
   DATABASE_POOL_SIZE=20
   DATABASE_MAX_OVERFLOW=40
   ```

---

### Issue: High Memory Usage

**Symptoms:**
- Out of memory errors
- Container restarts
- System becoming unresponsive

**Investigation:**
```bash
# Check memory usage
docker stats

# Check memory per process
docker compose exec api ps aux --sort=-%mem | head

# Check Python memory usage
docker compose exec api python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"
```

**Solutions:**
1. **Memory Leak:**
   ```bash
   # Restart service
   docker compose restart api

   # Monitor memory growth
   watch -n 5 'docker stats api --no-stream'

   # If leak continues, investigate code
   # Enable memory profiling and analyze
   ```

2. **Too Many Workers:**
   ```bash
   # Reduce Uvicorn workers in .env
   WORKERS=2  # Instead of 4
   ```

3. **Large Response Payloads:**
   ```bash
   # Check response sizes
   curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/api/v1/users

   # Implement pagination if needed
   ```

---

### Issue: Database Connection Errors

**Symptoms:**
- "Connection refused" errors
- "Too many connections" errors
- "Connection timeout" errors

**Investigation:**
```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs --tail=100 postgres

# Check connection count
docker compose exec postgres psql -U postgres \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Check max connections
docker compose exec postgres psql -U postgres \
  -c "SHOW max_connections;"
```

**Solutions:**
1. **PostgreSQL Not Running:**
   ```bash
   docker compose restart postgres
   docker compose ps postgres
   ```

2. **Connection Pool Exhausted:**
   ```bash
   # Kill idle connections
   docker compose exec postgres psql -U postgres -d fastapi_db \
     -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
         WHERE datname='fastapi_db' AND state='idle';"

   # Increase max connections in docker-compose.yml
   # postgres:
   #   command: postgres -c max_connections=200
   ```

3. **Network Issues:**
   ```bash
   # Check network
   docker network ls
   docker network inspect app-network

   # Restart network
   docker compose down
   docker compose up -d
   ```

---

### Issue: Redis Connection Errors

**Symptoms:**
- "Connection refused" to Redis
- Cache misses
- Slow performance

**Investigation:**
```bash
# Check Redis status
docker compose ps redis

# Check Redis logs
docker compose logs --tail=100 redis

# Test connection
docker compose exec redis redis-cli PING
```

**Solutions:**
1. **Redis Not Running:**
   ```bash
   docker compose restart redis
   ```

2. **Redis Out of Memory:**
   ```bash
   # Check memory
   docker compose exec redis redis-cli INFO memory

   # Clear cache if needed
   docker compose exec redis redis-cli FLUSHDB
   ```

3. **Too Many Connections:**
   ```bash
   # Check connections
   docker compose exec redis redis-cli CLIENT LIST | wc -l

   # Increase max connections in docker-compose.yml
   # redis:
   #   command: redis-server --maxclients 10000
   ```

---

## Incident Response

### Severity Levels

**P0 - Critical (Complete Outage)**
- Service completely down
- Data loss occurring
- Security breach

**P1 - High (Partial Outage)**
- Major functionality unavailable
- Significant performance degradation
- Affecting multiple users

**P2 - Medium (Degraded Service)**
- Minor functionality issues
- Affecting small number of users
- Workaround available

**P3 - Low (Minor Issues)**
- Cosmetic issues
- Minimal user impact
- Can be addressed during business hours

---

### P0 Incident Response Procedure

1. **Acknowledge (< 5 minutes)**
   ```bash
   # Check service status
   curl http://localhost:8000/health
   docker compose ps

   # Post in incident channel
   # "P0 incident acknowledged. Investigating API outage."
   ```

2. **Investigate (< 15 minutes)**
   ```bash
   # Check logs
   docker compose logs --tail=200 api

   # Check metrics
   # Open Grafana: http://localhost:3000

   # Check database
   docker compose ps postgres

   # Document findings in incident doc
   ```

3. **Mitigate (< 30 minutes)**
   ```bash
   # Quick fixes:
   # - Restart services
   # - Rollback deployment
   # - Scale up resources
   # - Enable maintenance mode

   # Example: Restart all services
   docker compose restart
   ```

4. **Resolve (< 1 hour)**
   ```bash
   # Verify resolution
   curl http://localhost:8000/health

   # Run smoke tests
   pytest tests/integration/test_health.py -v

   # Monitor for 15 minutes
   watch -n 30 'curl -s http://localhost:8000/health'
   ```

5. **Post-Incident (< 48 hours)**
   - Write incident report
   - Identify root cause
   - Create action items
   - Schedule post-mortem

---

## Performance Issues

### Monitoring Performance

```bash
# API response times
time curl http://localhost:8000/health

# Database query times
docker compose exec postgres psql -U postgres -d fastapi_db \
  -c "SELECT query, mean_exec_time, calls
      FROM pg_stat_statements
      ORDER BY mean_exec_time DESC
      LIMIT 10;"

# Cache hit rate
docker compose exec redis redis-cli INFO stats | grep keyspace_hits
```

### Performance Optimization Checklist

- [ ] Enable Redis caching (`CACHE_ENABLED=true`)
- [ ] Add database indexes for frequent queries
- [ ] Enable connection pooling
- [ ] Implement pagination for large result sets
- [ ] Enable gzip compression
- [ ] Use CDN for static assets
- [ ] Optimize N+1 queries (use bulk queries)
- [ ] Enable query result caching
- [ ] Review slow query logs
- [ ] Monitor memory usage

---

## Database Operations

### Backup Database

```bash
# Create backup
make db-backup file=backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql

# Upload to S3 (if configured)
aws s3 cp backup_*.sql s3://backups/fastapi/
```

### Restore Database

```bash
# Restore from backup
make db-restore file=backup_20250101_120000.sql

# Verify restoration
docker compose exec postgres psql -U postgres -d fastapi_db \
  -c "SELECT count(*) FROM users;"
```

### Run Migrations

```bash
# Check migration status
make migrate-status env=production

# Apply migrations
make migrate env=production

# Rollback migration
make migrate-downgrade env=production n=1
```

---

## Cache Operations

### Clear Cache

```bash
# Clear all cache
docker compose exec redis redis-cli FLUSHDB

# Clear specific pattern
docker compose exec redis redis-cli --scan --pattern "user:*" | \
  xargs docker compose exec redis redis-cli DEL

# Restart Redis
docker compose restart redis
```

### Monitor Cache

```bash
# Cache statistics
docker compose exec redis redis-cli INFO stats

# Monitor commands
docker compose exec redis redis-cli MONITOR

# Check memory
docker compose exec redis redis-cli INFO memory
```

---

## Monitoring & Alerts

### Key Metrics to Monitor

**Application Metrics:**
- Request rate (req/s)
- Response time (p50, p95, p99)
- Error rate (%)
- Active connections

**System Metrics:**
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)
- Network I/O

**Database Metrics:**
- Connection count
- Query time (ms)
- Slow query count
- Deadlock count

**Cache Metrics:**
- Hit rate (%)
- Memory usage (%)
- Eviction rate
- Connection count

### Setting Up Alerts

Example alert thresholds:

```yaml
# API Response Time
- alert: HighAPILatency
  expr: api_request_duration_p95 > 1.0
  for: 5m
  severity: warning

# Error Rate
- alert: HighErrorRate
  expr: api_error_rate > 5.0
  for: 2m
  severity: critical

# Database Connections
- alert: DatabaseConnectionPoolExhausted
  expr: database_connections_active > 45
  for: 1m
  severity: warning
```

---

## Disaster Recovery

### Recovery Time Objectives (RTO)

- **Complete Service Restoration:** < 4 hours
- **Database Restoration:** < 1 hour
- **Cache Restoration:** < 15 minutes

### Recovery Point Objectives (RPO)

- **Database:** < 15 minutes (transaction log backup)
- **Configuration:** Current (git-backed)
- **Code:** Current (git-backed)

### Disaster Recovery Procedure

1. **Assess Scope of Disaster**
   ```bash
   # Check what's down
   docker compose ps
   curl http://localhost:8000/health
   ```

2. **Restore from Backup**
   ```bash
   # Restore database
   make db-restore file=latest-backup.sql

   # Restore configuration
   git checkout main
   cp .env.backup .env
   ```

3. **Rebuild Services**
   ```bash
   # Rebuild all services
   docker compose down -v
   docker compose up -d --build
   ```

4. **Verify Recovery**
   ```bash
   # Check health
   curl http://localhost:8000/health

   # Run smoke tests
   pytest tests/integration/ -v
   ```

5. **Communicate Status**
   - Update status page
   - Notify stakeholders
   - Document incident

---

## Emergency Contacts

**On-Call Rotation:** See PagerDuty schedule

**Escalation Path:**
1. On-call engineer (primary)
2. Team lead (secondary)
3. Engineering manager (tertiary)

**External Vendors:**
- AWS Support: 1-800-XXX-XXXX
- Database hosting: support@provider.com
- CDN provider: cdn-support@provider.com

---

## Related Documentation

- [Architecture Overview](../reference/architecture.md)
- [Deployment Guide](../how-to/deployment.md)
- [Monitoring Setup](../how-to/observability.md)
- [Database Migrations](../how-to/database-migrations.md)

---

**Last Updated:** 2025-11-11
**Maintained By:** DevOps Team
**Review Frequency:** Quarterly
