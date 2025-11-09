"""Temporal client for starting workflows from the API."""

from temporalio.client import Client

from src.infrastructure.config import get_settings
from src.infrastructure.logging.config import get_logger


logger = get_logger(__name__)
settings = get_settings()

_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create Temporal client.

    Returns:
        Temporal client instance
    """
    global _client

    if _client is None:
        logger.info(
            "creating_temporal_client",
            host=settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        _client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        logger.info("temporal_client_created")

    return _client


async def close_temporal_client() -> None:
    """Close Temporal client connection."""
    global _client

    if _client is not None:
        logger.info("closing_temporal_client")
        # Temporal client doesn't need explicit closing in Python SDK
        _client = None
        logger.info("temporal_client_closed")
