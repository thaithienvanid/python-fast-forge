"""Main entry point for the FastAPI application."""

import uvicorn

from src.infrastructure.config import get_settings
from src.presentation.api import create_app


app = create_app()


def main() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
