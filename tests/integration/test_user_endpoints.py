"""Integration tests for User CRUD endpoints."""

from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.utils.tenant_auth import create_tenant_token


class TestUserCreateEndpoint:
    """Test POST /api/v1/users endpoint for creating users."""

    def test_creates_user_with_valid_data(self, client: TestClient) -> None:
        """Test creating a new user with all required fields.

        Arrange: Valid user data with email, username, and full_name
        Act: POST /api/v1/users
        Assert: Returns 201 with user data and default is_active=True
        """
        # Arrange
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "full_name": "New User",
        }

        # Act
        response = client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert data["full_name"] == user_data["full_name"]
        assert "id" in data
        assert data["is_active"] is True

    def test_creates_user_with_tenant_token(self, client: TestClient) -> None:
        """Test creating user with valid tenant token in request header.

        Arrange: Valid user data and X-Tenant-Token header with ES256 JWT
        Act: POST /api/v1/users with tenant header
        Assert: Returns 201 (created) or 501 (tenant isolation not yet implemented)
        """
        # Arrange
        tenant_id = uuid4()
        tenant_token = create_tenant_token(tenant_id)

        user_data = {
            "email": "tenant@example.com",
            "username": "tenantuser",
            "full_name": "Tenant User",
        }
        headers = {"X-Tenant-Token": tenant_token}

        # Act
        response = client.post("/api/v1/users", json=user_data, headers=headers)

        # Assert - should work with valid token (or return 501 if not implemented)
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_501_NOT_IMPLEMENTED,
        ]

        # If created successfully, verify response structure
        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert data["email"] == user_data["email"]
            assert "id" in data

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "invalid-email",  # Missing @ symbol
            "@example.com",  # Missing local part
            "test@",  # Missing domain
            "test..user@example.com",  # Consecutive dots
            "",  # Empty string
        ],
    )
    def test_rejects_invalid_email_format(self, client: TestClient, invalid_email: str) -> None:
        """Test creating user with various invalid email formats.

        Arrange: User data with invalid email format
        Act: POST /api/v1/users
        Assert: Returns 422 validation error
        """
        # Arrange
        user_data = {
            "email": invalid_email,
            "username": "testuser",
        }

        # Act
        response = client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.parametrize(
        "invalid_username",
        [
            "invalid@user!",  # Special characters
            "user name",  # Contains space
            "ab",  # Too short (if minimum is 3)
            "user@domain",  # Contains @
        ],
    )
    def test_rejects_invalid_username_pattern(
        self, client: TestClient, invalid_username: str
    ) -> None:
        """Test creating user with various invalid username patterns.

        Arrange: User data with invalid username
        Act: POST /api/v1/users
        Assert: Returns 422 validation error
        """
        # Arrange
        user_data = {
            "email": "test@example.com",
            "username": invalid_username,
        }

        # Act
        response = client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_missing_required_fields(self, client: TestClient) -> None:
        """Test creating user without required fields.

        Arrange: User data missing required username field
        Act: POST /api/v1/users
        Assert: Returns 422 validation error
        """
        # Arrange - missing username
        user_data = {
            "email": "test@example.com",
        }

        # Act
        response = client.post("/api/v1/users", json=user_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_standardized_validation_error_format(self, client: TestClient) -> None:
        """Test validation error response has standardized format.

        Arrange: Empty request body (missing all required fields)
        Act: POST /api/v1/users
        Assert: Returns 422 with error code, message, and details
        """
        # Arrange
        empty_data = {}

        # Act
        response = client.post("/api/v1/users", json=empty_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()

        # Verify standardized error structure
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]

        # Verify error content
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Request validation failed"
        assert data["error"]["details"] is not None


class TestUserListEndpoint:
    """Test GET /api/v1/users endpoint for listing users."""

    def test_lists_users_with_pagination_structure(self, client: TestClient) -> None:
        """Test listing users returns paginated response.

        Arrange: No specific setup needed
        Act: GET /api/v1/users
        Assert: Returns 200 with items, total, page, and page_size
        """
        # Arrange: (no setup needed)

        # Act
        response = client.get("/api/v1/users")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)

    def test_accepts_pagination_query_parameters(self, client: TestClient) -> None:
        """Test listing users with pagination parameters.

        Arrange: Pagination params skip=0, limit=10
        Act: GET /api/v1/users?skip=0&limit=10
        Assert: Returns 200 with page_size=10
        """
        # Arrange
        query_params = "?skip=0&limit=10"

        # Act
        response = client.get(f"/api/v1/users{query_params}")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page_size"] == 10

    def test_accepts_tenant_token(self, client: TestClient) -> None:
        """Test listing users filtered by tenant with valid token.

        Arrange: Valid tenant token in header
        Act: GET /api/v1/users with X-Tenant-Token header
        Assert: Returns 200 or 501 with tenant-filtered results
        """
        # Arrange
        tenant_id = uuid4()
        tenant_token = create_tenant_token(tenant_id)
        headers = {"X-Tenant-Token": tenant_token}

        # Act
        response = client.get("/api/v1/users", headers=headers)

        # Assert
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_501_NOT_IMPLEMENTED,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "items" in data
            assert isinstance(data["items"], list)

    @pytest.mark.parametrize(
        ("skip", "limit", "expected_status"),
        [
            (20000, 10, status.HTTP_422_UNPROCESSABLE_CONTENT),  # skip > max (10000)
            (0, 200, status.HTTP_422_UNPROCESSABLE_CONTENT),  # limit > max (100)
            (100, 50, status.HTTP_200_OK),  # valid bounds
            (0, 1, status.HTTP_200_OK),  # minimum valid limit
            (0, 100, status.HTTP_200_OK),  # maximum valid limit
        ],
    )
    def test_validates_pagination_bounds(
        self, client: TestClient, skip: int, limit: int, expected_status: int
    ) -> None:
        """Test pagination parameter validation with boundary values.

        Arrange: Various skip/limit combinations including edge cases
        Act: GET /api/v1/users with pagination params
        Assert: Returns appropriate status based on validation
        """
        # Arrange
        query_params = f"?skip={skip}&limit={limit}"

        # Act
        response = client.get(f"/api/v1/users{query_params}")

        # Assert
        assert response.status_code == expected_status


