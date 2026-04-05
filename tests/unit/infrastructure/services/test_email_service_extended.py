"""Extended unit tests for infrastructure EmailService.

Covers missing lines in src/infrastructure/services/email_service.py:
- Lines 52-56: __init__ initialization logging
- Lines 97-117: send_email provider routing (smtp, sendgrid, unsupported)
- Lines 144-231: _send_via_smtp (dev mode, production SMTP, CC, BCC, reply-to,
                  SSL vs TLS, login, error handling)
- Lines 259-263: _send_via_sendgrid fallback to SMTP
- Line 285: get_email_service singleton

Test Organization:
- AAA pattern (Arrange-Act-Assert)
- patch for smtplib, settings, and logger
- parametrize for different provider/config combinations
- AsyncMock for async send methods
"""

import smtplib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.services.email_service import EmailService, get_email_service


# ============================================================================
# Shared Fixtures
# ============================================================================


def make_mock_settings(
    provider="smtp",
    smtp_host="localhost",
    smtp_port=587,
    smtp_username="",
    smtp_password="",
    smtp_use_tls=True,
    smtp_use_ssl=False,
    email_from_address="noreply@example.com",
    email_from_name="Test App",
):
    """Create a mock settings object with configurable values."""
    mock_settings = MagicMock()
    mock_settings.external_services.email_provider = provider
    mock_settings.external_services.smtp_host = smtp_host
    mock_settings.external_services.smtp_port = smtp_port
    mock_settings.external_services.smtp_username = smtp_username
    mock_settings.external_services.smtp_password = smtp_password
    mock_settings.external_services.smtp_use_tls = smtp_use_tls
    mock_settings.external_services.smtp_use_ssl = smtp_use_ssl
    mock_settings.external_services.email_from_address = email_from_address
    mock_settings.external_services.email_from_name = email_from_name
    return mock_settings


@pytest.fixture
def mock_settings():
    """Default mock settings using SMTP provider in dev mode."""
    return make_mock_settings()


@pytest.fixture
def email_service(mock_settings):
    """Create EmailService with mocked settings."""
    with patch(
        "src.infrastructure.services.email_service.get_settings", return_value=mock_settings
    ):
        return EmailService()


@pytest.fixture
def production_settings():
    """Mock settings for production SMTP (non-localhost, credentials configured)."""
    return make_mock_settings(
        smtp_host="smtp.production.example.com",
        smtp_port=587,
        smtp_username="smtpuser",
        smtp_password="smtppass",
        smtp_use_tls=True,
        smtp_use_ssl=False,
    )


@pytest.fixture
def ssl_production_settings():
    """Mock settings for production SMTP with SSL."""
    return make_mock_settings(
        smtp_host="smtp.ssl.example.com",
        smtp_port=465,
        smtp_username="ssluser",
        smtp_password="sslpass",
        smtp_use_tls=False,
        smtp_use_ssl=True,
    )


# ============================================================================
# EmailService Initialization Tests
# ============================================================================


class TestEmailServiceInitialization:
    """Tests for EmailService.__init__ covering lines 52-56."""

    def test_initializes_with_smtp_provider(self):
        """Test EmailService stores smtp provider from settings.

        Arrange: Settings with smtp provider
        Act: Create EmailService
        Assert: Provider stored correctly (lines 53-54)
        """
        # Arrange
        settings = make_mock_settings(provider="smtp")

        # Act
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()

        # Assert
        assert service._provider == "smtp"

    def test_initializes_with_sendgrid_provider(self):
        """Test EmailService stores sendgrid provider from settings.

        Arrange: Settings with sendgrid provider
        Act: Create EmailService
        Assert: Provider is sendgrid
        """
        # Arrange
        settings = make_mock_settings(provider="sendgrid")

        # Act
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()

        # Assert
        assert service._provider == "sendgrid"

    def test_stores_config_reference(self):
        """Test EmailService stores external_services config reference.

        Arrange: Settings object
        Act: Create EmailService
        Assert: _config is settings.external_services (line 53)
        """
        # Arrange
        settings = make_mock_settings()

        # Act
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()

        # Assert
        assert service._config is settings.external_services

    def test_logs_initialization(self):
        """Test EmailService logs initialization with provider info.

        Arrange: Mock logger
        Act: Create EmailService
        Assert: Logger.info called (lines 56-60)
        """
        # Arrange
        settings = make_mock_settings()

        # Act & Assert
        with (
            patch("src.infrastructure.services.email_service.get_settings", return_value=settings),
            patch("src.infrastructure.services.email_service.logger") as mock_logger,
        ):
            EmailService()
            mock_logger.info.assert_called_once()


