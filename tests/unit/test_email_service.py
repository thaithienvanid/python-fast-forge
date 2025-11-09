"""Tests for email service integration.

Test Organization:
- TestEmailServiceInitialization: Service initialization
- TestEmailServiceSendEmail: send_email with circuit breaker
- TestEmailServiceInternalSuccess: Successful sends
- TestEmailServiceHTTPErrors: HTTP error responses
- TestEmailServiceNetworkErrors: Network failures
- TestEmailServiceEdgeCases: Edge cases and boundaries
- TestEmailServiceLogging: Logging behavior
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.external.email_service import EmailService
from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_circuit_breaker() -> MagicMock:
    """Create mock circuit breaker.

    Returns:
        MagicMock configured as CircuitBreakerService
    """
    return MagicMock(spec=CircuitBreakerService)


@pytest.fixture
def email_service(mock_circuit_breaker: MagicMock) -> EmailService:
    """Create EmailService instance with test API key.

    Args:
        mock_circuit_breaker: Mock circuit breaker

    Returns:
        EmailService instance for testing
    """
    return EmailService(circuit_breaker=mock_circuit_breaker, api_key="test_api_key_12345")


# ============================================================================
# Initialization Tests
# ============================================================================


class TestEmailServiceInitialization:
    """Test EmailService initialization."""

    def test_initializes_with_api_key(self, mock_circuit_breaker: MagicMock) -> None:
        """Test EmailService stores API key.

        Arrange: Circuit breaker and API key
        Act: Create EmailService
        Assert: API key is stored
        """
        # Arrange & Act
        service = EmailService(circuit_breaker=mock_circuit_breaker, api_key="test_key_123")

        # Assert
        assert service._api_key == "test_key_123"

    def test_initializes_with_circuit_breaker(self, mock_circuit_breaker: MagicMock) -> None:
        """Test EmailService stores circuit breaker.

        Arrange: Circuit breaker instance
        Act: Create EmailService
        Assert: Circuit breaker is stored
        """
        # Arrange & Act
        service = EmailService(circuit_breaker=mock_circuit_breaker, api_key="key")

        # Assert
        assert service._circuit_breaker is mock_circuit_breaker

    def test_initializes_with_default_base_url(self, mock_circuit_breaker: MagicMock) -> None:
        """Test EmailService sets default base URL.

        Arrange: Circuit breaker
        Act: Create EmailService
        Assert: Base URL is set to default
        """
        # Arrange & Act
        service = EmailService(circuit_breaker=mock_circuit_breaker, api_key="key")

        # Assert
        assert service._base_url == "https://api.emailprovider.com"

    def test_initializes_with_empty_api_key(self, mock_circuit_breaker: MagicMock) -> None:
        """Test EmailService accepts empty API key.

        Arrange: Circuit breaker and empty API key
        Act: Create EmailService
        Assert: Empty API key is stored
        """
        # Arrange & Act
        service = EmailService(circuit_breaker=mock_circuit_breaker, api_key="")

        # Assert
        assert service._api_key == ""


# ============================================================================
# Send Email Tests (Circuit Breaker Integration)
# ============================================================================


class TestEmailServiceSendEmail:
    """Test send_email method with circuit breaker integration."""

    async def test_calls_circuit_breaker_with_correct_parameters(
        self, email_service: EmailService, mock_circuit_breaker: MagicMock
    ) -> None:
        """Test send_email calls circuit breaker with correct params.

        Arrange: Email service with mock circuit breaker
        Act: Call send_email
        Assert: Circuit breaker called with correct breaker name and params
        """
        # Arrange
        mock_circuit_breaker.call_with_breaker = AsyncMock(return_value=True)

        # Act
        await email_service.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        # Assert
        mock_circuit_breaker.call_with_breaker.assert_called_once()
        call_kwargs = mock_circuit_breaker.call_with_breaker.call_args.kwargs
        assert call_kwargs["breaker_name"] == "email_service"
        assert call_kwargs["to"] == "recipient@example.com"
        assert call_kwargs["subject"] == "Test Subject"
        assert call_kwargs["body"] == "Test Body"

    async def test_returns_true_on_success(
        self, email_service: EmailService, mock_circuit_breaker: MagicMock
    ) -> None:
        """Test send_email returns True on successful send.

        Arrange: Circuit breaker returns True
        Act: Call send_email
        Assert: Returns True
        """
        # Arrange
        mock_circuit_breaker.call_with_breaker = AsyncMock(return_value=True)

        # Act
        result = await email_service.send_email(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

        # Assert
        assert result is True

    async def test_returns_false_on_circuit_breaker_exception(
        self, email_service: EmailService, mock_circuit_breaker: MagicMock
    ) -> None:
        """Test send_email returns False when circuit breaker raises.

        Arrange: Circuit breaker raises exception
        Act: Call send_email
        Assert: Returns False
        """
        # Arrange
        mock_circuit_breaker.call_with_breaker = AsyncMock(
            side_effect=Exception("Circuit breaker open")
        )

        # Act
        result = await email_service.send_email(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

        # Assert
        assert result is False

    async def test_returns_false_on_falsy_circuit_breaker_result(
        self, email_service: EmailService, mock_circuit_breaker: MagicMock
    ) -> None:
        """Test send_email returns False when breaker returns falsy value.

        Arrange: Circuit breaker returns None
        Act: Call send_email
        Assert: Returns False
        """
        # Arrange
        mock_circuit_breaker.call_with_breaker = AsyncMock(return_value=None)

        # Act
        result = await email_service.send_email(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

        # Assert
        assert result is False

    async def test_returns_false_on_circuit_breaker_zero_result(
        self, email_service: EmailService, mock_circuit_breaker: MagicMock
    ) -> None:
        """Test send_email returns False when breaker returns 0.

        Arrange: Circuit breaker returns 0
        Act: Call send_email
        Assert: Returns False
        """
        # Arrange
        mock_circuit_breaker.call_with_breaker = AsyncMock(return_value=0)

        # Act
        result = await email_service.send_email(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

        # Assert
        assert result is False


# ============================================================================
# Internal Send Success Tests
# ============================================================================


class TestEmailServiceInternalSuccess:
    """Test successful internal email sending."""

    async def test_sends_to_correct_endpoint(self, email_service: EmailService) -> None:
        """Test _send_email_internal calls correct API endpoint.

        Arrange: Mock HTTP client with 200 response
        Act: Call _send_email_internal
        Assert: Correct URL is called
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            await email_service._send_email_internal(
                to="test@example.com",
                subject="Subject",
                body="Body",
            )

            # Assert
            assert mock_client.post.call_args[0][0] == "https://api.emailprovider.com/send"

    async def test_sends_correct_json_payload(self, email_service: EmailService) -> None:
        """Test _send_email_internal sends correct JSON payload.

        Arrange: Mock HTTP client
        Act: Call _send_email_internal
        Assert: JSON payload contains correct data
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            await email_service._send_email_internal(
                to="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )

            # Assert
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["to"] == "recipient@example.com"
            assert call_kwargs["json"]["subject"] == "Test Subject"
            assert call_kwargs["json"]["body"] == "Test Body"

    async def test_sends_authorization_header(self, email_service: EmailService) -> None:
        """Test _send_email_internal sends Authorization header.

        Arrange: Mock HTTP client, EmailService with API key
        Act: Call _send_email_internal
        Assert: Authorization header contains Bearer token
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            await email_service._send_email_internal(
                to="test@example.com",
                subject="Subject",
                body="Body",
            )

            # Assert
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["headers"]["Authorization"] == "Bearer test_api_key_12345"

    async def test_uses_10_second_timeout(self, email_service: EmailService) -> None:
        """Test _send_email_internal uses 10 second timeout.

        Arrange: Mock HTTP client
        Act: Call _send_email_internal
        Assert: Timeout is set to 10.0 seconds
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            await email_service._send_email_internal(
                to="test@example.com",
                subject="Subject",
                body="Body",
            )

            # Assert
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["timeout"] == 10.0

    async def test_returns_true_on_200_response(self, email_service: EmailService) -> None:
        """Test _send_email_internal returns True on 200 OK.

        Arrange: Mock HTTP client with 200 response
        Act: Call _send_email_internal
        Assert: Returns True
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            result = await email_service._send_email_internal(
                to="test@example.com",
                subject="Subject",
                body="Body",
            )

            # Assert
            assert result is True


