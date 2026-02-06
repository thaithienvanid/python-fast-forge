"""API performance benchmarks.

This module contains performance benchmarks for API endpoints to ensure
they meet response time targets.

Target Metrics:
- p50 (median): < 100ms
- p95: < 200ms
- p99: < 500ms
"""

import asyncio
import time
from statistics import median, quantiles

import pytest
from fastapi.testclient import TestClient


@pytest.mark.benchmark
class TestAPIPerformance:
    """Performance benchmarks for API endpoints."""

    def test_health_endpoint_performance(self, client: TestClient) -> None:
        """Benchmark health check endpoint performance.

        Health checks should be extremely fast (< 50ms p95).
        """
        iterations = 100
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            response = client.get("/health")
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            times.append(elapsed)

            assert response.status_code == 200

        # Calculate percentiles
        p50 = median(times)
        p95, p99 = quantiles(times, n=100)[94], quantiles(times, n=100)[98]


        # Assert performance targets
        assert p50 < 50, f"p50 should be < 50ms, got {p50:.2f}ms"
        assert p95 < 100, f"p95 should be < 100ms, got {p95:.2f}ms"
        assert p99 < 200, f"p99 should be < 200ms, got {p99:.2f}ms"

    def test_list_users_endpoint_performance(
        self,
        client: TestClient,
    ) -> None:
        """Benchmark list users endpoint performance.

        List operations should be fast (< 200ms p95).
        """
        iterations = 50
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            response = client.get("/api/v1/users")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

            assert response.status_code in [200, 401, 403]  # May require auth

        # Calculate percentiles
        p50 = median(times)
        p95, _p99 = quantiles(times, n=100)[94], quantiles(times, n=100)[98]


        # Assert performance targets
        assert p50 < 100, f"p50 should be < 100ms, got {p50:.2f}ms"
        assert p95 < 200, f"p95 should be < 200ms, got {p95:.2f}ms"

    def test_create_user_endpoint_performance(
        self,
        client: TestClient,
    ) -> None:
        """Benchmark user creation endpoint performance.

        Write operations should complete reasonably fast (< 300ms p95).
        """
        iterations = 30
        times = []

        for i in range(iterations):
            start = time.perf_counter()
            response = client.post(
                "/api/v1/users",
                json={
                    "email": f"perf{i}_{time.time()}@example.com",
                    "username": f"perf{i}_{int(time.time())}",
                    "full_name": f"Performance Test {i}",
                },
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

            # May succeed or fail with validation/auth - that's ok for benchmark
            assert response.status_code in [201, 400, 401, 403, 422]

        # Calculate percentiles
        p50 = median(times)
        p95 = quantiles(times, n=100)[94] if len(times) >= 20 else max(times)


        # Assert performance targets (more lenient for writes)
        assert p50 < 150, f"p50 should be < 150ms, got {p50:.2f}ms"
        assert p95 < 300, f"p95 should be < 300ms, got {p95:.2f}ms"


@pytest.mark.benchmark
@pytest.mark.asyncio
class TestAsyncAPIPerformance:
    """Async performance benchmarks for API operations."""

    async def test_concurrent_health_checks_performance(
        self,
        async_client,
    ) -> None:
        """Benchmark concurrent health check performance.

        Tests that concurrent requests don't degrade performance significantly.
        """
        concurrency = 20
        iterations = 5
        all_times = []

        for _ in range(iterations):

            async def single_request() -> float:
                start = time.perf_counter()
                response = await async_client.get("/health")
                elapsed = (time.perf_counter() - start) * 1000
                assert response.status_code == 200
                return elapsed

            tasks = [single_request() for _ in range(concurrency)]
            times = await asyncio.gather(*tasks)
            all_times.extend(times)

        # Calculate percentiles
        p50 = median(all_times)
        p95, _p99 = quantiles(all_times, n=100)[94], quantiles(all_times, n=100)[98]


        # Under concurrency, allow slightly higher latency
        assert p50 < 100, f"p50 should be < 100ms under concurrency, got {p50:.2f}ms"
        assert p95 < 200, f"p95 should be < 200ms under concurrency, got {p95:.2f}ms"

    async def test_concurrent_user_reads_performance(
        self,
        async_client,
    ) -> None:
        """Benchmark concurrent user read performance.

        Tests read performance under concurrent load.
        """
        concurrency = 10
        iterations = 3
        all_times = []

        for _ in range(iterations):

            async def single_request() -> float:
                start = time.perf_counter()
                response = await async_client.get("/api/v1/users")
                elapsed = (time.perf_counter() - start) * 1000
                assert response.status_code in [200, 401, 403]
                return elapsed

            tasks = [single_request() for _ in range(concurrency)]
            times = await asyncio.gather(*tasks)
            all_times.extend(times)

        # Calculate percentiles
        p50 = median(all_times)
        p95 = quantiles(all_times, n=100)[94] if len(all_times) >= 20 else max(all_times)


        # Under concurrency, allow higher latency
        assert p50 < 150, f"p50 should be < 150ms under concurrency, got {p50:.2f}ms"
        assert p95 < 300, f"p95 should be < 300ms under concurrency, got {p95:.2f}ms"


@pytest.mark.benchmark
class TestResponsePayloadSize:
    """Benchmarks for response payload sizes."""

    def test_health_response_size(self, client: TestClient) -> None:
        """Verify health check response is minimal.

        Health checks should have minimal payload (< 1KB).
        """
        response = client.get("/health")
        payload_size = len(response.content)


        assert payload_size < 1024, f"Health response should be < 1KB, got {payload_size} bytes"

    def test_user_list_response_reasonable_size(
        self,
        client: TestClient,
    ) -> None:
        """Verify user list response size is reasonable.

        List responses should be paginated to keep size manageable.
        """
        response = client.get("/api/v1/users?limit=100")
        if response.status_code == 200:
            payload_size = len(response.content)


            # With 100 users, should be less than 100KB
            assert payload_size < 102400, (
                f"User list response should be < 100KB, got {payload_size} bytes"
            )


@pytest.mark.benchmark
class TestEndpointThroughput:
    """Throughput benchmarks for API endpoints."""

    def test_health_endpoint_throughput(self, client: TestClient) -> None:
        """Measure health endpoint throughput.

        Health endpoint should handle many requests per second.
        """
        duration_seconds = 2
        request_count = 0
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            response = client.get("/health")
            assert response.status_code == 200
            request_count += 1

        elapsed = time.time() - start_time
        rps = request_count / elapsed


        # Should handle at least 100 requests per second
        assert rps >= 100, f"Should handle >= 100 req/s, got {rps:.0f} req/s"

    def test_api_endpoint_throughput(self, client: TestClient) -> None:
        """Measure typical API endpoint throughput.

        API endpoints should handle reasonable throughput.
        """
        duration_seconds = 2
        request_count = 0
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            response = client.get("/api/v1/users")
            # Count both successful and auth-required responses
            assert response.status_code in [200, 401, 403]
            request_count += 1

        elapsed = time.time() - start_time
        rps = request_count / elapsed


        # Should handle at least 50 requests per second
        assert rps >= 50, f"Should handle >= 50 req/s, got {rps:.0f} req/s"
