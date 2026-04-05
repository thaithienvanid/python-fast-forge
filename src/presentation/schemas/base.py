"""Base response schemas for API endpoints."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """Standard API response format.

    This provides a consistent response structure across all API endpoints.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable message
        data: Response payload (optional)

    Example:
        ```python
        return BaseResponse(
            success=True, message="User created successfully", data={"user_id": "123"}
        )
        ```
    """

    success: bool = Field(description="Whether operation succeeded")
    message: str = Field(description="Human-readable message")
    data: T | dict[str, Any] | None = Field(default=None, description="Response payload")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response format.

    Attributes:
        items: List of items in current page
        total: Total number of items
        page: Current page number
        page_size: Number of items per page
        pages: Total number of pages

    Example:
        ```python
        return PaginatedResponse(
            items=[user1, user2, user3], total=100, page=1, page_size=10, pages=10
        )
        ```
    """

    items: list[T] = Field(description="Items in current page")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")
