"""Built-in plugin implementations.

This package provides ready-to-use plugin implementations for common
integration needs:

- Email: SMTP, SendGrid, SES
- Storage: Local, S3, GCS, Azure Blob
- Auth: JWT, OAuth2, SAML, LDAP

Example:
    >>> from src.infrastructure.plugins.builtin import (
    ...     SMTPEmailPlugin,
    ...     S3StoragePlugin,
    ...     JWTAuthPlugin,
    ... )
    >>>
    >>> # Register plugins
    >>> manager = PluginManager()
    >>> await manager.register_plugin(SMTPEmailPlugin, config={...})
    >>> await manager.register_plugin(S3StoragePlugin, config={...})
    >>> await manager.register_plugin(JWTAuthPlugin, config={...})
"""

from src.infrastructure.plugins.builtin.auth import (
    AuthPlugin,
    JWTAuthPlugin,
    OAuth2AuthPlugin,
)
from src.infrastructure.plugins.builtin.email import (
    EmailPlugin,
    SendGridEmailPlugin,
    SMTPEmailPlugin,
)
from src.infrastructure.plugins.builtin.storage import (
    LocalStoragePlugin,
    S3StoragePlugin,
    StoragePlugin,
)


__all__ = [
    # Auth plugins
    "AuthPlugin",
    # Email plugins
    "EmailPlugin",
    "JWTAuthPlugin",
    "LocalStoragePlugin",
    "OAuth2AuthPlugin",
    "S3StoragePlugin",
    "SMTPEmailPlugin",
    "SendGridEmailPlugin",
    # Storage plugins
    "StoragePlugin",
]
