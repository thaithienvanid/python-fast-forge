"""External services configuration including email, SMS, etc."""

from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ExternalServicesSettings(BaseSettings):
    """External service integrations configuration.

    Handles API keys and configuration for third-party services
    like email providers, SMS gateways, payment processors, etc.
    """

    # Email provider configuration
    email_provider: Literal["smtp", "sendgrid", "ses", "mailgun"] = Field(
        default="smtp",
        alias="EMAIL_PROVIDER",
        description="Email provider to use (smtp, sendgrid, ses, mailgun)",
    )

    # SMTP Configuration (for email_provider=smtp)
    smtp_host: str = Field(
        default="localhost",
        alias="SMTP_HOST",
        description="SMTP server hostname",
    )
    smtp_port: int = Field(
        default=587,
        alias="SMTP_PORT",
        description="SMTP server port (587 for TLS, 465 for SSL)",
    )
    smtp_username: str = Field(
        default="",
        alias="SMTP_USERNAME",
        description="SMTP username",
    )
    smtp_password: str = Field(
        default="",
        alias="SMTP_PASSWORD",
        description="SMTP password",
    )
    smtp_use_tls: bool = Field(
        default=True,
        alias="SMTP_USE_TLS",
        description="Use TLS for SMTP connection",
    )
    smtp_use_ssl: bool = Field(
        default=False,
        alias="SMTP_USE_SSL",
        description="Use SSL for SMTP connection",
    )

    # Email sender configuration
    email_from_address: str = Field(
        default="noreply@example.com",
        alias="EMAIL_FROM_ADDRESS",
        description="Default sender email address",
    )
    email_from_name: str = Field(
        default="Python Fast Forge",
        alias="EMAIL_FROM_NAME",
        description="Default sender name",
    )

    # SendGrid/Other API-based providers
    email_api_key: str = Field(
        default="dev-email-api-key-UNSAFE",
        alias="EMAIL_API_KEY",
        description="Email API key (for SendGrid, SES, Mailgun) - MUST be set in production",
    )

    # Environment flag (needed for validation)
    is_production: bool = Field(
        default=False,
        description="Production environment flag (set internally)",
    )

    @field_validator("email_api_key")
    @classmethod
    def validate_email_api_key(cls, v: str, info: Any) -> str:
        """Validate email API key in production for API-based providers."""
        is_production = info.data.get("is_production", False)
        email_provider = info.data.get("email_provider", "smtp")

        # Only validate API key for API-based providers
        if (
            is_production
            and email_provider in ["sendgrid", "ses", "mailgun"]
            and ("dev-email" in v.lower() or "unsafe" in v.lower())
        ):
            raise ValueError(
                f"EMAIL_API_KEY must be set to a real API key in production for {email_provider}. "
                "Default development key is not allowed."
            )
        return v
