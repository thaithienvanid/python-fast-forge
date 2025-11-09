"""Temporal worker application for background workflows and activities."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from src.app.tasks.user_tasks import SendWelcomeEmailWorkflow, send_welcome_email_activity
from src.infrastructure.config import get_settings
from src.infrastructure.logging.config import configure_logging, get_logger


# Get settings
settings = get_settings()

# Configure logging
configure_logging(settings)
logger = get_logger(__name__)


async def main() -> None:
    """Start Temporal worker."""
    try:
        # Connect to Temporal server
        logger.info(
            "connecting_to_temporal",
            host=settings.temporal_host,
            namespace=settings.temporal_namespace,
        )

        client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )

        logger.info(
            "temporal_connected",
            host=settings.temporal_host,
            namespace=settings.temporal_namespace,
        )

        # Create worker
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[SendWelcomeEmailWorkflow],
            activities=[send_welcome_email_activity],
        )

        logger.info(
            "temporal_worker_starting",
            task_queue=settings.temporal_task_queue,
            workflows=["SendWelcomeEmailWorkflow"],
            activities=["send_welcome_email_activity"],
        )

        # Run worker
        await worker.run()

    except Exception as exc:
        logger.exception("temporal_worker_error", error=str(exc))
        raise


if __name__ == "__main__":
    asyncio.run(main())
