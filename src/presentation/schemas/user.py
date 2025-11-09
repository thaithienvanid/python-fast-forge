"""User API request and response schemas.

This module defines Pydantic models for user-related API operations,
including validation rules, serialization, and OpenAPI documentation examples.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema with common fields shared across operations.

    Contains core user attributes used in both create and response schemas,
    ensuring consistent validation rules.
    """

    email: EmailStr = Field(..., description="User email address (must be valid email format)")
    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Username (3-100 chars, alphanumeric with underscores/hyphens only)",
    )
    full_name: str | None = Field(None, max_length=255, description="User's full display name")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str | None:
        """Sanitize full name by removing control characters.

        Control characters (ASCII < 32) are stripped to prevent:
        - Text rendering issues
        - Terminal escape sequence injection
        - Data export format corruption

        Args:
            v: Raw full name input

        Returns:
            Sanitized full name with control characters removed
        """
        if v:
            v = "".join(c for c in v if ord(c) >= 32)
        return v


class UserCreate(UserBase):
    """Request schema for creating a new user.

    Inherits validation from UserBase and adds OpenAPI documentation examples.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "john.doe@example.com",
                    "username": "johndoe",
                    "full_name": "John Doe",
                },
                {
                    "email": "jane.smith@company.com",
                    "username": "janesmith",
                    "full_name": None,
                },
            ]
        }
    }


class UserUpdate(BaseModel):
    """Request schema for updating an existing user.

    All fields are optional to support partial updates (PATCH semantics).
    """

    email: EmailStr | None = Field(None, description="New email address (must be valid)")
    username: str | None = Field(
        None,
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="New username (3-100 chars, alphanumeric with underscores/hyphens)",
    )
    full_name: str | None = Field(None, max_length=255, description="New full display name")
    is_active: bool | None = Field(None, description="Account activation status")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "newemail@example.com",
                    "full_name": "Updated Name",
                },
                {
                    "username": "newusername",
                    "is_active": False,
                },
            ]
        }
    }


class UserResponse(UserBase):
    """Response schema for user data.

    Extends UserBase with read-only fields (ID, timestamps, status) that
    are populated by the system.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "018c5e9e-1234-7000-8000-000000000001",
                    "email": "john.doe@example.com",
                    "username": "johndoe",
                    "full_name": "John Doe",
                    "is_active": True,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:00Z",
                }
            ]
        },
    )

    id: UUID = Field(..., description="Unique user identifier (UUIDv7)")
    is_active: bool = Field(..., description="Whether user account is active")
    created_at: datetime = Field(..., description="User creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last modification timestamp (UTC)")


class UserListResponse(BaseModel):
    """Response schema for paginated user lists.

    Contains user items plus pagination metadata for client navigation.
    """

    items: list[UserResponse] = Field(..., description="Users in current page")
    total: int = Field(..., description="Total number of users in this page")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [
                        {
                            "id": "018c5e9e-1234-7000-8000-000000000001",
                            "email": "user1@example.com",
                            "username": "user1",
                            "full_name": "User One",
                            "is_active": True,
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z",
                        },
                        {
                            "id": "018c5e9e-1234-7000-8000-000000000002",
                            "email": "user2@example.com",
                            "username": "user2",
                            "full_name": "User Two",
                            "is_active": True,
                            "created_at": "2024-01-15T11:00:00Z",
                            "updated_at": "2024-01-15T11:00:00Z",
                        },
                    ],
                    "total": 2,
                    "page": 1,
                    "page_size": 20,
                }
            ]
        }
    }


class BatchUserCreate(BaseModel):
    """Request schema for batch user creation.

    Allows creating multiple users in a single transaction (1-100 users).
    """

    users: list[UserCreate] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of users to create (minimum 1, maximum 100 for performance)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "users": [
                        {
                            "email": "user1@example.com",
                            "username": "user1",
                            "full_name": "User One",
                        },
                        {
                            "email": "user2@example.com",
                            "username": "user2",
                            "full_name": "User Two",
                        },
                        {
                            "email": "user3@example.com",
                            "username": "user3",
                            "full_name": None,
                        },
                    ]
                }
            ]
        }
    }


class BatchUserCreateResponse(BaseModel):
    """Response schema for batch user creation results.

    Returns successfully created users with transaction metadata.
    """

    created: list[UserResponse] = Field(..., description="Successfully created users")
    total: int = Field(..., description="Total number of users created")
    message: str = Field(..., description="Operation success message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "created": [
                        {
                            "id": "018c5e9e-1234-7000-8000-000000000001",
                            "email": "user1@example.com",
                            "username": "user1",
                            "full_name": "User One",
                            "is_active": True,
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z",
                        },
                        {
                            "id": "018c5e9e-1234-7000-8000-000000000002",
                            "email": "user2@example.com",
                            "username": "user2",
                            "full_name": "User Two",
                            "is_active": True,
                            "created_at": "2024-01-15T10:30:01Z",
                            "updated_at": "2024-01-15T10:30:01Z",
                        },
                    ],
                    "total": 2,
                    "message": "Successfully created 2 user(s) in a single transaction",
                }
            ]
        }
    }
