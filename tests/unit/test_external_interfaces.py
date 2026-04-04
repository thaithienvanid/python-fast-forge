"""Unit tests for external service interfaces."""

import pytest

from src.external.interfaces import IEmailService


class MockEmailService(IEmailService):
    """Mock implementation of IEmailService for testing."""

    def __init__(self):
        self.sent_emails = []

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Mock send_email implementation."""
        self.sent_emails.append({"to": to, "subject": subject, "body": body})
        return True


class TestIEmailService:
    """Tests for IEmailService interface."""

    @pytest.mark.asyncio
    async def test_mock_implementation_works(self):
        """Mock implementation of IEmailService works."""
        service = MockEmailService()

        result = await service.send_email(
            to="test@example.com", subject="Test Subject", body="Test Body"
        )

        assert result is True
        assert len(service.sent_emails) == 1
        assert service.sent_emails[0]["to"] == "test@example.com"
        assert service.sent_emails[0]["subject"] == "Test Subject"
        assert service.sent_emails[0]["body"] == "Test Body"

    @pytest.mark.asyncio
    async def test_interface_defines_send_email(self):
        """IEmailService defines send_email abstract method."""
        assert hasattr(IEmailService, "send_email")
        assert callable(IEmailService.send_email)
