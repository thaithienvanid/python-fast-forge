"""Performance benchmarks for API and database operations.

Run benchmarks with:
    pytest tests/benchmarks/ -v
    pytest -m benchmark

Benchmark targets:
- API p95 response time: < 200ms
- Database query p95: < 50ms
- Health check p95: < 50ms
"""