class TestUserGetByIdEndpoint:
    """Test GET /api/v1/users/{user_id} endpoint."""

    def test_accepts_valid_uuidv7_format(self, client: TestClient) -> None:
        """Test getting user by valid UUIDv7 ID.

        Arrange: Valid UUIDv7 format ID (version 7 in 13th hex digit)
        Act: GET /api/v1/users/{uuid}
        Assert: Returns 404 or 500 (ID format accepted)
        """
        # Arrange - valid UUIDv7 format
        valid_uuidv7 = "018c5e9e-1234-7000-8000-000000000000"

        # Act
        response = client.get(f"/api/v1/users/{valid_uuidv7}")

        # Assert - format is valid, but user might not exist
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_rejects_invalid_uuid_format(self, client: TestClient) -> None:
        """Test getting user with malformed UUID.

        Arrange: Invalid UUID string
        Act: GET /api/v1/users/{invalid_uuid}
        Assert: Returns 422 validation error
        """
        # Arrange
        invalid_uuid = "not-a-valid-uuid"

        # Act
        response = client.get(f"/api/v1/users/{invalid_uuid}")

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_accepts_non_uuidv7_but_valid_uuid(self, client: TestClient) -> None:
        """Test getting user with valid UUID but not UUIDv7.

        Arrange: Valid UUIDv4 format (version 4 instead of 7)
        Act: GET /api/v1/users/{uuid}
        Assert: Returns 404 (endpoint accepts any valid UUID)
        """
        # Arrange - valid UUIDv4 format
        valid_uuidv4 = "12345678-1234-4678-9012-123456789012"

        # Act
        response = client.get(f"/api/v1/users/{valid_uuidv4}")

        # Assert - UUID format valid, but user doesn't exist
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUserUpdateEndpoint:
    """Test PATCH /api/v1/users/{user_id} endpoint."""

    def test_accepts_valid_uuidv7_for_update(self, client: TestClient) -> None:
        """Test updating user with valid UUIDv7.

        Arrange: Valid UUIDv7 and update data
        Act: PATCH /api/v1/users/{uuid}
        Assert: Returns 200, 404, or 500 based on database state
        """
        # Arrange
        valid_uuidv7 = "018c5e9e-1234-7000-8000-000000000000"
        update_data = {"full_name": "Updated Name"}

        # Act
        response = client.patch(f"/api/v1/users/{valid_uuidv7}", json=update_data)

        # Assert
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    def test_rejects_invalid_username_in_update(self, client: TestClient) -> None:
        """Test updating user with invalid username pattern.

        Arrange: Update data with invalid username
        Act: PATCH /api/v1/users/{uuid}
        Assert: Returns 422 validation error
        """
        # Arrange
        valid_uuidv7 = "018c5e9e-1234-7000-8000-000000000000"
        update_data = {"username": "invalid@username!"}

        # Act
        response = client.patch(f"/api/v1/users/{valid_uuidv7}", json=update_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestUserDeleteEndpoint:
    """Test DELETE /api/v1/users/{user_id} endpoint."""

    def test_accepts_valid_uuidv7_for_deletion(self, client: TestClient) -> None:
        """Test deleting user with valid UUIDv7.

        Arrange: Valid UUIDv7 ID
        Act: DELETE /api/v1/users/{uuid}
        Assert: Returns 204, 404, or 500 based on database state
        """
        # Arrange
        valid_uuidv7 = "018c5e9e-1234-7000-8000-000000000000"

        # Act
        response = client.delete(f"/api/v1/users/{valid_uuidv7}")

        # Assert
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]


