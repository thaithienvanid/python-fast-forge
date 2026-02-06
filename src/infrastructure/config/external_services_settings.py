"""External services configuration including email, SMS, etc."""

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ExternalServicesSettings(BaseSettings):
    """External service integrations configuration.

    Handles API keys and configuration for third-party services
    like email providers, SMS gateways, payment processors, etc.
    """

    email_api_key: str = Field(
        default="dev-email-api-key-UNSAFE",
        alias="EMAIL_API_KEY",
        description="Email API key - MUST be set in production",
    )

    # Environment flag (needed for validation)
    is_production: bool = Field(
        default=False,
        description="Production environment flag (set internally)",
    )

    @field_validator("email_api_key")
    @classmethod
    def validate_email_api_key(cls, v: str, info: Any) -> str:
        """Validate email API key in production."""
        is_production = info.data.get("is_production", False)
        if is_production and ("dev-email" in v.lower() or "unsafe" in v.lower()):
            raise ValueError(
                "EMAIL_API_KEY must be set to a real API key in production. "
                "Default development key is not allowed."
            )
        return v
