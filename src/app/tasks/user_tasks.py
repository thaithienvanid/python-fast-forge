"""User-related background workflows and activities."""

from datetime import timedelta
from typing import Any

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from src.infrastructure.logging.config import get_logger
from src.infrastructure.services import get_email_service


logger = get_logger(__name__)


@activity.defn(name="send_welcome_email")
async def send_welcome_email_activity(user_id: str, email: str) -> dict[str, Any]:
    """Send welcome email to new user.

    Args:
        user_id: User UUID
        email: User email address

    Returns:
        Activity result dictionary
    """
    try:
        logger.info("sending_welcome_email", user_id=user_id, email=email)

        # Get email service
        email_service = get_email_service()

        # Send welcome email
        message_id = await email_service.send_email(
            to=email,
            subject="Welcome to Python Fast Forge!",
            body=f"""
                <html>
                <body>
                    <h1>Welcome to Python Fast Forge!</h1>
                    <p>Hi there,</p>
                    <p>Thank you for joining our platform. We're excited to have you on board!</p>
                    <p>Your user ID is: <code>{user_id}</code></p>
                    <p>If you have any questions, feel free to reach out to our support team.</p>
                    <br>
                    <p>Best regards,<br>The Python Fast Forge Team</p>
                </body>
                </html>
            """,
            html=True,
        )

        logger.info(
            "welcome_email_sent",
            user_id=user_id,
            email=email,
            message_id=message_id,
        )
        return {
            "status": "success",
            "user_id": user_id,
            "email": email,
            "message_id": message_id,
        }
    except Exception as exc:
        logger.error("welcome_email_failed", user_id=user_id, error=str(exc))
        raise


@workflow.defn(name="SendWelcomeEmailWorkflow")
class SendWelcomeEmailWorkflow:
    """Workflow for sending welcome email with retry logic."""

    @workflow.run
    async def run(self, user_id: str, email: str) -> dict[str, Any]:
        """Execute the workflow.

        Args:
            user_id: User UUID
            email: User email address

        Returns:
            Workflow result dictionary
        """
        result: dict[str, Any] = await workflow.execute_activity(
            send_welcome_email_activity,
            args=[user_id, email],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=1),
                maximum_attempts=3,
                backoff_coefficient=2.0,
            ),
        )
        return result