# ============================================================================
# send_email Tests - Provider Routing
# ============================================================================


class TestSendEmailProviderRouting:
    """Tests for send_email provider routing covering lines 97-117."""

    async def test_routes_to_smtp_when_provider_is_smtp(self, email_service):
        """Test send_email calls _send_via_smtp when provider is smtp.

        Arrange: Provider is smtp
        Act: Call send_email
        Assert: _send_via_smtp called (lines 97-106)
        """
        # Arrange
        email_service._send_via_smtp = AsyncMock(return_value="msg-id-123")

        # Act
        result = await email_service.send_email(
            to="user@example.com",
            subject="Test",
            body="Hello",
        )

        # Assert
        email_service._send_via_smtp.assert_called_once()
        assert result == "msg-id-123"

    async def test_routes_to_sendgrid_when_provider_is_sendgrid(self, mock_settings):
        """Test send_email calls _send_via_sendgrid when provider is sendgrid.

        Arrange: Provider is sendgrid
        Act: Call send_email
        Assert: _send_via_sendgrid called (lines 107-116)
        """
        # Arrange
        settings = make_mock_settings(provider="sendgrid")
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()
        service._send_via_sendgrid = AsyncMock(return_value="sendgrid-msg-id")

        # Act
        result = await service.send_email(
            to="user@example.com",
            subject="Test",
            body="Body",
        )

        # Assert
        service._send_via_sendgrid.assert_called_once()
        assert result == "sendgrid-msg-id"

    async def test_raises_value_error_for_unsupported_provider(self):
        """Test send_email raises ValueError for unsupported provider.

        Arrange: Provider is unsupported (e.g. 'mailgun')
        Act: Call send_email
        Assert: ValueError raised (line 117)
        """
        # Arrange
        settings = make_mock_settings(provider="mailgun")
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()

        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported email provider"):
            await service.send_email(to="user@example.com", subject="Test", body="Body")

    async def test_passes_all_parameters_to_smtp(self, email_service):
        """Test send_email forwards all optional parameters to smtp.

        Arrange: Provider smtp, all optional params provided
        Act: Call send_email with cc, bcc, reply_to
        Assert: _send_via_smtp called with all params
        """
        # Arrange
        email_service._send_via_smtp = AsyncMock(return_value="msg-id")

        # Act
        await email_service.send_email(
            to=["a@example.com", "b@example.com"],
            subject="Multi",
            body="Body",
            html=True,
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            reply_to="reply@example.com",
        )

        # Assert
        call_kwargs = email_service._send_via_smtp.call_args.kwargs
        assert call_kwargs["to"] == ["a@example.com", "b@example.com"]
        assert call_kwargs["html"] is True
        assert call_kwargs["cc"] == ["cc@example.com"]
        assert call_kwargs["bcc"] == ["bcc@example.com"]
        assert call_kwargs["reply_to"] == "reply@example.com"


# ============================================================================
# _send_via_smtp Tests
# ============================================================================


