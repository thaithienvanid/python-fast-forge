# syntax=docker/dockerfile:1

# ===================================
# Stage 1: Builder - Install dependencies
# ===================================
FROM python:3.13-slim AS builder

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.5.18

WORKDIR /app

# Copy dependency files (lock file ensures reproducible builds)
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync (respects lock file for reproducibility)
# --frozen ensures lock file is used without modification
# --no-dev excludes development dependencies for production
RUN uv sync --frozen --no-dev

# ===================================
# Stage 2: Runtime - Minimal image
# ===================================
FROM python:3.13-slim

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser && \
    chown -R appuser:appuser /app

# Use non-root user
USER appuser

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Metadata labels
LABEL org.opencontainers.image.title="Python FastAPI Boilerplate"
LABEL org.opencontainers.image.description="Production-ready FastAPI boilerplate with clean architecture"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.authors="thaithienvanid"

# Run the application
CMD ["python", "main.py"]
