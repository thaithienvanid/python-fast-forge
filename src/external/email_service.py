"""External email service using HTTP API with circuit breaker protection.

This is a thin gateway to an external email provider API,
wrapped with circuit breaker for resilience.
"""

import httpx

from src.infrastructure.patterns.circuit_breaker import CircuitBreakerService


class EmailService:
    """Email service that sends via external HTTP API with circuit breaker.

    Attributes:
        _api_key: API key for the email provider
        _circuit_breaker: Circuit breaker service for resilience
        _base_url: Base URL for the email provider API
    """

    def __init__(self, circuit_breaker: CircuitBreakerService, api_key: str) -> None:
        self._api_key = api_key
        self._circuit_breaker = circuit_breaker
        self._base_url = "https://api.emailprovider.com"

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email via circuit breaker.

        Returns True on success, False on any failure.
        """
        try:
            result = await self._circuit_breaker.call_with_breaker(
                breaker_name="email_service",
                func=self._send_email_internal,
                to=to,
                subject=subject,
                body=body,
            )
            return bool(result)
        except Exception:
            return False

    async def _send_email_internal(self, to: str, subject: str, body: str) -> bool:
        """Send email via HTTP API.

        Raises on non-200 responses and network errors.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/send",
                json={"to": to, "subject": subject, "body": body},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10.0,
            )

        if response.status_code != 200:
            raise Exception(f"Email API returned {response.status_code}")

        return True
