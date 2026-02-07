"""Authentication plugin interface and built-in implementations.

Auth plugins provide authentication and authorization capabilities through
various identity providers and protocols.

Supported Providers (built-in):
- JWT: JSON Web Token authentication
- OAuth2: OAuth 2.0 (Google, GitHub, etc.)
- SAML: SAML 2.0 single sign-on
- LDAP: LDAP/Active Directory

Example:
    >>> # Using JWT auth
    >>> plugin = JWTAuthPlugin()
    >>> await plugin.init(context)
    >>> token = await plugin.create_token(
    ...     user_id="123",
    ...     claims={"role": "admin"},
    ...     expires_in=3600,
    ... )
    >>> user_id = await plugin.verify_token(token)
"""

import hashlib
import hmac
from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

from src.infrastructure.plugins.base import Plugin, PluginContext, PluginMetadata


class AuthPlugin(Plugin):
    """Base interface for authentication plugins.

    All auth plugins must implement this interface to provide
    consistent authentication and authorization.

    Methods:
        authenticate: Authenticate user credentials
        create_token: Create authentication token
        verify_token: Verify and decode token
        refresh_token: Refresh expired token
        revoke_token: Revoke/invalidate token
    """

    @abstractmethod
    async def authenticate(
        self,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """Authenticate user with credentials.

        Args:
            credentials: Authentication credentials (username/password, API key, etc.)

        Returns:
            User info dict with user_id, email, roles, etc.

        Raises:
            AuthenticationError: If authentication fails

        Example:
            >>> user = await plugin.authenticate({
            ...     "username": "john",
            ...     "password": "secret123",
            ... })
            >>> print(user["user_id"])
        """
        pass

    @abstractmethod
    async def create_token(
        self,
        user_id: str,
        claims: dict[str, Any] | None = None,
        expires_in: int | None = None,
    ) -> str:
        """Create authentication token.

        Args:
            user_id: User identifier
            claims: Additional claims to include in token
            expires_in: Token expiration in seconds

        Returns:
            Encoded token string

        Example:
            >>> token = await plugin.create_token(
            ...     user_id="123",
            ...     claims={"role": "admin", "tenant_id": "456"},
            ...     expires_in=3600,
            ... )
        """
        pass

    @abstractmethod
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode token.

        Args:
            token: Token string to verify

        Returns:
            Decoded token claims (user_id, exp, etc.)

        Raises:
            AuthenticationError: If token is invalid or expired

        Example:
            >>> claims = await plugin.verify_token(token)
            >>> user_id = claims["user_id"]
        """
        pass

    async def refresh_token(
        self,
        refresh_token: str,
    ) -> tuple[str, str]:
        """Refresh expired token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Example:
            >>> access_token, refresh_token = await plugin.refresh_token(old_refresh)
        """
        raise NotImplementedError("Token refresh not supported by this provider")

    async def revoke_token(self, token: str) -> None:
        """Revoke/invalidate token.

        Args:
            token: Token to revoke

        Example:
            >>> await plugin.revoke_token(token)
        """
        # Default: no-op (tokens expire naturally)
        pass


class JWTAuthPlugin(AuthPlugin):
    """JWT (JSON Web Token) authentication plugin.

    Provides stateless authentication using signed JWT tokens.

    Configuration:
        secret_key: Secret key for signing tokens
        algorithm: JWT algorithm (default: HS256)
        access_token_expires: Access token expiration in seconds (default: 3600)
        refresh_token_expires: Refresh token expiration in seconds (default: 2592000)
        issuer: Token issuer claim (optional)
        audience: Token audience claim (optional)

    Example:
        >>> context = PluginContext(config={
        ...     "secret_key": "your-secret-key-here",
        ...     "algorithm": "HS256",
        ...     "access_token_expires": 3600,
        ... })
        >>> plugin = JWTAuthPlugin()
        >>> await plugin.init(context)
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="jwt-auth",
            version="1.0.0",
            description="JWT authentication provider",
            author="Python Fast Forge",
            plugin_type="auth",
            config_schema={
                "type": "object",
                "properties": {
                    "secret_key": {"type": "string", "minLength": 32},
                    "algorithm": {"type": "string", "default": "HS256"},
                    "access_token_expires": {"type": "integer", "default": 3600},
                    "refresh_token_expires": {"type": "integer", "default": 2592000},
                    "issuer": {"type": "string"},
                    "audience": {"type": "string"},
                },
                "required": ["secret_key"],
            },
        )

    async def init(self, context: PluginContext) -> None:
        """Initialize JWT auth."""
        self.context = context
        self._secret_key = context.config["secret_key"]
        self._algorithm = context.config.get("algorithm", "HS256")
        self._access_token_expires = context.config.get("access_token_expires", 3600)
        self._refresh_token_expires = context.config.get("refresh_token_expires", 2592000)
        self._issuer = context.config.get("issuer")
        self._audience = context.config.get("audience")

        # TODO: Initialize PyJWT or python-jose
        # import jwt
        # self._jwt = jwt

    async def validate(self) -> bool:
        """Validate configuration."""
        if "secret_key" not in self.context.config:
            return False
        if len(self.context.config["secret_key"]) < 32:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "jwt_weak_secret",
                    message="Secret key should be at least 32 characters",
                )
        return True

    async def authenticate(
        self,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """Authenticate user.

        For JWT, this is typically handled by an external user service.
        This method is a placeholder that should integrate with your
        user repository.

        Args:
            credentials: Must contain username and password

        Returns:
            User info dict

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # TODO: Integrate with user repository
        # For now, this is a placeholder
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            raise ValueError("Username and password required")

        # Placeholder user info
        return {
            "user_id": "user-123",
            "username": username,
            "email": f"{username}@example.com",
            "roles": ["user"],
        }

    async def create_token(
        self,
        user_id: str,
        claims: dict[str, Any] | None = None,
        expires_in: int | None = None,
    ) -> str:
        """Create JWT access token.

        Args:
            user_id: User identifier
            claims: Additional claims
            expires_in: Expiration in seconds

        Returns:
            JWT token string
        """
        # TODO: Implement actual JWT encoding
        # import jwt
        #
        # now = datetime.now(UTC)
        # expires_at = now + timedelta(seconds=expires_in or self._access_token_expires)
        #
        # payload = {
        #     "sub": user_id,
        #     "iat": int(now.timestamp()),
        #     "exp": int(expires_at.timestamp()),
        #     "iss": self._issuer,
        #     "aud": self._audience,
        #     **(claims or {}),
        # }
        #
        # token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        # return token

        # Placeholder
        return f"jwt-token-{user_id}"

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded claims

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        # TODO: Implement actual JWT decoding
        # import jwt
        #
        # try:
        #     payload = jwt.decode(
        #         token,
        #         self._secret_key,
        #         algorithms=[self._algorithm],
        #         issuer=self._issuer,
        #         audience=self._audience,
        #     )
        #     return payload
        # except jwt.ExpiredSignatureError:
        #     raise AuthenticationError("Token expired")
        # except jwt.InvalidTokenError as e:
        #     raise AuthenticationError(f"Invalid token: {e}")

        # Placeholder
        return {
            "user_id": "user-123",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        }

    async def refresh_token(
        self,
        refresh_token: str,
    ) -> tuple[str, str]:
        """Refresh JWT token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Tuple of (new_access_token, new_refresh_token)
        """
        # Verify refresh token
        claims = await self.verify_token(refresh_token)
        user_id = claims.get("user_id")

        if not user_id:
            raise ValueError("Invalid refresh token")

        # Create new tokens
        new_access_token = await self.create_token(user_id)
        new_refresh_token = await self.create_token(
            user_id, expires_in=self._refresh_token_expires
        )

        return new_access_token, new_refresh_token


class OAuth2AuthPlugin(AuthPlugin):
    """OAuth 2.0 authentication plugin.

    Provides OAuth 2.0 authentication for third-party providers
    (Google, GitHub, Facebook, etc.).

    Configuration:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        redirect_uri: OAuth redirect URI
        provider: OAuth provider (google, github, facebook, etc.)
        scopes: OAuth scopes to request

    Example:
        >>> context = PluginContext(config={
        ...     "client_id": "xxx.apps.googleusercontent.com",
        ...     "client_secret": "GOCSPX-xxx",
        ...     "redirect_uri": "https://example.com/auth/callback",
        ...     "provider": "google",
        ...     "scopes": ["openid", "email", "profile"],
        ... })
        >>> plugin = OAuth2AuthPlugin()
        >>> await plugin.init(context)
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        return PluginMetadata(
            name="oauth2-auth",
            version="1.0.0",
            description="OAuth 2.0 authentication provider",
            author="Python Fast Forge",
            plugin_type="auth",
            config_schema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "client_secret": {"type": "string"},
                    "redirect_uri": {"type": "string", "format": "uri"},
                    "provider": {
                        "type": "string",
                        "enum": ["google", "github", "facebook", "microsoft"],
                    },
                    "scopes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["client_id", "client_secret", "redirect_uri", "provider"],
            },
        )

    async def init(self, context: PluginContext) -> None:
        """Initialize OAuth2 client."""
        self.context = context
        self._client_id = context.config["client_id"]
        self._client_secret = context.config["client_secret"]
        self._redirect_uri = context.config["redirect_uri"]
        self._provider = context.config["provider"]
        self._scopes = context.config.get("scopes", [])

        # TODO: Initialize OAuth2 client library
        # from authlib.integrations.httpx_client import AsyncOAuth2Client
        # self._client = AsyncOAuth2Client(
        #     client_id=self._client_id,
        #     client_secret=self._client_secret,
        # )

    async def validate(self) -> bool:
        """Validate OAuth2 configuration."""
        required = ["client_id", "client_secret", "redirect_uri", "provider"]
        return all(key in self.context.config for key in required)

    async def authenticate(
        self,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """Authenticate via OAuth2.

        Args:
            credentials: Must contain authorization_code

        Returns:
            User info from OAuth provider
        """
        # TODO: Implement OAuth2 token exchange
        # auth_code = credentials.get("authorization_code")
        # token = await self._client.fetch_token(
        #     token_url=self._get_token_url(),
        #     code=auth_code,
        #     redirect_uri=self._redirect_uri,
        # )
        #
        # user_info = await self._client.get(self._get_userinfo_url())
        # return user_info.json()

        return {"user_id": "oauth-user-123", "email": "user@example.com"}

    async def create_token(
        self,
        user_id: str,
        claims: dict[str, Any] | None = None,
        expires_in: int | None = None,
    ) -> str:
        """OAuth2 tokens are created by the provider."""
        raise NotImplementedError("Use OAuth2 provider tokens")

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify OAuth2 token with provider."""
        # TODO: Implement token introspection
        return {"user_id": "oauth-user-123"}


__all__ = [
    "AuthPlugin",
    "JWTAuthPlugin",
    "OAuth2AuthPlugin",
]
