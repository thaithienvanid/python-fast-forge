"""Unit tests for HTTP logging middleware."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response

from src.presentation.api.middleware.logging import LoggingMiddleware


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.mark.asyncio
    async def test_logs_successful_request(self):
        """Logs request completion with status and duration."""
        app = FastAPI()
        middleware = LoggingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.__str__ = MagicMock(return_value="http://example.com/test")

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request: Request) -> Response:
            return mock_response

        with (
            patch("src.presentation.api.middleware.logging.logger") as mock_logger,
            patch("time.time", side_effect=[100.0, 100.5]),
        ):
            result = await middleware.dispatch(mock_request, mock_call_next)

        assert result == mock_response
        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["method"] == "GET"
        assert call_kwargs["url"] == "http://example.com/test"
        assert call_kwargs["status_code"] == 200
        assert "duration" in call_kwargs

    @pytest.mark.asyncio
    async def test_logs_error_response(self):
        """Logs failed requests with error status code."""
        app = FastAPI()
        middleware = LoggingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = MagicMock()
        mock_request.url.__str__ = MagicMock(return_value="http://example.com/api/users")

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500

        async def mock_call_next(request: Request) -> Response:
            return mock_response

        with patch("src.presentation.api.middleware.logging.logger") as mock_logger:
            result = await middleware.dispatch(mock_request, mock_call_next)

        assert result == mock_response
        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["status_code"] == 500

    @pytest.mark.asyncio
    async def test_measures_request_duration(self):
        """Accurately measures and logs request processing duration."""
        app = FastAPI()
        middleware = LoggingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.__str__ = MagicMock(return_value="http://example.com")

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request: Request) -> Response:
            return mock_response

        with (
            patch("src.presentation.api.middleware.logging.logger") as mock_logger,
            patch("time.time", side_effect=[1000.0, 1002.5]),
        ):
            await middleware.dispatch(mock_request, mock_call_next)

        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["duration"] == "2.500s"

    @pytest.mark.asyncio
    async def test_logs_all_http_methods(self):
        """Logs requests for different HTTP methods."""
        app = FastAPI()
        middleware = LoggingMiddleware(app)

        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            mock_request = MagicMock(spec=Request)
            mock_request.method = method
            mock_request.url = MagicMock()
            mock_request.url.__str__ = MagicMock(return_value="http://example.com")

            mock_response = MagicMock(spec=Response)
            mock_response.status_code = 200

            async def mock_call_next(request: Request, _resp=mock_response) -> Response:
                return _resp

            with patch("src.presentation.api.middleware.logging.logger") as mock_logger:
                await middleware.dispatch(mock_request, mock_call_next)

            call_kwargs = mock_logger.info.call_args[1]
            assert call_kwargs["method"] == method

    @pytest.mark.asyncio
    async def test_logs_different_status_codes(self):
        """Logs responses with various status codes."""
        app = FastAPI()
        middleware = LoggingMiddleware(app)

        for status_code in [200, 201, 400, 404, 500]:
            mock_request = MagicMock(spec=Request)
            mock_request.method = "GET"
            mock_request.url = MagicMock()
            mock_request.url.__str__ = MagicMock(return_value="http://example.com")

            mock_response = MagicMock(spec=Response)
            mock_response.status_code = status_code

            async def mock_call_next(request: Request, _resp=mock_response) -> Response:
                return _resp

            with patch("src.presentation.api.middleware.logging.logger") as mock_logger:
                await middleware.dispatch(mock_request, mock_call_next)

            call_kwargs = mock_logger.info.call_args[1]
            assert call_kwargs["status_code"] == status_code
