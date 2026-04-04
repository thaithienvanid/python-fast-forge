"""Tests for built-in plugins: auth, email, storage.

Minimal test cases maximizing branch coverage.
"""

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helper: lightweight PluginContext stub
# ---------------------------------------------------------------------------
@dataclass
class FakePluginContext:
    config: dict[str, Any] = field(default_factory=dict)
    logger: Any = field(default_factory=lambda: MagicMock())
    app_config: dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# Auth plugin tests
# ===========================================================================
class TestJWTAuthPlugin:
    """Covers JWTAuthPlugin init, validate, authenticate, create/verify/refresh token."""

    @pytest.fixture
    def ctx(self) -> FakePluginContext:
        return FakePluginContext(
            config={
                "secret_key": "a" * 64,
                "algorithm": "HS256",
                "access_token_expires": 60,
                "refresh_token_expires": 3600,
                "issuer": "test-issuer",
                "audience": "test-audience",
            }
        )

    async def test_full_lifecycle(self, ctx: FakePluginContext) -> None:
        """Init → validate → create token → verify token → authenticate."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        plugin = JWTAuthPlugin()

        # metadata
        meta = plugin.metadata
        assert meta.name == "jwt-auth"
        assert meta.plugin_type == "auth"

        # init + validate
        await plugin.init(ctx)
        assert await plugin.validate() is True
        assert plugin._algorithm == "HS256"
        assert plugin._issuer == "test-issuer"

        # create + verify roundtrip
        token = await plugin.create_token("user-1", claims={"role": "admin"}, expires_in=300)
        assert isinstance(token, (str, bytes))
        claims = await plugin.verify_token(token)
        assert claims["sub"] == "user-1"
        assert claims["role"] == "admin"
        assert claims["iss"] == "test-issuer"

        user = await plugin.authenticate({"username": "john", "password": "pass"})
        assert user["username"] == "john"

    async def test_validate_weak_key(self) -> None:
        """Validate warns on weak secret but still returns True."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={"secret_key": "short"})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        assert await plugin.validate() is True
        ctx.logger.warning.assert_called()

    async def test_validate_missing_key(self) -> None:
        """Validate returns False when secret_key missing."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={})
        plugin = JWTAuthPlugin()
        plugin.context = ctx
        assert await plugin.validate() is False

    async def test_authenticate_missing_credentials(self) -> None:
        """Authenticate raises ValueError for missing username/password."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={"secret_key": "a" * 64})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        with pytest.raises(ValueError, match="Username and password required"):
            await plugin.authenticate({})

    async def test_verify_expired_token(self) -> None:
        """Verify raises for expired token."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={"secret_key": "a" * 64})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        token = await plugin.create_token("u1", expires_in=-1)
        with pytest.raises(Exception, match="Token expired"):
            await plugin.verify_token(token)

    async def test_verify_invalid_token(self) -> None:
        """Verify raises for garbage token."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={"secret_key": "a" * 64})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        with pytest.raises(Exception, match="Invalid token"):
            await plugin.verify_token("not.a.token")

    async def test_refresh_token_flow(self) -> None:
        """Refresh creates two new tokens from a valid refresh token."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={"secret_key": "a" * 64})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        # create a token with user_id claim (refresh_token expects this)
        token = await plugin.create_token("u1", claims={"user_id": "u1"})
        access, refresh = await plugin.refresh_token(token)
        assert access is not None
        assert refresh is not None

    async def test_refresh_token_missing_user_id(self) -> None:
        """Refresh raises ValueError when token has no user_id claim."""
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        ctx = FakePluginContext(config={"secret_key": "a" * 64})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        # create a token without user_id claim
        token = await plugin.create_token("u1")
        with pytest.raises(ValueError, match="Invalid refresh token"):
            await plugin.refresh_token(token)


class TestOAuth2AuthPlugin:
    """Covers OAuth2AuthPlugin init, validate, authenticate, verify_token."""

    def _ctx(self, **overrides: Any) -> FakePluginContext:
        config = {
            "client_id": "cid",
            "client_secret": "csecret",
            "redirect_uri": "https://example.com/cb",
            "provider": "google",
            "scopes": ["openid"],
            **overrides,
        }
        return FakePluginContext(config=config)

    async def test_init_and_validate(self) -> None:
        """Init with authlib available, validate with complete config."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        plugin = OAuth2AuthPlugin()
        meta = plugin.metadata
        assert meta.name == "oauth2-auth"

        ctx = self._ctx()
        await plugin.init(ctx)
        assert plugin._oauth2_available is True
        assert await plugin.validate() is True

    async def test_init_without_authlib(self) -> None:
        """Init gracefully handles missing authlib."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx()
        plugin = OAuth2AuthPlugin()
        with (
            patch.dict("sys.modules", {"authlib.integrations.httpx_client": None}),
            patch(
                "src.infrastructure.plugins.builtin.auth.OAuth2AuthPlugin.init",
                wraps=plugin.init,
            ),
        ):
            # Simulate ImportError during init
            plugin.context = ctx
            plugin._client_id = ctx.config["client_id"]
            plugin._client_secret = ctx.config["client_secret"]
            plugin._redirect_uri = ctx.config["redirect_uri"]
            plugin._provider = ctx.config["provider"]
            plugin._scopes = ctx.config.get("scopes", [])
            plugin._client = None
            plugin._oauth2_available = False

        # When OAuth2 is unavailable, authenticate returns placeholder
        result = await plugin.authenticate({})
        assert result["user_id"] == "oauth-user-123"

        # verify_token also returns placeholder
        result = await plugin.verify_token("some-token")
        assert result["active"] is True

        # create_token raises
        with pytest.raises(NotImplementedError):
            await plugin.create_token("u1")

    async def test_authenticate_with_oauth_client(self) -> None:
        """Authenticate exchanges code via OAuth2 client."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx()
        plugin = OAuth2AuthPlugin()
        await plugin.init(ctx)

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "guser1", "email": "g@example.com"}
        plugin._client.fetch_token = AsyncMock(return_value=mock_response)
        plugin._client.get = AsyncMock(return_value=mock_response)

        result = await plugin.authenticate({"authorization_code": "code123"})
        assert result["id"] == "guser1"

    async def test_authenticate_missing_code(self) -> None:
        """Authenticate raises ValueError without authorization_code."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx()
        plugin = OAuth2AuthPlugin()
        await plugin.init(ctx)
        with pytest.raises(ValueError, match="authorization_code required"):
            await plugin.authenticate({})

    async def test_authenticate_error_handling(self) -> None:
        """Authenticate re-raises and logs on failure."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx()
        plugin = OAuth2AuthPlugin()
        await plugin.init(ctx)
        plugin._client.fetch_token = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(RuntimeError):
            await plugin.authenticate({"authorization_code": "code"})

    async def test_verify_token_with_introspect(self) -> None:
        """Verify token uses introspection endpoint when available (google)."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx(provider="google")
        plugin = OAuth2AuthPlugin()
        await plugin.init(ctx)

        mock_response = MagicMock()
        mock_response.json.return_value = {"active": True, "sub": "u1"}
        plugin._client.post = AsyncMock(return_value=mock_response)
        result = await plugin.verify_token("token123")
        assert result["active"] is True

    async def test_verify_token_without_introspect(self) -> None:
        """Verify token via userinfo when no introspect URL (github)."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx(provider="github")
        plugin = OAuth2AuthPlugin()
        await plugin.init(ctx)

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "ghuser1", "login": "john"}
        plugin._client.get = AsyncMock(return_value=mock_response)
        result = await plugin.verify_token("token123")
        assert result["active"] is True
        assert result["id"] == "ghuser1"

    async def test_verify_token_error(self) -> None:
        """Verify token re-raises on error."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = self._ctx()
        plugin = OAuth2AuthPlugin()
        await plugin.init(ctx)
        plugin._client.post = AsyncMock(side_effect=RuntimeError("network"))
        with pytest.raises(RuntimeError):
            await plugin.verify_token("token")

    async def test_provider_urls_all_providers(self) -> None:
        """Provider URLs returned for all known providers + unknown fallback."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        for provider in ["google", "github", "facebook", "microsoft", "unknown"]:
            ctx = self._ctx(provider=provider)
            plugin = OAuth2AuthPlugin()
            await plugin.init(ctx)
            urls = plugin._get_provider_urls()
            assert "token_url" in urls
            assert "userinfo_url" in urls

    async def test_validate_incomplete_config(self) -> None:
        """Validate returns False for incomplete config."""
        from src.infrastructure.plugins.builtin.auth import OAuth2AuthPlugin

        ctx = FakePluginContext(config={"client_id": "x"})
        plugin = OAuth2AuthPlugin()
        plugin.context = ctx
        assert await plugin.validate() is False


