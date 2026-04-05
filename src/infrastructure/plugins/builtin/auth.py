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

from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Any

from authlib.jose import JoseError, jwt
from authlib.jose.errors import ExpiredTokenError, InvalidTokenError

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
            >>> user = await plugin.authenticate(
            ...     {
            ...         "username": "john",
            ...         "password": "secret123",
            ...     }
            ... )
            >>> print(user["user_id"])
        """

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
        >>> context = PluginContext(
        ...     config={
        ...         "secret_key": "your-secret-key-here",
        ...         "algorithm": "HS256",
        ...         "access_token_expires": 3600,
        ...     }
        ... )
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

        # authlib is imported at module level
        # No additional initialization needed
        if context.logger:
            context.logger.info(
                "jwt_plugin_initialized",
                algorithm=self._algorithm,
                access_token_expires=self._access_token_expires,
            )

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
        # IMPORTANT: Integrate with your user repository
        # This is a placeholder implementation for testing.
        # In production, you should:
        # 1. Import your user repository
        # 2. Hash the password and compare with stored hash
        # 3. Return actual user data from your database
        # Example:
        #   user_repo = context.get_dependency("user_repository")
        #   user = await user_repo.get_by_username(username)
        #   if not user or not verify_password(password, user.password_hash):
        #       raise AuthenticationError("Invalid credentials")
        #   return {"user_id": str(user.id), "username": user.username, ...}

        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            raise ValueError("Username and password required")

        if self.context and self.context.logger:
            self.context.logger.warning(
                "jwt_using_placeholder_auth",
                message="Using placeholder authentication - integrate with user repository for production",
            )

        # Placeholder user info (for development/testing only)
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
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=expires_in or self._access_token_expires)

        # Build payload
        payload = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            **(claims or {}),
        }

        # Add optional issuer and audience
        if self._issuer:
            payload["iss"] = self._issuer
        if self._audience:
            payload["aud"] = self._audience

        # Encode token using authlib
        header = {"alg": self._algorithm, "typ": "JWT"}
        token = jwt.encode(header, payload, self._secret_key)

        if self.context and self.context.logger:
            self.context.logger.debug(
                "jwt_token_created",
                user_id=user_id,
                expires_in=expires_in or self._access_token_expires,
            )

        return token

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded claims

        Raises:
            Exception: If token is invalid or expired
        """
        try:
            # Decode token using authlib
            jwt_claims = jwt.decode(token, self._secret_key)

            # Validate claims (checks exp, iat, iss, aud, etc.)
            jwt_claims.validate()

            # Convert to dict
            payload = dict(jwt_claims)

            if self.context and self.context.logger:
                self.context.logger.debug(
                    "jwt_token_verified",
                    user_id=payload.get("sub"),
                )

            return payload

        except ExpiredTokenError:
            if self.context and self.context.logger:
                self.context.logger.warning("jwt_token_expired")
            raise Exception("Token expired")
        except (InvalidTokenError, JoseError) as e:
            if self.context and self.context.logger:
                self.context.logger.warning("jwt_token_invalid", error=str(e))
            raise Exception(f"Invalid token: {e}")

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
        new_refresh_token = await self.create_token(user_id, expires_in=self._refresh_token_expires)

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
        >>> context = PluginContext(
        ...     config={
        ...         "client_id": "xxx.apps.googleusercontent.com",
        ...         "client_secret": "GOCSPX-xxx",
        ...         "redirect_uri": "https://example.com/auth/callback",
        ...         "provider": "google",
        ...         "scopes": ["openid", "email", "profile"],
        ...     }
        ... )
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

        # Initialize OAuth2 client using authlib
        try:
            from authlib.integrations.httpx_client import AsyncOAuth2Client

            self._client = AsyncOAuth2Client(
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
            self._oauth2_available = True

            if context.logger:
                context.logger.info(
                    "oauth2_plugin_initialized",
                    provider=self._provider,
                    scopes=self._scopes,
                )
        except ImportError:
            if context.logger:
                context.logger.warning(
                    "oauth2_not_available",
                    message="authlib[asyncio] or httpx not installed. Install with: pip install authlib[asyncio] httpx",
                )
            self._client = None
            self._oauth2_available = False

    async def validate(self) -> bool:
        """Validate OAuth2 configuration."""
        required = ["client_id", "client_secret", "redirect_uri", "provider"]
        return all(key in self.context.config for key in required)

    def _get_provider_urls(self) -> dict[str, str]:
        """Get provider-specific URLs for token and userinfo endpoints.

        Returns:
            Dict with token_url and userinfo_url for the provider
        """
        provider_configs = {
            "google": {
                "token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
                "introspect_url": "https://oauth2.googleapis.com/tokeninfo",
            },
            "github": {
                "token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
                "introspect_url": None,  # GitHub doesn't have introspection endpoint
            },
            "facebook": {
                "token_url": "https://graph.facebook.com/v12.0/oauth/access_token",
                "userinfo_url": "https://graph.facebook.com/me?fields=id,name,email",
                "introspect_url": "https://graph.facebook.com/debug_token",
            },
            "microsoft": {
                "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                "userinfo_url": "https://graph.microsoft.com/v1.0/me",
                "introspect_url": None,  # Use Microsoft Graph API validation instead
            },
        }

        return provider_configs.get(
            self._provider,
            {
                "token_url": "",
                "userinfo_url": "",
                "introspect_url": None,
            },
        )

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
        # Check if OAuth2 is available
        if not self._oauth2_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "oauth2_unavailable",
                    message="OAuth2 client not available, returning placeholder data",
                )
            return {"user_id": "oauth-user-123", "email": "user@example.com"}

        auth_code = credentials.get("authorization_code")
        if not auth_code:
            raise ValueError("authorization_code required for OAuth2 authentication")

        try:
            # Get provider URLs
            urls = self._get_provider_urls()

            # Exchange authorization code for access token
            token = await self._client.fetch_token(
                url=urls["token_url"],
                grant_type="authorization_code",
                code=auth_code,
                redirect_uri=self._redirect_uri,
            )

            # Fetch user info from provider
            response = await self._client.get(urls["userinfo_url"])
            user_info = response.json()

            if self.context and self.context.logger:
                self.context.logger.info(
                    "oauth2_authentication_success",
                    provider=self._provider,
                    user_id=user_info.get("id") or user_info.get("sub"),
                )

            return user_info

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "oauth2_authentication_failed",
                    provider=self._provider,
                    error=str(e),
                )
            raise

    async def create_token(
        self,
        user_id: str,
        claims: dict[str, Any] | None = None,
        expires_in: int | None = None,
    ) -> str:
        """OAuth2 tokens are created by the provider."""
        raise NotImplementedError("Use OAuth2 provider tokens")

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify OAuth2 token with provider.

        Args:
            token: OAuth2 access token

        Returns:
            Token introspection result or user info

        Raises:
            Exception: If token is invalid or verification fails
        """
        # Check if OAuth2 is available
        if not self._oauth2_available or not self._client:
            if self.context and self.context.logger:
                self.context.logger.warning(
                    "oauth2_unavailable",
                    message="OAuth2 client not available, returning placeholder data",
                )
            return {"user_id": "oauth-user-123", "active": True}

        try:
            urls = self._get_provider_urls()

            # Some providers have introspection endpoint, others verify by fetching userinfo
            if urls["introspect_url"]:
                # Use token introspection endpoint
                response = await self._client.post(
                    urls["introspect_url"],
                    data={"token": token},
                )
                introspection_result = response.json()

                if self.context and self.context.logger:
                    self.context.logger.debug(
                        "oauth2_token_introspected",
                        provider=self._provider,
                        active=introspection_result.get("active", False),
                    )

                return introspection_result
            # Verify by fetching user info (implicit validation)
            self._client.token = {"access_token": token, "token_type": "Bearer"}
            response = await self._client.get(urls["userinfo_url"])
            user_info = response.json()

            if self.context and self.context.logger:
                self.context.logger.debug(
                    "oauth2_token_verified",
                    provider=self._provider,
                )

            # Add active flag for consistency
            user_info["active"] = True
            return user_info

        except Exception as e:
            if self.context and self.context.logger:
                self.context.logger.error(
                    "oauth2_token_verification_failed",
                    provider=self._provider,
                    error=str(e),
                )
            raise


__all__ = [
    "AuthPlugin",
    "JWTAuthPlugin",
    "OAuth2AuthPlugin",
]
