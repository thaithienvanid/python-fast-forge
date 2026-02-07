"""Infrastructure services module.

Provides high-level services that can be used throughout the application.
"""

from .email_service import EmailService, get_email_service

__all__ = [
    "EmailService",
    "get_email_service",
]
