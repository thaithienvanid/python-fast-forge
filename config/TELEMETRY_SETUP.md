# Telemetry Stack Setup Guide

📍 **Documentation Path**: [README](../README.md) → [GUIDE](../GUIDE.md) → [SECRETS_MANAGEMENT](../docs/SECRETS_MANAGEMENT.md) → **TELEMETRY_SETUP**

💡 **Prerequisites**: Complete [GUIDE.md](../GUIDE.md) setup and read [SECRETS_MANAGEMENT.md](../docs/SECRETS_MANAGEMENT.md)
🎯 **You'll learn**: Set up observability stack with Jaeger, Prometheus, and Grafana
⏱️ **Time**: 15 minutes

---

This guide explains how to use the telemetry stack for observability in the FastAPI Boilerplate.

## Stack Components

The telemetry stack includes:

1. **OpenTelemetry Collector** - Receives and processes telemetry data (traces, metrics, logs)
2. **Jaeger** - Distributed tracing backend and UI
3. **Prometheus** - Metrics storage and time-series database
4. **Grafana** - Visualization and dashboards

## Quick Start

### Start Telemetry Stack

```bash
# Start infrastructure + telemetry (for local development)
docker-compose --profile infra --profile telemetry up -d

# Or start everything including the app
docker-compose --profile infra --profile app --profile telemetry up -d
```

### Access UIs

Once started, access the following UIs:

- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686
- **Prometheus**: http://localhost:9090

### Enable Telemetry in Application

Update your application environment variables:

```bash
# For local development (running on host)
export ENABLE_OPENTELEMETRY=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=fastapi-app

# Or set in .env file
ENABLE_OPENTELEMETRY=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=fastapi-app
```

For Docker containers, the environment is already configured in `docker-compose.yml`.

## Architecture

```
┌─────────────────┐
│  FastAPI App    │
│  (with OTEL SDK)│
└────────┬────────┘
         │ OTLP (gRPC/HTTP)
         ▼
┌─────────────────┐
│ OTEL Collector  │ ──────┐
│  (processes &   │       │
│   routes data)  │       │
└─────────────────┘       │
         │                │
         │                │
    ┌────┴────┬───────────┘
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│ Jaeger │ │Prometheus│
│(traces)│ │ (metrics)│
└───┬────┘ └────┬─────┘
    │           │
    └─────┬─────┘
          ▼
    ┌──────────┐
    │ Grafana  │
    │(visualize)│
    └──────────┘
```

## Using the Stack

### 1. Viewing Traces in Jaeger

1. Open http://localhost:16686
2. Select "fastapi-app" from the Service dropdown
3. Click "Find Traces" to see recent traces
4. Click on a trace to see detailed span information

**Use Cases:**
- Debug slow API requests
- Identify bottlenecks in request flow
- Analyze database query performance
- Track external API calls

### 2. Querying Metrics in Prometheus

1. Open http://localhost:9090
2. Use PromQL to query metrics:

```promql
# Request rate
rate(http_server_requests_total[5m])

# Error rate
rate(http_server_requests_total{status=~"5.."}[5m])

# Request duration (p95)
histogram_quantile(0.95, rate(http_server_request_duration_seconds_bucket[5m]))

# Database connection pool
db_pool_connections{state="active"}
```

### 3. Creating Dashboards in Grafana

1. Open http://localhost:3000 (admin/admin)
2. Prometheus and Jaeger are already configured as datasources
3. Create new dashboard or import existing ones

**Pre-built Dashboard IDs** (import via Grafana UI):
- **FastAPI Metrics**: Dashboard ID `11159` (FastAPI Observability)
- **RED Metrics**: Dashboard ID `13639` (Request, Error, Duration)
- **Jaeger Traces**: Use built-in Jaeger datasource explore

#### Example Dashboard: FastAPI RED Metrics

Save this as `config/grafana/dashboards/fastapi-red.json`:

```json
{
  "dashboard": {
    "title": "FastAPI RED Metrics",
    "tags": ["fastapi", "red"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Request Rate (requests/sec)",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_server_requests_total{job=\"fastapi-app\"}[5m])",
            "legendFormat": "{{method}} {{path}}"
          }
        ],
        "yaxes": [
          {"format": "reqps"},
          {"format": "short"}
        ]
      },
      {
        "title": "Error Rate (%)",
        "type": "graph",
        "targets": [
          {
            "expr": "100 * (rate(http_server_requests_total{status=~\"5..\"}[5m]) / rate(http_server_requests_total[5m]))",
            "legendFormat": "5xx errors"
          }
        ],
        "yaxes": [
          {"format": "percent"},
          {"format": "short"}
        ]
      },
      {
        "title": "Request Duration (p50, p95, p99)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(http_server_request_duration_seconds_bucket[5m]))",
            "legendFormat": "p50"
          },
          {
            "expr": "histogram_quantile(0.95, rate(http_server_request_duration_seconds_bucket[5m]))",
            "legendFormat": "p95"
          },
          {
            "expr": "histogram_quantile(0.99, rate(http_server_request_duration_seconds_bucket[5m]))",
            "legendFormat": "p99"
          }
        ],
        "yaxes": [
          {"format": "s"},
          {"format": "short"}
        ]
      }
    ]
  }
}
```

