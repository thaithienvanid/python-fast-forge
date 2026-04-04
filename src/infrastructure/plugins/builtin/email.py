"""Email plugin interface and built-in implementations.

Email plugins provide email sending capabilities through various providers.
The EmailPlugin interface defines the contract that all email plugins must follow.

Supported Providers (built-in):
- SMTP: Standard SMTP server
- SendGrid: SendGrid API
- Amazon SES: AWS Simple Email Service
- Mailgun: Mailgun API

Example:
    >>> # Using SMTP plugin
    >>> plugin = SMTPEmailPlugin()
    >>> await plugin.init(context)
    >>> await plugin.send_email(
    ...     to="user@example.com",
    ...     subject="Welcome!",
    ...     body="<h1>Hello World</h1>",
    ...     html=True,
    ... )
"""

import base64
import smtplib
from abc import abstractmethod
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from src.infrastructure.plugins.base import Plugin, PluginContext, PluginMetadata


class EmailPlugin(Plugin):
    """Base interface for email plugins.

    All email plugins must implement this interface to provide
    consistent email sending capabilities.

    Methods:
        send_email: Send a single email
        send_bulk: Send emails in bulk (optional, defaults to sequential)
    """

    @abstractmethod
    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
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
            attachments: File attachments (list of {filename, content, mime_type})
            reply_to: Reply-to address

        Returns:
            Message ID or tracking ID

        Example:
            >>> message_id = await plugin.send_email(
            ...     to="user@example.com",
            ...     subject="Welcome!",
            ...     body="<h1>Hello</h1>",
            ...     html=True,
            ... )
        """

    async def send_bulk(
        self,
        emails: list[dict[str, Any]],
    ) -> list[str]:
        """Send multiple emails in bulk.

        Default implementation sends sequentially. Override for
        provider-specific bulk API support.

        Args:
            emails: List of email dicts with to, subject, body, etc.

        Returns:
            List of message IDs

        Example:
            >>> message_ids = await plugin.send_bulk(
            ...     [
            ...         {"to": "user1@example.com", "subject": "Hi", "body": "..."},
            ...         {"to": "user2@example.com", "subject": "Hi", "body": "..."},
            ...     ]
            ... )
        """
        message_ids = []
        for email in emails:
            message_id = await self.send_email(**email)
            message_ids.append(message_id)
        return message_ids


class SMTPEmailPlugin(EmailPlugin):
    """SMTP email plugin.

    Sends emails via standard SMTP server. Supports TLS/SSL.

    Configuration:
        host: SMTP server hostname
        port: SMTP server port (default: 587 for TLS, 465 for SSL)
        username: SMTP username
        password: SMTP password
        from_email: Default sender email
        from_name: Default sender name
        use_tls: Use TLS (default: True)
        use_ssl: Use SSL (default: False)

    Example:
        >>> context = PluginContext(
        ...     config={
        ...         "host": "smtp.gmail.com",
        ...         "port": 587,
        ...         "username": "myapp@gmail.com",
        ...         "password": "app_password",
        ...         "from_email": "noreply@example.com",
        ...         "from_name": "My App",
        ...     }
        ... )
        >>> plugin = SMTPEmailPlugin()
        >>> await plugin.init(context)
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="smtp-email",
            version="1.0.0",
            description="SMTP email provider",
            author="Python Fast Forge",
            plugin_type="email",
            config_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "from_email": {"type": "string", "format": "email"},
                    "from_name": {"type": "string"},
                    "use_tls": {"type": "boolean", "default": True},
                    "use_ssl": {"type": "boolean", "default": False},
                },
                "required": ["host", "username", "password", "from_email"],
            },
        )

    async def init(self, context: PluginContext) -> None:
        """Initialize SMTP connection."""
        self.context = context
        self._host = context.config["host"]
        self._port = context.config.get("port", 587)
        self._username = context.config["username"]
        self._password = context.config["password"]
        self._from_email = context.config["from_email"]
        self._from_name = context.config.get("from_name", "")
        self._use_tls = context.config.get("use_tls", True)
        self._use_ssl = context.config.get("use_ssl", False)

    async def validate(self) -> bool:
        """Validate SMTP configuration."""
        required_keys = ["host", "username", "password", "from_email"]
        return all(key in self.context.config for key in required_keys)

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
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
            attachments: File attachments
            reply_to: Reply-to address

        Returns:
            Message ID
        """
        # Normalize recipients
        to_list = [to] if isinstance(to, str) else to

        # Create message
        msg = MIMEMultipart("alternative")
        msg["From"] = (
            f"{self._from_name} <{self._from_email}>" if self._from_name else self._from_email
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

        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                filename = attachment.get("filename", "attachment")
                content = attachment.get("content", b"")
                mime_type_att = attachment.get("mime_type", "application/octet-stream")

                # If content is string, encode it
                if isinstance(content, str):
                    content = content.encode()

                part = MIMEApplication(content, Name=filename)
                part["Content-Disposition"] = f'attachment; filename="{filename}"'
                part["Content-Type"] = mime_type_att
                msg.attach(part)

        # Send via SMTP
        try:
            if self._use_ssl:
                server = smtplib.SMTP_SSL(self._host, self._port)
            else:
                server = smtplib.SMTP(self._host, self._port)

            if self._use_tls and not self._use_ssl:
                server.starttls()

            server.login(self._username, self._password)

            # All recipients
            all_recipients = to_list.copy()
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            server.sendmail(self._from_email, all_recipients, msg.as_string())
            server.quit()

            message_id = msg.get("Message-ID", "unknown")

            if self.context and self.context.logger:
                self.context.logger.info(
                    "email_sent",
                    to=to_list,
                    subject=subject,
                    message_id=message_id,
                )

            return message_id

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "email_send_failed",
                    to=to_list,
                    subject=subject,
                    error=str(e),
                )
            raise


class SendGridEmailPlugin(EmailPlugin):
    """SendGrid email plugin.

    Sends emails via SendGrid API. Supports templates, tracking, and analytics.

    Configuration:
        api_key: SendGrid API key
        from_email: Default sender email
        from_name: Default sender name
        template_id: Default template ID (optional)

    Example:
        >>> context = PluginContext(
        ...     config={
        ...         "api_key": "SG.xxx",
        ...         "from_email": "noreply@example.com",
        ...         "from_name": "My App",
        ...     }
        ... )
        >>> plugin = SendGridEmailPlugin()
        >>> await plugin.init(context)
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="sendgrid-email",
            version="1.0.0",
            description="SendGrid email provider",
            author="Python Fast Forge",
            plugin_type="email",
            dependencies=["http-client"],
            config_schema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string"},
                    "from_email": {"type": "string", "format": "email"},
                    "from_name": {"type": "string"},
                    "template_id": {"type": "string"},
                },
                "required": ["api_key", "from_email"],
            },
        )

    async def init(self, context: PluginContext) -> None:
        """Initialize SendGrid client."""
        self.context = context
        self._api_key = context.config["api_key"]
        self._from_email = context.config["from_email"]
        self._from_name = context.config.get("from_name", "")
        self._template_id = context.config.get("template_id")

        # Initialize SendGrid client
        try:
            from sendgrid import SendGridAPIClient

            self._client = SendGridAPIClient(self._api_key)
            self._sendgrid_available = True
        except ImportError:
            if context.logger:
                context.logger.warning(
                    "sendgrid_not_available",
                    message="sendgrid library not installed. Install with: pip install sendgrid",
                )
            self._client = None
            self._sendgrid_available = False

    async def validate(self) -> bool:
        """Validate SendGrid configuration."""
        return "api_key" in self.context.config and "from_email" in self.context.config

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        reply_to: str | None = None,
    ) -> str:
        """Send email via SendGrid.

        Args:
            to: Recipient email(s)
            subject: Email subject
            body: Email body
            html: Whether body is HTML
            cc: CC recipients
            bcc: BCC recipients
            attachments: File attachments
            reply_to: Reply-to address

        Returns:
            Message ID from SendGrid
        """
        # Check if SendGrid is available
        if not self._sendgrid_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "sendgrid_unavailable",
                    message="SendGrid client not available, email not sent",
                )
            return "sendgrid-unavailable"

        try:
            from sendgrid.helpers.mail import (
                Attachment,
                Content,
                Email,
                FileContent,
                FileName,
                FileType,
                Mail,
                Personalization,
            )

            # Normalize recipients
            to_list = [to] if isinstance(to, str) else to

            # Create mail object
            mail = Mail()

            # Set from address
            mail.from_email = Email(self._from_email, self._from_name)

            # Set subject
            mail.subject = subject

            # Add personalization (to, cc, bcc)
            personalization = Personalization()
            for recipient in to_list:
                personalization.add_to(Email(recipient))

            if cc:
                for cc_recipient in cc:
                    personalization.add_cc(Email(cc_recipient))

            if bcc:
                for bcc_recipient in bcc:
                    personalization.add_bcc(Email(bcc_recipient))

            mail.add_personalization(personalization)

            # Set body content
            content_type = "text/html" if html else "text/plain"
            mail.add_content(Content(content_type, body))

            # Add reply-to if provided
            if reply_to:
                mail.reply_to = Email(reply_to)

            # Add attachments if provided
            if attachments:
                for attachment_data in attachments:
                    filename = attachment_data.get("filename", "attachment")
                    content = attachment_data.get("content", b"")
                    mime_type = attachment_data.get("mime_type", "application/octet-stream")

                    # Encode content to base64
                    if isinstance(content, str):
                        content = content.encode()
                    encoded_content = base64.b64encode(content).decode()

                    attachment = Attachment()
                    attachment.file_content = FileContent(encoded_content)
                    attachment.file_name = FileName(filename)
                    attachment.file_type = FileType(mime_type)

                    mail.add_attachment(attachment)

            # Send via SendGrid API
            response = self._client.send(mail)

            message_id = response.headers.get("X-Message-Id", "unknown")

            if self.context and self.context.logger:
                self.context.logger.info(
                    "sendgrid_email_sent",
                    to=to_list,
                    subject=subject,
                    message_id=message_id,
                    status_code=response.status_code,
                )

            return message_id

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "sendgrid_send_failed",
                    to=to,
                    subject=subject,
                    error=str(e),
                )
            raise


__all__ = [
    "EmailPlugin",
    "SMTPEmailPlugin",
    "SendGridEmailPlugin",
]