# ============================================================================
# HTTP Error Tests
# ============================================================================


class TestEmailServiceHTTPErrors:
    """Test HTTP error handling in internal email sending."""

    async def test_raises_on_400_bad_request(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 400 Bad Request.

        Arrange: Mock HTTP client with 400 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 400

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 400"):
                await email_service._send_email_internal(
                    to="invalid@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_401_unauthorized(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 401 Unauthorized.

        Arrange: Mock HTTP client with 401 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 401"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_403_forbidden(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 403 Forbidden.

        Arrange: Mock HTTP client with 403 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 403"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_404_not_found(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 404 Not Found.

        Arrange: Mock HTTP client with 404 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 404"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_429_rate_limit(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 429 Too Many Requests.

        Arrange: Mock HTTP client with 429 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 429"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_500_internal_server_error(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 500 Internal Server Error.

        Arrange: Mock HTTP client with 500 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 500"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_502_bad_gateway(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 502 Bad Gateway.

        Arrange: Mock HTTP client with 502 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 502

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 502"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_raises_on_503_service_unavailable(self, email_service: EmailService) -> None:
        """Test _send_email_internal raises on 503 Service Unavailable.

        Arrange: Mock HTTP client with 503 response
        Act: Call _send_email_internal
        Assert: Exception raised with status code
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(Exception, match="Email API returned 503"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )


# ============================================================================
# Network Error Tests
# ============================================================================


class TestEmailServiceNetworkErrors:
    """Test network error handling."""

    async def test_propagates_connect_error(self, email_service: EmailService) -> None:
        """Test _send_email_internal propagates connection errors.

        Arrange: Mock HTTP client raises ConnectError
        Act: Call _send_email_internal
        Assert: ConnectError is propagated
        """
        # Arrange
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(httpx.ConnectError, match="Connection failed"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_propagates_timeout_exception(self, email_service: EmailService) -> None:
        """Test _send_email_internal propagates timeout exceptions.

        Arrange: Mock HTTP client raises TimeoutException
        Act: Call _send_email_internal
        Assert: TimeoutException is propagated
        """
        # Arrange
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(httpx.TimeoutException, match="Request timeout"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )

    async def test_propagates_network_error(self, email_service: EmailService) -> None:
        """Test _send_email_internal propagates network errors.

        Arrange: Mock HTTP client raises NetworkError
        Act: Call _send_email_internal
        Assert: NetworkError is propagated
        """
        # Arrange
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.NetworkError("Network failure"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act & Assert
            with pytest.raises(httpx.NetworkError, match="Network failure"):
                await email_service._send_email_internal(
                    to="test@example.com",
                    subject="Subject",
                    body="Body",
                )


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEmailServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_handles_long_email_address(self, email_service: EmailService) -> None:
        """Test sending to very long email address.

        Arrange: Mock HTTP client, very long email address
        Act: Call _send_email_internal
        Assert: Request is made with long email
        """
        # Arrange
        long_email = "a" * 50 + "@" + "b" * 50 + ".com"
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            result = await email_service._send_email_internal(
                to=long_email,
                subject="Subject",
                body="Body",
            )

            # Assert
            assert result is True
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["to"] == long_email

    async def test_handles_empty_subject(self, email_service: EmailService) -> None:
        """Test sending email with empty subject.

        Arrange: Mock HTTP client, empty subject
        Act: Call _send_email_internal
        Assert: Request is made with empty subject
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            result = await email_service._send_email_internal(
                to="test@example.com",
                subject="",
                body="Body",
            )

            # Assert
            assert result is True
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["subject"] == ""

    async def test_handles_empty_body(self, email_service: EmailService) -> None:
        """Test sending email with empty body.

        Arrange: Mock HTTP client, empty body
        Act: Call _send_email_internal
        Assert: Request is made with empty body
        """
        # Arrange
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            result = await email_service._send_email_internal(
                to="test@example.com",
                subject="Subject",
                body="",
            )

            # Assert
            assert result is True
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["body"] == ""

    async def test_handles_unicode_in_subject(self, email_service: EmailService) -> None:
        """Test sending email with Unicode in subject.

        Arrange: Mock HTTP client, subject with Unicode
        Act: Call _send_email_internal
        Assert: Request is made with Unicode subject
        """
        # Arrange
        unicode_subject = "Test 日本語 Ñoño 🎉"
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            result = await email_service._send_email_internal(
                to="test@example.com",
                subject=unicode_subject,
                body="Body",
            )

            # Assert
            assert result is True
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["subject"] == unicode_subject

    async def test_handles_unicode_in_body(self, email_service: EmailService) -> None:
        """Test sending email with Unicode in body.

        Arrange: Mock HTTP client, body with Unicode
        Act: Call _send_email_internal
        Assert: Request is made with Unicode body
        """
        # Arrange
        unicode_body = "Hello 世界 مرحبا мир 🌍"
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Act
            result = await email_service._send_email_internal(
                to="test@example.com",
                subject="Subject",
                body=unicode_body,
            )

            # Assert
            assert result is True
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["body"] == unicode_body