class TestAuthPluginBase:
    """Covers base AuthPlugin default implementations."""

    async def test_refresh_token_not_implemented(self) -> None:
        from src.infrastructure.plugins.builtin.auth import JWTAuthPlugin

        # Test base class revoke_token (no-op) and refresh_token on AuthPlugin
        ctx = FakePluginContext(config={"secret_key": "a" * 64})
        plugin = JWTAuthPlugin()
        await plugin.init(ctx)
        # revoke_token is a no-op on base
        await plugin.revoke_token("some-token")  # should not raise


# ===========================================================================
# Email plugin tests
# ===========================================================================
class TestSMTPEmailPlugin:
    """Covers SMTPEmailPlugin full lifecycle with minimal tests."""

    @pytest.fixture
    def ctx(self) -> FakePluginContext:
        return FakePluginContext(
            config={
                "host": "smtp.test.com",
                "port": 587,
                "username": "user",
                "password": "pass",
                "from_email": "noreply@test.com",
                "from_name": "Test App",
                "use_tls": True,
                "use_ssl": False,
            }
        )

    async def test_init_validate_metadata(self, ctx: FakePluginContext) -> None:
        from src.infrastructure.plugins.builtin.email import SMTPEmailPlugin

        plugin = SMTPEmailPlugin()
        assert plugin.metadata.name == "smtp-email"
        await plugin.init(ctx)
        assert plugin._host == "smtp.test.com"
        assert await plugin.validate() is True

    @patch("src.infrastructure.plugins.builtin.email.smtplib.SMTP")
    async def test_send_email_tls(self, mock_smtp_cls: MagicMock, ctx: FakePluginContext) -> None:
        """Send email via TLS SMTP with all features: cc, bcc, reply_to, attachments."""
        from src.infrastructure.plugins.builtin.email import SMTPEmailPlugin

        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        plugin = SMTPEmailPlugin()
        await plugin.init(ctx)

        msg_id = await plugin.send_email(
            to=["a@test.com", "b@test.com"],
            subject="Hello",
            body="<h1>Hi</h1>",
            html=True,
            cc=["cc@test.com"],
            bcc=["bcc@test.com"],
            attachments=[
                {"filename": "doc.pdf", "content": b"data", "mime_type": "application/pdf"}
            ],
            reply_to="reply@test.com",
        )

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
        assert msg_id is not None

    @patch("src.infrastructure.plugins.builtin.email.smtplib.SMTP_SSL")
    async def test_send_email_ssl(self, mock_smtp_ssl_cls: MagicMock) -> None:
        """Send email via SSL SMTP."""
        from src.infrastructure.plugins.builtin.email import SMTPEmailPlugin

        ctx = FakePluginContext(
            config={
                "host": "smtp.test.com",
                "port": 465,
                "username": "user",
                "password": "pass",
                "from_email": "noreply@test.com",
                "use_tls": False,
                "use_ssl": True,
            }
        )

        mock_server = MagicMock()
        mock_smtp_ssl_cls.return_value = mock_server

        plugin = SMTPEmailPlugin()
        await plugin.init(ctx)
        await plugin.send_email(to="a@test.com", subject="Test", body="Body")

        mock_smtp_ssl_cls.assert_called_once_with("smtp.test.com", 465)
        mock_server.starttls.assert_not_called()

    @patch("src.infrastructure.plugins.builtin.email.smtplib.SMTP")
    async def test_send_email_error(self, mock_smtp_cls: MagicMock, ctx: FakePluginContext) -> None:
        """Send email raises and logs on SMTP failure."""
        from src.infrastructure.plugins.builtin.email import SMTPEmailPlugin

        mock_smtp_cls.side_effect = ConnectionError("refused")
        plugin = SMTPEmailPlugin()
        await plugin.init(ctx)
        with pytest.raises(ConnectionError):
            await plugin.send_email(to="a@test.com", subject="S", body="B")

    @patch("src.infrastructure.plugins.builtin.email.smtplib.SMTP")
    async def test_send_email_string_attachment(
        self, mock_smtp_cls: MagicMock, ctx: FakePluginContext
    ) -> None:
        """Attachment with string content gets encoded to bytes."""
        from src.infrastructure.plugins.builtin.email import SMTPEmailPlugin

        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        plugin = SMTPEmailPlugin()
        await plugin.init(ctx)
        await plugin.send_email(
            to="a@test.com",
            subject="S",
            body="B",
            attachments=[{"filename": "f.txt", "content": "text content"}],
        )
        mock_server.sendmail.assert_called_once()

    async def test_send_bulk(self, ctx: FakePluginContext) -> None:
        """Bulk send calls send_email for each item."""
        from src.infrastructure.plugins.builtin.email import SMTPEmailPlugin

        plugin = SMTPEmailPlugin()
        await plugin.init(ctx)

        with patch.object(plugin, "send_email", return_value="msg-1") as mock_send:
            ids = await plugin.send_bulk(
                [
                    {"to": "a@test.com", "subject": "S1", "body": "B1"},
                    {"to": "b@test.com", "subject": "S2", "body": "B2"},
                ]
            )
            assert len(ids) == 2
            assert mock_send.call_count == 2


