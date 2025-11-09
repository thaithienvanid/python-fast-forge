"""Email service integration with external email provider.

Example of integrating with third-party email APIs using circuit breaker pattern.
"""

import httpx

from src.external.interfaces import IEmailService
from src.infrastructure.logging.config import get_logger
from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService


logger = get_logger(__name__)


class EmailService(IEmailService):
    """Email service integration with circuit breaker protection.

    Demonstrates integrating with external email APIs and using circuit breaker
    pattern to prevent cascading failures when the external service is down.
    """

    def __init__(self, circuit_breaker: CircuitBreakerService, api_key: str = "") -> None:
        """Initialize email service.

        Args:
            circuit_breaker: Circuit breaker service instance
            api_key: Email service API key
        """
        self._circuit_breaker = circuit_breaker
        self._api_key = api_key
        self._base_url = "https://api.emailprovider.com"  # Example

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> bool:
        """Send email with circuit breaker protection.

        If the email service is down or slow, the circuit breaker will open
        after configured failures, preventing unnecessary requests.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Call external service with circuit breaker protection
            result = await self._circuit_breaker.call_with_breaker(
                breaker_name="email_service",
                func=self._send_email_internal,
                to=to,
                subject=subject,
                body=body,
            )
            return bool(result)
        except Exception as e:
            logger.error(
                "email_send_failed",
                to=to,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def _send_email_internal(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> bool:
        """Internal method to send email via external API.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body

        Returns:
            True if successful

        Raises:
            Exception: If API call fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/send",
                json={
                    "to": to,
                    "subject": subject,
                    "body": body,
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10.0,
            )
            if response.status_code != 200:
                raise Exception(f"Email API returned {response.status_code}")

            logger.info("email_sent_successfully", to=to)
            return True
