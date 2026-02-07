"""Email service for sending emails using configured provider.

This service provides a high-level interface for sending emails
throughout the application. It automatically uses the configured
email provider (SMTP, SendGrid, SES, Mailgun) based on settings.

Example:
    >>> from src.infrastructure.services.email_service import get_email_service
    >>>
    >>> service = get_email_service()
    >>> await service.send_email(
    ...     to="user@example.com",
    ...     subject="Welcome!",
    ...     body="<h1>Hello World</h1>",
    ...     html=True,
    ... )
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import lru_cache
from typing import Any

from src.infrastructure.config import get_settings
from src.infrastructure.logging.config import get_logger

logger = get_logger(__name__)


class EmailService:
    """Email service for sending emails.

    Automatically uses the configured email provider from settings.
    Currently supports SMTP with graceful degradation for development.

    Attributes:
        _config: External services configuration
        _provider: Email provider name (smtp, sendgrid, etc.)

    Example:
        >>> service = EmailService()
        >>> await service.send_email(
        ...     to="user@example.com",
        ...     subject="Test",
        ...     body="Hello",
        ... )
    """

    def __init__(self):
        """Initialize email service with configuration."""
        settings = get_settings()
        self._config = settings.external_services
        self._provider = self._config.email_provider

        logger.info(
            "email_service_initialized",
            provider=self._provider,
            from_address=self._config.email_from_address,
        )

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
    ) -> str:
        """Send email to recipients.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Email body (text or HTML)
            html: Whether body is HTML
            cc: CC recipients
            bcc: BCC recipients
            reply_to: Reply-to address

        Returns:
            Message ID

        Raises:
            Exception: If email sending fails

        Example:
            >>> message_id = await service.send_email(
            ...     to="user@example.com",
            ...     subject="Welcome to Python Fast Forge",
            ...     body="<h1>Welcome!</h1><p>Thanks for joining.</p>",
            ...     html=True,
            ... )
        """
        if self._provider == "smtp":
            return await self._send_via_smtp(
                to=to,
                subject=subject,
                body=body,
                html=html,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
            )
        elif self._provider == "sendgrid":
            return await self._send_via_sendgrid(
                to=to,
                subject=subject,
                body=body,
                html=html,
                cc=cc,
                bcc=bcc,
                reply_to=reply_to,
            )
        else:
            raise ValueError(f"Unsupported email provider: {self._provider}")

    async def _send_via_smtp(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
    ) -> str:
        """Send email via SMTP.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Email body
            html: Whether body is HTML
            cc: CC recipients
            bcc: BCC recipients
            reply_to: Reply-to address

        Returns:
            Message ID
        """
        # Normalize recipients
        to_list = [to] if isinstance(to, str) else to

        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = (
            f"{self._config.email_from_name} <{self._config.email_from_address}>"
            if self._config.email_from_name
            else self._config.email_from_address
        )
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to

        # Attach body
        mime_type = "html" if html else "plain"
        msg.attach(MIMEText(body, mime_type))

        # Development mode: just log the email
        if self._config.smtp_host == "localhost" and not self._config.smtp_username:
            logger.info(
                "email_simulated",
                to=to_list,
                subject=subject,
                message="SMTP not configured, simulating email send (development mode)",
            )
            return "simulated-message-id"

        # Production mode: send via SMTP
        try:
            if self._config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(
                    self._config.smtp_host,
                    self._config.smtp_port,
                )
            else:
                server = smtplib.SMTP(
                    self._config.smtp_host,
                    self._config.smtp_port,
                )

            if self._config.smtp_use_tls and not self._config.smtp_use_ssl:
                server.starttls()

            if self._config.smtp_username and self._config.smtp_password:
                server.login(
                    self._config.smtp_username,
                    self._config.smtp_password,
                )

            # All recipients
            all_recipients = to_list.copy()
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            server.sendmail(
                self._config.email_from_address,
                all_recipients,
                msg.as_string(),
            )
            server.quit()

            message_id = msg.get("Message-ID", "unknown")

            logger.info(
                "email_sent",
                to=to_list,
                subject=subject,
                message_id=message_id,
                provider="smtp",
            )

            return message_id

        except Exception as e:
            logger.error(
                "email_send_failed",
                to=to_list,
                subject=subject,
                error=str(e),
                provider="smtp",
            )
            raise

    async def _send_via_sendgrid(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
    ) -> str:
        """Send email via SendGrid API.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Email body
            html: Whether body is HTML
            cc: CC recipients
            bcc: BCC recipients
            reply_to: Reply-to address

        Returns:
            Message ID from SendGrid
        """
        # Placeholder for SendGrid implementation
        # This will be completed when SendGrid plugin is finished
        logger.warning(
            "sendgrid_not_implemented",
            message="SendGrid provider not yet implemented, falling back to SMTP",
        )
        return await self._send_via_smtp(
            to=to,
            subject=subject,
            body=body,
            html=html,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
        )


@lru_cache
def get_email_service() -> EmailService:
    """Get singleton email service instance.

    Returns:
        EmailService instance

    Example:
        >>> service = get_email_service()
        >>> await service.send_email(...)
    """
    return EmailService()


__all__ = [
    "EmailService",
    "get_email_service",
]