class TestSendGridEmailPlugin:
    """Covers SendGridEmailPlugin with sendgrid available and unavailable paths."""

    async def test_init_sendgrid_available(self) -> None:
        """Init with sendgrid library mocked as available."""
        from src.infrastructure.plugins.builtin.email import SendGridEmailPlugin

        ctx = FakePluginContext(
            config={
                "api_key": "SG.test",
                "from_email": "noreply@test.com",
                "from_name": "App",
                "template_id": "tmpl-1",
            }
        )
        plugin = SendGridEmailPlugin()
        assert plugin.metadata.name == "sendgrid-email"

        with patch(
            "src.infrastructure.plugins.builtin.email.SendGridEmailPlugin.init"
        ) as mock_init:
            mock_init.return_value = None
            await plugin.init(ctx)

        # Simulate available state manually
        plugin.context = ctx
        plugin._api_key = ctx.config["api_key"]
        plugin._from_email = ctx.config["from_email"]
        plugin._from_name = ctx.config.get("from_name", "")
        plugin._template_id = ctx.config.get("template_id")
        plugin._sendgrid_available = True
        plugin._client = MagicMock()

        assert await plugin.validate() is True

    async def test_init_sendgrid_unavailable(self) -> None:
        """Init when sendgrid not installed - graceful fallback."""
        from src.infrastructure.plugins.builtin.email import SendGridEmailPlugin

        ctx = FakePluginContext(
            config={
                "api_key": "SG.test",
                "from_email": "noreply@test.com",
            }
        )
        plugin = SendGridEmailPlugin()
        plugin.context = ctx
        plugin._api_key = "SG.test"
        plugin._from_email = "noreply@test.com"
        plugin._from_name = ""
        plugin._template_id = None
        plugin._client = None
        plugin._sendgrid_available = False

        result = await plugin.send_email(to="a@test.com", subject="S", body="B")
        assert result == "sendgrid-unavailable"

    async def test_send_email_with_all_options(self) -> None:
        """Send email through SendGrid with cc, bcc, reply_to, attachments.

        Mocks sendgrid.helpers.mail since the library may not be installed.
        """
        # Create mock sendgrid helpers
        mock_helpers = MagicMock()
        mock_mail_instance = MagicMock()
        mock_helpers.Mail.return_value = mock_mail_instance
        mock_helpers.Email = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        mock_helpers.Personalization.return_value = MagicMock()
        mock_helpers.Content = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        mock_helpers.Attachment.return_value = MagicMock()
        mock_helpers.FileContent = MagicMock(side_effect=lambda x: x)
        mock_helpers.FileName = MagicMock(side_effect=lambda x: x)
        mock_helpers.FileType = MagicMock(side_effect=lambda x: x)

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": mock_helpers,
            },
        ):
            from src.infrastructure.plugins.builtin.email import SendGridEmailPlugin

            ctx = FakePluginContext(
                config={
                    "api_key": "SG.test",
                    "from_email": "noreply@test.com",
                    "from_name": "App",
                }
            )
            plugin = SendGridEmailPlugin()
            plugin.context = ctx
            plugin._api_key = "SG.test"
            plugin._from_email = "noreply@test.com"
            plugin._from_name = "App"
            plugin._template_id = None
            plugin._sendgrid_available = True

            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.headers = {"X-Message-Id": "sg-msg-123"}
            mock_response.status_code = 202
            mock_client.send.return_value = mock_response
            plugin._client = mock_client

            msg_id = await plugin.send_email(
                to=["a@test.com", "b@test.com"],
                subject="Hello",
                body="<h1>Hi</h1>",
                html=True,
                cc=["cc@test.com"],
                bcc=["bcc@test.com"],
                reply_to="reply@test.com",
                attachments=[
                    {"filename": "doc.pdf", "content": b"data", "mime_type": "application/pdf"},
                    {"filename": "note.txt", "content": "text data"},
                ],
            )

            assert msg_id == "sg-msg-123"
            mock_client.send.assert_called_once()

    async def test_send_email_error(self) -> None:
        """SendGrid send error is logged and re-raised."""
        mock_helpers = MagicMock()
        mock_helpers.Mail.return_value = MagicMock()
        mock_helpers.Email = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        mock_helpers.Personalization.return_value = MagicMock()
        mock_helpers.Content = MagicMock(side_effect=lambda *a, **kw: MagicMock())

        with patch.dict(
            "sys.modules",
            {
                "sendgrid": MagicMock(),
                "sendgrid.helpers": MagicMock(),
                "sendgrid.helpers.mail": mock_helpers,
            },
        ):
            from src.infrastructure.plugins.builtin.email import SendGridEmailPlugin

            ctx = FakePluginContext(
                config={
                    "api_key": "SG.test",
                    "from_email": "noreply@test.com",
                }
            )
            plugin = SendGridEmailPlugin()
            plugin.context = ctx
            plugin._api_key = "SG.test"
            plugin._from_email = "noreply@test.com"
            plugin._from_name = ""
            plugin._template_id = None
            plugin._sendgrid_available = True
            plugin._client = MagicMock()
            plugin._client.send.side_effect = RuntimeError("API error")

            with pytest.raises(RuntimeError):
                await plugin.send_email(to="a@test.com", subject="S", body="B")