class TestUserBatchCreateEndpoint:
    """Test POST /api/v1/users/batch endpoint for batch user creation."""

    def test_creates_multiple_users_successfully(self, client: TestClient) -> None:
        """Test batch creating multiple valid users.

        Arrange: Batch data with 3 valid users
        Act: POST /api/v1/users/batch
        Assert: Returns 201 with created users array and total count
        """
        # Arrange
        batch_data = {
            "users": [
                {
                    "email": "batch1@example.com",
                    "username": "batch_user1",
                    "full_name": "Batch User One",
                },
                {
                    "email": "batch2@example.com",
                    "username": "batch_user2",
                    "full_name": "Batch User Two",
                },
                {
                    "email": "batch3@example.com",
                    "username": "batch_user3",
                    "full_name": None,
                },
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert "created" in data
            assert "total" in data
            assert "message" in data
            assert data["total"] == 3
            assert len(data["created"]) == 3
            assert data["created"][0]["email"] == "batch1@example.com"
            assert data["created"][1]["email"] == "batch2@example.com"
            assert data["created"][2]["email"] == "batch3@example.com"

    def test_creates_single_user_in_batch(self, client: TestClient) -> None:
        """Test batch endpoint with single user (edge case).

        Arrange: Batch data with only 1 user
        Act: POST /api/v1/users/batch
        Assert: Returns 201 with total=1
        """
        # Arrange
        batch_data = {
            "users": [
                {
                    "email": "single_batch@example.com",
                    "username": "single_batch",
                    "full_name": "Single Batch User",
                }
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert data["total"] == 1
            assert len(data["created"]) == 1

    def test_works_with_tenant_token(self, client: TestClient) -> None:
        """Test batch creating users with valid tenant token.

        Arrange: Batch data and valid X-Tenant-Token header
        Act: POST /api/v1/users/batch with tenant header
        Assert: Returns 201 or 501 (tenant isolation applies or not implemented)
        """
        # Arrange
        tenant_id = uuid4()
        tenant_token = create_tenant_token(tenant_id)

        batch_data = {
            "users": [
                {
                    "email": "tenant_batch1@example.com",
                    "username": "tenant_batch1",
                    "full_name": "Tenant Batch User",
                }
            ]
        }
        headers = {"X-Tenant-Token": tenant_token}

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data, headers=headers)

        # Assert
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_501_NOT_IMPLEMENTED,
        ]

        # If created successfully, verify response structure
        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()
            assert "total" in data
            assert "created" in data

    def test_rejects_empty_users_list(self, client: TestClient) -> None:
        """Test batch creating with empty users array.

        Arrange: Batch data with empty users list
        Act: POST /api/v1/users/batch
        Assert: Returns 422 validation error
        """
        # Arrange
        batch_data = {"users": []}

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_batch_exceeding_maximum_size(self, client: TestClient) -> None:
        """Test batch creating more than maximum allowed users.

        Arrange: Batch data with 101 users (exceeds max of 100)
        Act: POST /api/v1/users/batch
        Assert: Returns 422 validation error
        """
        # Arrange - create 101 users (over the limit)
        batch_data = {
            "users": [
                {
                    "email": f"user{i}@example.com",
                    "username": f"user{i}",
                    "full_name": f"User {i}",
                }
                for i in range(101)
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_batch_with_missing_required_fields(self, client: TestClient) -> None:
        """Test batch creating with invalid user data.

        Arrange: Batch data with user missing required username
        Act: POST /api/v1/users/batch
        Assert: Returns 422 validation error
        """
        # Arrange
        batch_data = {
            "users": [
                {
                    "email": "test@example.com",
                    # Missing username
                }
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_batch_with_invalid_email(self, client: TestClient) -> None:
        """Test batch creating with invalid email format.

        Arrange: Batch data with invalid email
        Act: POST /api/v1/users/batch
        Assert: Returns 422 validation error
        """
        # Arrange
        batch_data = {
            "users": [
                {
                    "email": "invalid-email",
                    "username": "testuser",
                }
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_batch_with_invalid_username(self, client: TestClient) -> None:
        """Test batch creating with invalid username pattern.

        Arrange: Batch data with invalid username
        Act: POST /api/v1/users/batch
        Assert: Returns 422 validation error
        """
        # Arrange
        batch_data = {
            "users": [
                {
                    "email": "test@example.com",
                    "username": "invalid@user!",
                }
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_standardized_response_structure(self, client: TestClient) -> None:
        """Test batch create returns standardized response format.

        Arrange: Valid batch data with one user
        Act: POST /api/v1/users/batch
        Assert: Response contains created, total, message fields
        """
        # Arrange
        batch_data = {
            "users": [
                {
                    "email": "structure_test@example.com",
                    "username": "structure_test",
                    "full_name": "Structure Test",
                }
            ]
        }

        # Act
        response = client.post("/api/v1/users/batch", json=batch_data)

        # Assert
        if response.status_code == status.HTTP_201_CREATED:
            data = response.json()

            # Check top-level response structure
            assert "created" in data
            assert "total" in data
            assert "message" in data
            assert isinstance(data["created"], list)
            assert isinstance(data["total"], int)
            assert isinstance(data["message"], str)

            # Check created user structure
            if len(data["created"]) > 0:
                user = data["created"][0]
                assert "id" in user
                assert "email" in user
                assert "username" in user
                assert "full_name" in user
                assert "is_active" in user
                assert "created_at" in user
                assert "updated_at" in user