#### Common Dashboard Panels

**Active Requests:**
```promql
http_server_active_requests{job="fastapi-app"}
```

**Database Connection Pool:**
```promql
db_pool_connections{state="active"}
db_pool_connections{state="idle"}
```

**Memory Usage:**
```promql
process_resident_memory_bytes{job="fastapi-app"}
```

**Cache Hit Rate:**
```promql
100 * (rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])))
```

**Slow Requests (>1s):**
```promql
count(rate(http_server_request_duration_seconds_bucket{le="1.0"}[5m]) < rate(http_server_request_duration_seconds_count[5m]))
```

## Configuration Files

### OpenTelemetry Collector

**File**: `config/otel-collector-config.yaml`

Configure receivers, processors, and exporters:
- Receivers: OTLP (gRPC/HTTP) for receiving telemetry
- Processors: Batching, memory limiting, resource attributes
- Exporters: Jaeger (traces), Prometheus (metrics)

### Prometheus

**File**: `config/prometheus.yml`

Add scrape targets:
```yaml
scrape_configs:
  - job_name: 'my-service'
    static_configs:
      - targets: ['my-service:9090']
```

### Grafana

**Files**:
- `config/grafana/provisioning/datasources/datasources.yaml` - Auto-provision datasources
- `config/grafana/provisioning/dashboards/dashboards.yaml` - Auto-provision dashboards
- `config/grafana/dashboards/` - Add dashboard JSON files here

## Python Application Integration

### Install Dependencies

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
```

### Instrument FastAPI App

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Configure OpenTelemetry
resource = Resource.create({"service.name": "fastapi-app"})
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Add OTLP exporter
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

# Instrument SQLAlchemy
SQLAlchemyInstrumentor().instrument(engine=engine)
```

### Auto-instrumentation (Easier)

```bash
# Install auto-instrumentation
pip install opentelemetry-bootstrap
opentelemetry-bootstrap -a install

# Run with auto-instrumentation
opentelemetry-instrument \
  --traces_exporter otlp \
  --metrics_exporter otlp \
  --service_name fastapi-app \
  --exporter_otlp_endpoint http://localhost:4317 \
  python main.py
```

## Troubleshooting

### Collector Not Receiving Data

1. Check collector health:
   ```bash
   curl http://localhost:13133/health/status
   ```

2. Check collector logs:
   ```bash
   docker logs fastapi-otel-collector
   ```

### Jaeger Not Showing Traces

1. Verify collector is sending to Jaeger:
   ```bash
   docker logs fastapi-otel-collector | grep jaeger
   ```

2. Check Jaeger logs:
   ```bash
   docker logs fastapi-jaeger
   ```

### Prometheus Not Scraping Metrics

1. Check Prometheus targets:
   - Open http://localhost:9090/targets
   - Ensure all targets are "UP"

2. Check Prometheus logs:
   ```bash
   docker logs fastapi-prometheus
   ```

## Production Considerations

For production deployments:

1. **Security**:
   - Change Grafana admin password
   - Enable authentication on all services
   - Use TLS/SSL for all connections
   - Restrict network access with firewall rules

2. **Scalability**:
   - Use separate collector instances per environment
   - Consider Jaeger distributed deployment
   - Use Prometheus federation or Thanos for multi-cluster

3. **Retention**:
   - Configure appropriate retention periods
   - Set up backup strategies
   - Monitor disk usage

4. **High Availability**:
   - Run multiple collector instances with load balancer
   - Use Prometheus HA pairs
   - Deploy Grafana in HA mode

## Quick Reference

### Service URLs (Local Development)
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686
- **Prometheus**: http://localhost:9090
- **Mailpit**: http://localhost:8025
- **Temporal**: http://localhost:8080

### Makefile Commands
```bash
make docker-up-telemetry    # Start telemetry stack
make docker-down            # Stop all services
make open-grafana           # Open Grafana UI
make open-jaeger            # Open Jaeger UI
```

---

## Additional Resources

- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)

---

## 🔗 Related Documentation

- ✅ **Completed**: [README](../README.md) - Overview
- ✅ **Completed**: [GUIDE](../GUIDE.md) - Setup
- ✅ **Completed**: [ARCHITECTURE](../docs/ARCHITECTURE.md) - System design
- ✅ **Completed**: [SECRETS_MANAGEMENT](../docs/SECRETS_MANAGEMENT.md) - Secure secrets
- ✅ **Current**: **TELEMETRY_SETUP** - Monitoring and observability

---

## 💬 Need Help?

- See [Example Dashboard](#example-dashboard-fastapi-red-metrics) for Grafana dashboard JSON
- Check [Troubleshooting](#troubleshooting) for common issues
- Review [Common Dashboard Panels](#common-dashboard-panels) for useful queries
- Read [Production Considerations](#production-considerations) for deployment guidance
- Open an issue on GitHub for questions