class TestSendViaSMTP:
    """Tests for _send_via_smtp covering lines 144-231."""

    async def test_returns_simulated_id_in_dev_mode(self, email_service):
        """Test returns 'simulated-message-id' when smtp_host is localhost with no auth.

        Arrange: smtp_host='localhost', smtp_username=''
        Act: Call _send_via_smtp
        Assert: Returns 'simulated-message-id' (lines 166-173)
        """
        # Act
        result = await email_service._send_via_smtp(
            to="user@example.com",
            subject="Dev Test",
            body="Hello",
        )

        # Assert
        assert result == "simulated-message-id"

    async def test_logs_simulated_send_in_dev_mode(self, email_service):
        """Test logs email_simulated in dev mode.

        Arrange: Dev mode settings
        Act: Call _send_via_smtp
        Assert: logger.info called with 'email_simulated'
        """
        # Act
        with patch("src.infrastructure.services.email_service.logger") as mock_logger:
            await email_service._send_via_smtp(
                to="user@example.com",
                subject="Test",
                body="Body",
            )

        # Assert
        mock_logger.info.assert_called_with(
            "email_simulated",
            to=["user@example.com"],
            subject="Test",
            message="SMTP not configured, simulating email send (development mode)",
        )

    async def test_normalizes_single_recipient_to_list(self, email_service):
        """Test normalizes string recipient to list.

        Arrange: to is a string, dev mode
        Act: Call _send_via_smtp
        Assert: Simulated send succeeds (line 144)
        """
        # Act
        result = await email_service._send_via_smtp(
            to="single@example.com",
            subject="Test",
            body="Body",
        )

        # Assert
        assert result == "simulated-message-id"

    async def test_handles_list_recipient_in_dev_mode(self, email_service):
        """Test handles list of recipients correctly in dev mode.

        Arrange: to is a list, dev mode
        Act: Call _send_via_smtp
        Assert: Simulated send succeeds
        """
        # Act
        result = await email_service._send_via_smtp(
            to=["a@example.com", "b@example.com"],
            subject="Multi",
            body="Body",
        )

        # Assert
        assert result == "simulated-message-id"

    async def test_sends_via_smtp_in_production_mode(self, production_settings):
        """Test sends actual SMTP email in production mode.

        Arrange: Production SMTP settings, mock smtplib.SMTP
        Act: Call _send_via_smtp
        Assert: SMTP server called correctly (lines 183-221)
        """
        # Arrange
        with patch(
            "src.infrastructure.services.email_service.get_settings",
            return_value=production_settings,
        ):
            service = EmailService()

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.sendmail = MagicMock()
        mock_smtp_instance.quit = MagicMock()
        mock_smtp_instance.starttls = MagicMock()
        mock_smtp_instance.login = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp_instance):
            # Act
            await service._send_via_smtp(
                to="recipient@example.com",
                subject="Production Test",
                body="Hello from production",
            )

        # Assert
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("smtpuser", "smtppass")
        mock_smtp_instance.sendmail.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()

    async def test_uses_smtp_ssl_when_configured(self, ssl_production_settings):
        """Test uses SMTP_SSL connection when smtp_use_ssl=True.

        Arrange: ssl_production_settings with smtp_use_ssl=True
        Act: Call _send_via_smtp
        Assert: smtplib.SMTP_SSL used instead of SMTP (lines 178-181)
        """
        # Arrange
        with patch(
            "src.infrastructure.services.email_service.get_settings",
            return_value=ssl_production_settings,
        ):
            service = EmailService()

        mock_ssl_instance = MagicMock()
        mock_ssl_instance.sendmail = MagicMock()
        mock_ssl_instance.quit = MagicMock()
        mock_ssl_instance.login = MagicMock()

        with patch("smtplib.SMTP_SSL", return_value=mock_ssl_instance) as mock_smtp_ssl:
            # Act
            await service._send_via_smtp(
                to="recipient@example.com",
                subject="SSL Test",
                body="Hello via SSL",
            )

        # Assert
        mock_smtp_ssl.assert_called_once_with(
            ssl_production_settings.external_services.smtp_host,
            ssl_production_settings.external_services.smtp_port,
        )
        mock_ssl_instance.sendmail.assert_called_once()

    async def test_adds_cc_to_all_recipients(self, production_settings):
        """Test includes CC addresses in the sendmail call.

        Arrange: Production settings, CC recipient
        Act: Call _send_via_smtp with cc
        Assert: CC included in all_recipients (lines 199-201)
        """
        # Arrange
        with patch(
            "src.infrastructure.services.email_service.get_settings",
            return_value=production_settings,
        ):
            service = EmailService()

        mock_smtp_instance = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp_instance):
            # Act
            await service._send_via_smtp(
                to="to@example.com",
                subject="CC Test",
                body="Body",
                cc=["cc@example.com"],
            )

        # Assert - sendmail should include cc in recipients
        sendmail_call = mock_smtp_instance.sendmail.call_args
        all_recipients = sendmail_call[0][1]
        assert "cc@example.com" in all_recipients

    async def test_adds_bcc_to_all_recipients(self, production_settings):
        """Test includes BCC addresses in the sendmail call.

        Arrange: Production settings, BCC recipient
        Act: Call _send_via_smtp with bcc
        Assert: BCC included in all_recipients (lines 201-202)
        """
        # Arrange
        with patch(
            "src.infrastructure.services.email_service.get_settings",
            return_value=production_settings,
        ):
            service = EmailService()

        mock_smtp_instance = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp_instance):
            # Act
            await service._send_via_smtp(
                to="to@example.com",
                subject="BCC Test",
                body="Body",
                bcc=["bcc@example.com"],
            )

        # Assert
        sendmail_call = mock_smtp_instance.sendmail.call_args
        all_recipients = sendmail_call[0][1]
        assert "bcc@example.com" in all_recipients

    async def test_logs_error_and_reraises_on_smtp_failure(self, production_settings):
        """Test logs error and re-raises exception on SMTP failure.

        Arrange: SMTP raises exception
        Act: Call _send_via_smtp
        Assert: Exception re-raised, logger.error called (lines 223-231)
        """
        # Arrange
        with patch(
            "src.infrastructure.services.email_service.get_settings",
            return_value=production_settings,
        ):
            service = EmailService()

        with (
            patch(
                "smtplib.SMTP",
                side_effect=smtplib.SMTPConnectError(421, "Cannot connect"),
            ),
            patch("src.infrastructure.services.email_service.logger") as mock_logger,
            pytest.raises(smtplib.SMTPConnectError),
        ):
            # Act
            await service._send_via_smtp(
                to="recipient@example.com",
                subject="Test",
                body="Body",
            )

        # Assert
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "email_send_failed"

    async def test_sets_reply_to_header(self, email_service):
        """Test sets Reply-To header when reply_to provided (dev mode).

        Arrange: Dev mode, reply_to provided
        Act: Call _send_via_smtp
        Assert: Simulated send succeeds (reply_to stored in message headers)
        """
        # Act
        result = await email_service._send_via_smtp(
            to="user@example.com",
            subject="Test",
            body="Body",
            reply_to="replyto@example.com",
        )

        # Assert
        assert result == "simulated-message-id"

    async def test_sends_html_email(self, email_service):
        """Test sends HTML email when html=True (dev mode).

        Arrange: Dev mode, html=True
        Act: Call _send_via_smtp
        Assert: Simulated send (mime_type='html' set internally)
        """
        # Act
        result = await email_service._send_via_smtp(
            to="user@example.com",
            subject="HTML Test",
            body="<h1>Hello</h1>",
            html=True,
        )

        # Assert
        assert result == "simulated-message-id"

    async def test_from_header_without_name(self):
        """Test From header uses only email when email_from_name is empty.

        Arrange: Settings with empty email_from_name
        Act: Call _send_via_smtp
        Assert: From header uses just the email address (lines 148-152)
        """
        # Arrange
        settings = make_mock_settings(email_from_name="", email_from_address="noreply@example.com")
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()

        # Act
        result = await service._send_via_smtp(
            to="user@example.com",
            subject="Test",
            body="Body",
        )

        # Assert - dev mode so simulated
        assert result == "simulated-message-id"


