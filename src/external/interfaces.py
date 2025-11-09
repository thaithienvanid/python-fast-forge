"""External service interface definitions.

This module defines abstract interfaces for external services (email, SMS, etc.),
enabling dependency injection and facilitating testing with mock implementations.
"""

from abc import ABC, abstractmethod


class IEmailService(ABC):
    """Abstract interface for email service providers.

    Defines the contract for sending emails through various providers
    (SendGrid, AWS SES, SMTP, etc.) while keeping the domain layer
    provider-agnostic.
    """

    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email message to a recipient.

        Args:
            to: Recipient email address
            subject: Email subject line
            body: Email body content (plain text or HTML)

        Returns:
            True if email was sent successfully, False otherwise

        Note:
            Implementations should handle provider-specific errors and
            return False rather than raising exceptions for delivery failures.
        """
