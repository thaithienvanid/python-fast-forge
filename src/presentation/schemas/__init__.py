"""API schemas."""

from src.presentation.schemas.error import ErrorDetail, ErrorResponse
from src.presentation.schemas.user import (
    UserBase,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)


__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "UserBase",
    "UserCreate",
    "UserListResponse",
    "UserResponse",
    "UserUpdate",
]
