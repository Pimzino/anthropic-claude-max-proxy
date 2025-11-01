"""Tests for OAuth token refresh functionality"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from oauth.token_refresh import refresh_tokens
from utils.storage import TokenStorage


@pytest.mark.unit
class TestRefreshTokens:
    """Test suite for token refresh"""

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self):
        """Test successful token refresh"""
        storage = TokenStorage()

        # Mock storage methods
        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'get_refresh_token', return_value="refresh_token_123"):

            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 3600
            }

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            with patch('oauth.token_refresh.httpx.AsyncClient', return_value=mock_client), \
                 patch.object(storage, 'save_tokens') as mock_save:

                result = await refresh_tokens(storage)

                # Verify success
                assert result is True

                # Verify new tokens were saved
                mock_save.assert_called_once_with(
                    access_token="new_access_token",
                    refresh_token="new_refresh_token",
                    expires_in=3600
                )

    @pytest.mark.asyncio
    async def test_refresh_tokens_long_term_token_returns_false(self):
        """Test that long-term tokens cannot be refreshed"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=True):
            result = await refresh_tokens(storage)

            # Should return False for long-term tokens
            assert result is False

    @pytest.mark.asyncio
    async def test_refresh_tokens_no_refresh_token_returns_false(self):
        """Test that missing refresh token returns False"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'get_refresh_token', return_value=None):

            result = await refresh_tokens(storage)

            # Should return False when no refresh token available
            assert result is False

    @pytest.mark.asyncio
    async def test_refresh_tokens_http_error_returns_false(self):
        """Test that HTTP error returns False"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'get_refresh_token', return_value="refresh_token"):

            # Mock HTTP error response
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid refresh token"

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            with patch('oauth.token_refresh.httpx.AsyncClient', return_value=mock_client):
                result = await refresh_tokens(storage)

                # Should return False on HTTP error
                assert result is False

    @pytest.mark.asyncio
    async def test_refresh_tokens_network_error_returns_false(self):
        """Test that network error returns False"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'get_refresh_token', return_value="refresh_token"):

            # Mock network error
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            with patch('oauth.token_refresh.httpx.AsyncClient', return_value=mock_client):
                result = await refresh_tokens(storage)

                # Should return False on network error
                assert result is False

    @pytest.mark.asyncio
    async def test_refresh_tokens_exception_returns_false(self):
        """Test that unexpected exception returns False"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'get_refresh_token', return_value="refresh_token"):

            # Mock unexpected exception
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Unexpected error")
            )

            with patch('oauth.token_refresh.httpx.AsyncClient', return_value=mock_client):
                result = await refresh_tokens(storage)

                # Should return False on exception
                assert result is False

    @pytest.mark.asyncio
    async def test_refresh_tokens_sends_correct_request(self):
        """Test that refresh request has correct parameters"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'get_refresh_token', return_value="my_refresh_token"):

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_in": 3600
            }

            mock_post = AsyncMock(return_value=mock_response)
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = mock_post

            with patch('oauth.token_refresh.httpx.AsyncClient', return_value=mock_client), \
                 patch.object(storage, 'save_tokens'):

                await refresh_tokens(storage)

                # Verify POST was called with correct parameters
                call_args = mock_post.call_args
                json_data = call_args[1]['json']
                assert json_data['grant_type'] == "refresh_token"
                assert json_data['refresh_token'] == "my_refresh_token"
                assert 'client_id' in json_data
