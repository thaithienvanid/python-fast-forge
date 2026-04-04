"""Unit tests for external services configuration."""

from src.infrastructure.config.external_services_settings import (
    ExternalServicesSettings,
)


class TestExternalServicesSettings:
    """Tests for ExternalServicesSettings."""

    def test_creates_with_defaults(self):
        """Creates settings with default values."""
        settings = ExternalServicesSettings()

        assert settings.email_provider == "smtp"
        assert settings.smtp_host == "localhost"
        assert settings.smtp_port == 587
        assert settings.smtp_use_tls is True
        assert settings.email_from_address == "noreply@example.com"

    def test_configures_smtp_settings(self, monkeypatch):
        """Configures SMTP-specific settings."""
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USERNAME", "user@gmail.com")
        monkeypatch.setenv("SMTP_PASSWORD", "app_password")
        monkeypatch.setenv("SMTP_USE_TLS", "false")
        monkeypatch.setenv("SMTP_USE_SSL", "true")

        settings = ExternalServicesSettings()

        assert settings.smtp_host == "smtp.gmail.com"
        assert settings.smtp_port == 465
        assert settings.smtp_username == "user@gmail.com"
        assert settings.smtp_password == "app_password"
        assert settings.smtp_use_tls is False
        assert settings.smtp_use_ssl is True

    def test_configures_email_sender_info(self, monkeypatch):
        """Configures email sender information."""
        monkeypatch.setenv("EMAIL_FROM_ADDRESS", "support@myapp.com")
        monkeypatch.setenv("EMAIL_FROM_NAME", "MyApp Support")

        settings = ExternalServicesSettings()

        assert settings.email_from_address == "support@myapp.com"
        assert settings.email_from_name == "MyApp Support"

    def test_supports_all_email_providers(self, monkeypatch):
        """Supports all email provider options."""
        providers = ["smtp", "sendgrid", "ses", "mailgun"]

        for provider in providers:
            monkeypatch.setenv("EMAIL_PROVIDER", provider)
            settings = ExternalServicesSettings(is_production=False)
            assert settings.email_provider == provider

    def test_configures_email_api_key(self, monkeypatch):
        """Configures email API key from environment."""
        monkeypatch.setenv("EMAIL_API_KEY", "test-api-key-123")

        settings = ExternalServicesSettings()

        assert settings.email_api_key == "test-api-key-123"

    def test_smtp_defaults(self):
        """SMTP has sensible defaults for TLS/SSL."""
        settings = ExternalServicesSettings()

        assert settings.smtp_use_tls is True
        assert settings.smtp_use_ssl is False
        assert settings.smtp_port == 587  # Standard TLS port
