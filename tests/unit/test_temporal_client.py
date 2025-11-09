"""Tests for Temporal client management.

Test Organization:
- TestGetTemporalClientCreation: Client creation behavior
- TestGetTemporalClientCaching: Client caching and reuse
- TestGetTemporalClientConfiguration: Configuration settings
- TestCloseTemporalClient: Client closure behavior
- TestTemporalClientLifecycle: Full lifecycle scenarios
- TestTemporalClientErrorHandling: Error handling
"""

from unittest.mock import AsyncMock, patch

import pytest
from temporalio.client import Client

import src.infrastructure.temporal_client as temporal_module
from src.infrastructure.temporal_client import close_temporal_client, get_temporal_client


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_temporal_client():
    """Reset global Temporal client before and after each test.

    This fixture ensures test isolation by resetting the module-level
    _client variable to None before each test and restoring the original
    value after the test completes.

    Yields:
        None
    """
    # Arrange: Save original client state
    original_client = temporal_module._client

    # Reset to None for test isolation
    temporal_module._client = None

    yield

    # Cleanup: Restore original state
    temporal_module._client = original_client


# ============================================================================
# Client Creation Tests
# ============================================================================


class TestGetTemporalClientCreation:
    """Test Temporal client creation behavior."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_creates_new_client_on_first_call(self, mock_connect: AsyncMock) -> None:
        """Test get_temporal_client creates client on first call.

        Arrange: Mock Temporal Client.connect
        Act: Call get_temporal_client for first time
        Assert: New client is created and returned
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        client = await get_temporal_client()

        # Assert
        assert client is mock_client
        assert client is not None
        mock_connect.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_caches_created_client_in_module_variable(self, mock_connect: AsyncMock) -> None:
        """Test created client is cached in module-level variable.

        Arrange: Mock Temporal Client.connect
        Act: Call get_temporal_client
        Assert: Client is stored in _client module variable
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        await get_temporal_client()

        # Assert
        assert temporal_module._client is mock_client


# ============================================================================
# Client Caching Tests
# ============================================================================


class TestGetTemporalClientCaching:
    """Test Temporal client caching and reuse."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_reuses_existing_client_on_subsequent_calls(
        self, mock_connect: AsyncMock
    ) -> None:
        """Test get_temporal_client returns cached client on subsequent calls.

        Arrange: Mock client and call get_temporal_client once
        Act: Call get_temporal_client second time
        Assert: Same client instance returned, connect called only once
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client
        client1 = await get_temporal_client()

        # Act
        client2 = await get_temporal_client()

        # Assert
        assert client1 is client2  # Same object reference
        mock_connect.assert_awaited_once()  # Connect called only once

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_multiple_calls_return_same_instance(self, mock_connect: AsyncMock) -> None:
        """Test multiple calls all return same cached client.

        Arrange: Mock client
        Act: Call get_temporal_client 5 times
        Assert: All calls return same instance
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        clients = [await get_temporal_client() for _ in range(5)]

        # Assert
        assert all(c is clients[0] for c in clients)
        mock_connect.assert_awaited_once()


# ============================================================================
# Configuration Tests
# ============================================================================


class TestGetTemporalClientConfiguration:
    """Test Temporal client configuration settings."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_connects_with_correct_host(self, mock_connect: AsyncMock) -> None:
        """Test client connects with configured host.

        Arrange: Mock Client.connect
        Act: Call get_temporal_client
        Assert: Client.connect called with correct host
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        await get_temporal_client()

        # Assert
        mock_connect.assert_awaited_once()
        call_args = mock_connect.await_args
        assert "localhost:7233" in str(call_args[0])  # First positional arg is host

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_connects_with_correct_namespace(self, mock_connect: AsyncMock) -> None:
        """Test client connects with configured namespace.

        Arrange: Mock Client.connect
        Act: Call get_temporal_client
        Assert: Client.connect called with correct namespace
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        await get_temporal_client()

        # Assert
        call_kwargs = mock_connect.await_args.kwargs
        assert call_kwargs.get("namespace") == "default"

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_uses_settings_from_config(self, mock_connect: AsyncMock) -> None:
        """Test client uses settings from configuration module.

        Arrange: Mock Client.connect
        Act: Call get_temporal_client
        Assert: Settings values are used for connection
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        await get_temporal_client()

        # Assert
        mock_connect.assert_awaited_once()
        # Verify both host and namespace are passed
        call_args = mock_connect.await_args
        assert len(call_args.args) > 0  # Host as positional
        assert "namespace" in call_args.kwargs  # Namespace as keyword


# ============================================================================
# Client Closure Tests
# ============================================================================


