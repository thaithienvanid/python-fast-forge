"""Error response schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Any | None = Field(None, description="Additional error details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "ENTITY_NOT_FOUND",
                    "message": "User with ID 123 not found",
                    "details": None,
                },
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": [
                        {
                            "loc": ["body", "email"],
                            "msg": "value is not a valid email address",
                            "type": "value_error.email",
                        }
                    ],
                },
            ]
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: ErrorDetail = Field(..., description="Error information")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": {
                        "code": "ENTITY_NOT_FOUND",
                        "message": "User with ID 123 not found",
                        "details": None,
                    }
                }
            ]
        }
    }