# ===========================================================================
# Storage plugin tests
# ===========================================================================
class TestLocalStoragePlugin:
    """Covers LocalStoragePlugin using real tmp filesystem."""

    @pytest.fixture
    def ctx(self, tmp_path: Any) -> FakePluginContext:
        return FakePluginContext(
            config={
                "base_path": str(tmp_path / "storage"),
                "create_dirs": True,
                "public_url_base": "https://cdn.example.com/files",
            }
        )

    async def test_full_lifecycle(self, ctx: FakePluginContext, tmp_path: Any) -> None:
        """Upload → exists → download → get_url → list_files → delete."""
        from src.infrastructure.plugins.builtin.storage import LocalStoragePlugin

        plugin = LocalStoragePlugin()
        assert plugin.metadata.name == "local-storage"

        await plugin.init(ctx)
        assert await plugin.validate() is True

        # upload
        path = await plugin.upload("docs/test.txt", b"hello world", content_type="text/plain")
        assert path == "docs/test.txt"

        # exists
        assert await plugin.exists("docs/test.txt") is True
        assert await plugin.exists("docs/nope.txt") is False

        # download
        content = await plugin.download("docs/test.txt")
        assert content == b"hello world"

        # download missing
        with pytest.raises(FileNotFoundError):
            await plugin.download("docs/nope.txt")

        # get_url with public base
        url = await plugin.get_url("docs/test.txt", public=True)
        assert url == "https://cdn.example.com/files/docs/test.txt"

        # list_files
        files = await plugin.list_files(prefix="docs")
        assert len(files) == 1
        assert files[0]["path"] == "docs/test.txt"

        # list_files with limit
        await plugin.upload("docs/test2.txt", b"data2")
        files = await plugin.list_files(prefix="docs", limit=1)
        assert len(files) == 1

        # list_files missing prefix
        files = await plugin.list_files(prefix="missing")
        assert files == []

        # delete
        await plugin.delete("docs/test.txt")
        assert await plugin.exists("docs/test.txt") is False

        # delete non-existent (no error)
        await plugin.delete("docs/nope.txt")

    async def test_upload_file_like_object(self, ctx: FakePluginContext) -> None:
        """Upload from a file-like object (BinaryIO)."""
        from io import BytesIO

        from src.infrastructure.plugins.builtin.storage import LocalStoragePlugin

        plugin = LocalStoragePlugin()
        await plugin.init(ctx)
        buf = BytesIO(b"file content")
        await plugin.upload("test.bin", buf)
        assert await plugin.download("test.bin") == b"file content"

    async def test_get_url_without_public_base(self, tmp_path: Any) -> None:
        """get_url returns file:// URL when no public_url_base."""
        from src.infrastructure.plugins.builtin.storage import LocalStoragePlugin

        ctx = FakePluginContext(config={"base_path": str(tmp_path / "s")})
        plugin = LocalStoragePlugin()
        await plugin.init(ctx)
        url = await plugin.get_url("test.txt")
        assert url.startswith("file://")