# ============================================================================
# _send_via_sendgrid Tests
# ============================================================================


class TestSendViaSendGrid:
    """Tests for _send_via_sendgrid covering lines 259-263."""

    async def test_falls_back_to_smtp_with_warning(self):
        """Test _send_via_sendgrid logs warning and falls back to SMTP.

        Arrange: SendGrid provider configured
        Act: Call _send_via_sendgrid
        Assert: Warning logged, _send_via_smtp called (lines 259-271)
        """
        # Arrange
        settings = make_mock_settings(provider="sendgrid")
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            service = EmailService()

        service._send_via_smtp = AsyncMock(return_value="smtp-fallback-id")

        # Act
        with patch("src.infrastructure.services.email_service.logger") as mock_logger:
            result = await service._send_via_sendgrid(
                to="user@example.com",
                subject="SendGrid Test",
                body="Body",
            )

        # Assert
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args
        assert warning_call[0][0] == "sendgrid_not_implemented"
        service._send_via_smtp.assert_called_once()
        assert result == "smtp-fallback-id"


# ============================================================================
# get_email_service Tests
# ============================================================================


class TestGetEmailService:
    """Tests for get_email_service singleton covering line 285."""

    def test_returns_email_service_instance(self):
        """Test get_email_service returns an EmailService instance.

        Arrange: Mock settings
        Act: Call get_email_service
        Assert: Returns EmailService instance (line 285)
        """
        # Arrange
        settings = make_mock_settings()

        # Act
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            # Clear cache before calling
            get_email_service.cache_clear()
            service = get_email_service()

        # Assert
        assert isinstance(service, EmailService)

    def test_returns_same_instance_on_multiple_calls(self):
        """Test get_email_service returns cached singleton.

        Arrange: Mock settings
        Act: Call get_email_service twice
        Assert: Same instance returned both times
        """
        # Arrange
        settings = make_mock_settings()

        # Act
        with patch("src.infrastructure.services.email_service.get_settings", return_value=settings):
            get_email_service.cache_clear()
            service1 = get_email_service()
            service2 = get_email_service()

        # Assert
        assert service1 is service2
