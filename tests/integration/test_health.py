"""Integration tests for health check endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestRootEndpoint:
    """Test root API endpoint.

    The root endpoint provides API documentation links and metadata.
    """

    def test_returns_200_ok(self, client: TestClient) -> None:
        """Test root endpoint returns 200 OK status.

        Arrange: Client is ready
        Act: GET /api/v1/
        Assert: Status is 200 OK
        """
        # Arrange: (client fixture provides pre-configured client)

        # Act
        response = client.get("/api/v1/")

        # Assert
        assert response.status_code == status.HTTP_200_OK

    def test_returns_json_response(self, client: TestClient) -> None:
        """Test root endpoint returns JSON response.

        Arrange: Client is ready
        Act: GET /api/v1/
        Assert: Response is valid JSON
        """
        # Arrange: (client fixture provides pre-configured client)

        # Act
        response = client.get("/api/v1/")

        # Assert
        data = response.json()
        assert isinstance(data, dict)

    def test_includes_welcome_message(self, client: TestClient) -> None:
        """Test root endpoint includes welcome message.

        Arrange: Client is ready
        Act: GET /api/v1/
        Assert: Response contains 'message' field
        """
        # Arrange: (client fixture provides pre-configured client)

        # Act
        response = client.get("/api/v1/")
        data = response.json()

        # Assert
        assert "message" in data

    def test_includes_documentation_links(self, client: TestClient) -> None:
        """Test root endpoint includes documentation links.

        Arrange: Client is ready
        Act: GET /api/v1/
        Assert: Response contains 'docs' field
        """
        # Arrange: (client fixture provides pre-configured client)

        # Act
        response = client.get("/api/v1/")
        data = response.json()

        # Assert
        assert "docs" in data

    def test_includes_health_check_link(self, client: TestClient) -> None:
        """Test root endpoint includes health check link.

        Arrange: Client is ready
        Act: GET /api/v1/
        Assert: Response contains 'health' field
        """
        # Arrange: (client fixture provides pre-configured client)

        # Act
        response = client.get("/api/v1/")
        data = response.json()

        # Assert
        assert "health" in data


class TestHealthCheckEndpoint:
    """Test health check endpoint.

    The health check endpoint provides service health status,
    version information, and database connectivity status.
    """

    def test_returns_200_ok(self, client: TestClient, mocker) -> None:
        """Test health check returns 200 OK status.

        Arrange: Mock database health check to return True
        Act: GET /api/v1/health
        Assert: Status is 200 OK
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK

    def test_returns_json_response(self, client: TestClient, mocker) -> None:
        """Test health check returns JSON response.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: Response is valid JSON
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")

        # Assert
        data = response.json()
        assert isinstance(data, dict)

    def test_includes_healthy_status(self, client: TestClient, mocker) -> None:
        """Test health check includes 'healthy' status.

        Arrange: Mock database health check to return True
        Act: GET /api/v1/health
        Assert: Status field is 'healthy'
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")
        data = response.json()

        # Assert
        assert data["status"] == "healthy"

    def test_includes_version_field(self, client: TestClient, mocker) -> None:
        """Test health check includes version information.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: Response contains 'version' field
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")
        data = response.json()

        # Assert
        assert "version" in data

    def test_includes_environment_field(self, client: TestClient, mocker) -> None:
        """Test health check includes environment information.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: Response contains 'environment' field
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")
        data = response.json()

        # Assert
        assert "environment" in data

    def test_includes_database_status(self, client: TestClient, mocker) -> None:
        """Test health check includes database status.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: Response contains 'database' field
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")
        data = response.json()

        # Assert
        assert "database" in data

    def test_verifies_all_required_fields_present(self, client: TestClient, mocker) -> None:
        """Test health check has all required fields.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: All required fields are present
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )
        required_fields = ["status", "version", "environment", "database"]

        # Act
        response = client.get("/api/v1/health")
        data = response.json()

        # Assert
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"


class TestHealthCheckAsync:
    """Test health check endpoint with async client.

    Verifies the endpoint works correctly with async HTTP clients.
    """

    @pytest.mark.asyncio
    async def test_returns_200_ok_with_async_client(
        self, async_client: AsyncClient, mocker
    ) -> None:
        """Test health check returns 200 OK with async client.

        Arrange: Mock database health check
        Act: GET /api/v1/health with async client
        Assert: Status is 200 OK
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = await async_client.get("/api/v1/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_includes_healthy_status_with_async_client(
        self, async_client: AsyncClient, mocker
    ) -> None:
        """Test health check status with async client.

        Arrange: Mock database health check
        Act: GET /api/v1/health with async client
        Assert: Status is 'healthy'
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = await async_client.get("/api/v1/health")
        data = response.json()

        # Assert
        assert data["status"] == "healthy"


class TestTraceIDHeader:
    """Test X-Trace-ID header in responses.

    The X-Trace-ID header provides request tracking for observability.
    """

    def test_includes_trace_id_in_response_headers(self, client: TestClient, mocker) -> None:
        """Test health check response includes X-Trace-ID header.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: X-Trace-ID header is present
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")

        # Assert
        assert "X-Trace-ID" in response.headers

    def test_trace_id_is_not_empty(self, client: TestClient, mocker) -> None:
        """Test X-Trace-ID header has non-empty value.

        Arrange: Mock database health check
        Act: GET /api/v1/health
        Assert: X-Trace-ID value is non-empty
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response = client.get("/api/v1/health")
        trace_id = response.headers.get("X-Trace-ID")

        # Assert
        assert trace_id is not None
        assert len(trace_id) > 0

    def test_trace_id_is_unique_per_request(self, client: TestClient, mocker) -> None:
        """Test each request gets a unique X-Trace-ID.

        Arrange: Mock database health check
        Act: Make two requests to /api/v1/health
        Assert: Each response has different X-Trace-ID
        """
        # Arrange
        mock_health_check = mocker.AsyncMock(return_value=True)
        mocker.patch(
            "src.infrastructure.persistence.database.Database.health_check", mock_health_check
        )

        # Act
        response1 = client.get("/api/v1/health")
        response2 = client.get("/api/v1/health")
        trace_id1 = response1.headers.get("X-Trace-ID")
        trace_id2 = response2.headers.get("X-Trace-ID")

        # Assert
        assert trace_id1 != trace_id2