class TestCloseTemporalClient:
    """Test Temporal client closure behavior."""

    @pytest.mark.asyncio
    async def test_close_with_no_client_is_safe(self) -> None:
        """Test close_temporal_client is safe when no client exists.

        Arrange: No client created
        Act: Call close_temporal_client
        Assert: No error raised
        """
        # Arrange
        assert temporal_module._client is None

        # Act
        await close_temporal_client()

        # Assert: No exception raised, client still None
        assert temporal_module._client is None

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_close_resets_cached_client_to_none(self, mock_connect: AsyncMock) -> None:
        """Test close_temporal_client clears the cached client.

        Arrange: Create client
        Act: Call close_temporal_client
        Assert: Global _client variable is set to None
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client
        await get_temporal_client()
        assert temporal_module._client is not None

        # Act
        await close_temporal_client()

        # Assert
        assert temporal_module._client is None

    @pytest.mark.asyncio
    async def test_close_can_be_called_multiple_times(self) -> None:
        """Test close_temporal_client can be safely called multiple times.

        Arrange: No client
        Act: Call close_temporal_client twice
        Assert: No error raised
        """
        # Arrange & Act
        await close_temporal_client()
        await close_temporal_client()

        # Assert: No exception raised
        assert temporal_module._client is None


# ============================================================================
# Client Lifecycle Tests
# ============================================================================


class TestTemporalClientLifecycle:
    """Test full Temporal client lifecycle scenarios."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_get_after_close_creates_new_client(self, mock_connect: AsyncMock) -> None:
        """Test getting client after close creates new instance.

        Arrange: Create and close client
        Act: Call get_temporal_client again
        Assert: New client instance is created
        """
        # Arrange
        mock_client1 = AsyncMock(spec=Client)
        mock_client2 = AsyncMock(spec=Client)
        mock_connect.side_effect = [mock_client1, mock_client2]

        client1 = await get_temporal_client()
        await close_temporal_client()

        # Act
        client2 = await get_temporal_client()

        # Assert
        assert client2 is mock_client2
        assert client1 is not client2
        assert mock_connect.await_count == 2

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_multiple_create_close_cycles(self, mock_connect: AsyncMock) -> None:
        """Test multiple create-close cycles work correctly.

        Arrange: Mock multiple client instances
        Act: Create and close client 3 times
        Assert: Each cycle creates new client instance
        """
        # Arrange
        mock_clients = [AsyncMock(spec=Client) for _ in range(3)]
        mock_connect.side_effect = mock_clients

        # Act & Assert
        for i in range(3):
            client = await get_temporal_client()
            assert client is mock_clients[i]
            await close_temporal_client()
            assert temporal_module._client is None

        assert mock_connect.await_count == 3


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestTemporalClientErrorHandling:
    """Test Temporal client error handling."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_propagates_connection_errors(self, mock_connect: AsyncMock) -> None:
        """Test get_temporal_client propagates connection errors.

        Arrange: Mock Client.connect to raise exception
        Act: Call get_temporal_client
        Assert: Exception is propagated
        """
        # Arrange
        mock_connect.side_effect = RuntimeError("Connection failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Connection failed"):
            await get_temporal_client()

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_does_not_cache_client_on_connection_failure(
        self, mock_connect: AsyncMock
    ) -> None:
        """Test failed connection does not cache a client.

        Arrange: Mock connection to fail
        Act: Attempt to get client (fails)
        Assert: _client remains None
        """
        # Arrange
        mock_connect.side_effect = RuntimeError("Connection failed")

        # Act
        try:
            await get_temporal_client()
        except RuntimeError:
            pass

        # Assert
        assert temporal_module._client is None

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_retry_after_connection_failure_works(self, mock_connect: AsyncMock) -> None:
        """Test getting client after failed connection works on retry.

        Arrange: Mock first connection to fail, second to succeed
        Act: Attempt get twice
        Assert: Second attempt succeeds and caches client
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.side_effect = [RuntimeError("Connection failed"), mock_client]

        # Act: First attempt fails
        with pytest.raises(RuntimeError):
            await get_temporal_client()

        # Act: Second attempt succeeds
        client = await get_temporal_client()

        # Assert
        assert client is mock_client
        assert temporal_module._client is mock_client
        assert mock_connect.await_count == 2

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_handles_timeout_errors(self, mock_connect: AsyncMock) -> None:
        """Test get_temporal_client handles timeout errors.

        Arrange: Mock connection to raise TimeoutError
        Act: Call get_temporal_client
        Assert: TimeoutError is propagated
        """
        # Arrange
        mock_connect.side_effect = TimeoutError("Connection timeout")

        # Act & Assert
        with pytest.raises(TimeoutError, match="Connection timeout"):
            await get_temporal_client()

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_handles_generic_exceptions(self, mock_connect: AsyncMock) -> None:
        """Test get_temporal_client handles generic exceptions.

        Arrange: Mock connection to raise generic Exception
        Act: Call get_temporal_client
        Assert: Exception is propagated
        """
        # Arrange
        mock_connect.side_effect = Exception("Generic error")

        # Act & Assert
        with pytest.raises(Exception, match="Generic error"):
            await get_temporal_client()


# ============================================================================
# Global State Management Tests
# ============================================================================


class TestTemporalClientGlobalState:
    """Test global state management of Temporal client."""

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_module_level_client_starts_as_none(self, mock_connect: AsyncMock) -> None:
        """Test module-level _client variable starts as None.

        Arrange: Reset fixture ensures _client is None
        Act: Check _client value
        Assert: Value is None
        """
        # Arrange & Act & Assert
        assert temporal_module._client is None

    @pytest.mark.asyncio
    @patch("src.infrastructure.temporal_client.Client.connect")
    async def test_client_is_stored_globally(self, mock_connect: AsyncMock) -> None:
        """Test created client is accessible via module variable.

        Arrange: Mock client
        Act: Create client via get_temporal_client
        Assert: Client is accessible via module._client
        """
        # Arrange
        mock_client = AsyncMock(spec=Client)
        mock_connect.return_value = mock_client

        # Act
        client = await get_temporal_client()

        # Assert
        assert temporal_module._client is client
        assert temporal_module._client is not None