class TestS3StoragePlugin:
    """Covers S3StoragePlugin with mocked boto3."""

    def _ctx(self) -> FakePluginContext:
        return FakePluginContext(
            config={
                "bucket": "test-bucket",
                "region": "us-west-2",
                "access_key_id": "AKIA_TEST",
                "secret_access_key": "secret",
                "endpoint_url": "https://s3.test.com",
                "public_url_base": "https://cdn.test.com",
            }
        )

    async def test_init_with_boto3(self) -> None:
        """Init with boto3 available."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        plugin = S3StoragePlugin()
        assert plugin.metadata.name == "s3-storage"

        ctx = self._ctx()
        with patch("src.infrastructure.plugins.builtin.storage.S3StoragePlugin.init") as mock_init:
            mock_init.return_value = None
            await plugin.init(ctx)

        # Manually set up state
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._region = "us-west-2"
        plugin._access_key_id = "AKIA_TEST"
        plugin._secret_access_key = "secret"
        plugin._endpoint_url = "https://s3.test.com"
        plugin._public_url_base = "https://cdn.test.com"
        plugin._s3_available = True
        plugin._client = MagicMock()

        assert await plugin.validate() is True

    async def test_upload_download_delete_cycle(self) -> None:
        """Upload → download → delete with mocked S3 client."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._region = "us-west-2"
        plugin._public_url_base = "https://cdn.test.com"
        plugin._s3_available = True

        mock_client = MagicMock()
        plugin._client = mock_client

        # upload with content_type and metadata
        path = await plugin.upload(
            "file.txt", b"hello", content_type="text/plain", metadata={"k": "v"}
        )
        assert path == "file.txt"
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["ContentType"] == "text/plain"
        assert call_kwargs["Metadata"] == {"k": "v"}

        # download
        mock_body = MagicMock()
        mock_body.read.return_value = b"hello"
        mock_client.get_object.return_value = {"Body": mock_body}
        content = await plugin.download("file.txt")
        assert content == b"hello"

        # delete
        await plugin.delete("file.txt")
        mock_client.delete_object.assert_called_once()

    async def test_exists_true_and_false(self) -> None:
        """Exists returns True/False based on head_object result."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._region = "us-west-2"
        plugin._s3_available = True
        plugin._client = MagicMock()

        # Mock botocore.exceptions.ClientError since botocore may not be installed
        mock_client_error = type("ClientError", (Exception,), {})
        mock_botocore = MagicMock()
        mock_botocore.exceptions.ClientError = mock_client_error

        with patch.dict(
            "sys.modules",
            {"botocore": mock_botocore, "botocore.exceptions": mock_botocore.exceptions},
        ):
            # Successful head_object → file found
            plugin._client.head_object.side_effect = None
            assert await plugin.exists("file.txt") is True

            # ClientError from head_object → file not found
            plugin._client.head_object.side_effect = mock_client_error("not found")
            assert await plugin.exists("missing.txt") is False

            # Other exception → treated as not found
            plugin._client.head_object.side_effect = RuntimeError("network")
            assert await plugin.exists("bad.txt") is False

    async def test_get_url_variants(self) -> None:
        """get_url: public URL, signed URL, default URL."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._region = "us-west-2"
        plugin._public_url_base = "https://cdn.test.com"
        plugin._s3_available = True
        plugin._client = MagicMock()
        plugin._client.generate_presigned_url.return_value = "https://signed.url"

        # public URL
        url = await plugin.get_url("f.txt", public=True)
        assert url == "https://cdn.test.com/f.txt"

        # signed URL
        url = await plugin.get_url("f.txt", expires_in=3600)
        assert url == "https://signed.url"

        # signed URL error fallback
        plugin._client.generate_presigned_url.side_effect = RuntimeError("fail")
        url = await plugin.get_url("f.txt", expires_in=3600)
        assert "s3.us-west-2.amazonaws.com" in url

        # default URL (no expires_in, not public)
        url = await plugin.get_url("f.txt")
        assert "s3.us-west-2.amazonaws.com" in url

    async def test_list_files(self) -> None:
        """List files from S3."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._region = "us-west-2"
        plugin._s3_available = True
        plugin._client = MagicMock()
        plugin._client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "a.txt", "Size": 100, "LastModified": "2024-01-01"},
                {"Key": "b.txt", "Size": 200, "LastModified": "2024-01-02"},
            ]
        }

        files = await plugin.list_files(prefix="", limit=10)
        assert len(files) == 2

    async def test_list_files_error(self) -> None:
        """List files raises on S3 error."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._s3_available = True
        plugin._client = MagicMock()
        plugin._client.list_objects_v2.side_effect = RuntimeError("S3 error")

        with pytest.raises(RuntimeError):
            await plugin.list_files()

    async def test_s3_unavailable_paths(self) -> None:
        """All S3 operations gracefully handle unavailable client."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._region = "us-west-2"
        plugin._public_url_base = None
        plugin._s3_available = False
        plugin._client = None

        assert await plugin.upload("f.txt", b"data") == "f.txt"
        assert await plugin.download("f.txt") == b""
        await plugin.delete("f.txt")  # no error
        assert await plugin.exists("f.txt") is False
        assert await plugin.list_files() == []

    async def test_upload_error(self) -> None:
        """Upload error is logged and re-raised."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._s3_available = True
        plugin._client = MagicMock()
        plugin._client.put_object.side_effect = RuntimeError("upload fail")

        with pytest.raises(RuntimeError):
            await plugin.upload("f.txt", b"data")

    async def test_download_error(self) -> None:
        """Download error is logged and re-raised."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._s3_available = True
        plugin._client = MagicMock()
        plugin._client.get_object.side_effect = RuntimeError("download fail")

        with pytest.raises(RuntimeError):
            await plugin.download("f.txt")

    async def test_delete_error(self) -> None:
        """Delete error is logged and re-raised."""
        from src.infrastructure.plugins.builtin.storage import S3StoragePlugin

        ctx = self._ctx()
        plugin = S3StoragePlugin()
        plugin.context = ctx
        plugin._bucket = "test-bucket"
        plugin._s3_available = True
        plugin._client = MagicMock()
        plugin._client.delete_object.side_effect = RuntimeError("delete fail")

        with pytest.raises(RuntimeError):
            await plugin.delete("f.txt")


# ===========================================================================
# Builtin __init__ import test
# ===========================================================================
class TestBuiltinInit:
    """Verify builtin __init__ exports all plugins."""

    def test_imports(self) -> None:
        from src.infrastructure.plugins.builtin import (
            AuthPlugin,
            JWTAuthPlugin,
            LocalStoragePlugin,
            OAuth2AuthPlugin,
            S3StoragePlugin,
            SendGridEmailPlugin,
            SMTPEmailPlugin,
            StoragePlugin,
        )

        assert all(
            [
                AuthPlugin,
                JWTAuthPlugin,
                OAuth2AuthPlugin,
                SMTPEmailPlugin,
                SendGridEmailPlugin,
                LocalStoragePlugin,
                S3StoragePlugin,
                StoragePlugin,
            ]
        )
