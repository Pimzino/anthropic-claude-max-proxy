"""Tests for OAuth token exchange functionality"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from oauth.token_exchange import exchange_code, exchange_code_for_long_term_token, ONE_YEAR_SECONDS
from oauth.pkce import PKCEManager
from utils.storage import TokenStorage


@pytest.mark.unit
class TestExchangeCode:
    """Test suite for standard token exchange"""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, mocker):
        """Test successful token exchange"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "test_verifier_12345"
        pkce.state = "test_state_12345"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client), \
             patch.object(storage, 'save_tokens') as mock_save, \
             patch.object(pkce, 'clear_pkce') as mock_clear:

            result = await exchange_code("auth_code_123", storage, pkce)

            # Verify result
            assert result["status"] == "success"
            assert "successfully" in result["message"].lower()

            # Verify tokens were saved
            mock_save.assert_called_once_with(
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                expires_in=3600
            )

            # Verify PKCE was cleared
            mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_code_with_state(self, mocker):
        """Test token exchange with code#state format"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "test_verifier"
        pkce.state = "test_state"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600
        }

        mock_post = AsyncMock(return_value=mock_response)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = mock_post

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client), \
             patch.object(storage, 'save_tokens'), \
             patch.object(pkce, 'clear_pkce'):

            # Pass code with state
            await exchange_code("auth_code#state_value", storage, pkce)

            # Verify the POST was called with correct parameters
            call_args = mock_post.call_args
            json_data = call_args[1]['json']
            assert json_data['code'] == "auth_code"
            assert json_data['state'] == "state_value"

    @pytest.mark.asyncio
    async def test_exchange_code_loads_pkce_if_missing(self, mocker):
        """Test that PKCE is loaded from storage if not in memory"""
        storage = TokenStorage()
        pkce = PKCEManager()
        # Don't set code_verifier - should be loaded

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client), \
             patch.object(storage, 'save_tokens'), \
             patch.object(pkce, 'clear_pkce'), \
             patch.object(pkce, 'load_pkce', return_value=("loaded_verifier", "loaded_state")):

            await exchange_code("code", storage, pkce)

            # Verify PKCE was loaded
            assert pkce.code_verifier == "loaded_verifier"
            assert pkce.state == "loaded_state"

    @pytest.mark.asyncio
    async def test_exchange_code_no_pkce_raises_error(self):
        """Test that missing PKCE raises ValueError"""
        storage = TokenStorage()
        pkce = PKCEManager()
        # No PKCE verifier and load returns None

        with patch.object(pkce, 'load_pkce', return_value=(None, None)):
            with pytest.raises(ValueError, match="No PKCE verifier found"):
                await exchange_code("code", storage, pkce)

    @pytest.mark.asyncio
    async def test_exchange_code_http_error(self):
        """Test token exchange with HTTP error response"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "verifier"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid authorization code"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(Exception, match="Token exchange failed: 400"):
                await exchange_code("invalid_code", storage, pkce)

    @pytest.mark.asyncio
    async def test_exchange_code_network_error(self):
        """Test token exchange with network error"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "verifier"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.ConnectError):
                await exchange_code("code", storage, pkce)


@pytest.mark.unit
class TestExchangeCodeForLongTermToken:
    """Test suite for long-term token exchange"""

    @pytest.mark.asyncio
    async def test_exchange_long_term_token_success(self):
        """Test successful long-term token exchange"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "verifier"
        pkce.state = "state"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "sk-ant-oat01-longterm",
            "expires_in": ONE_YEAR_SECONDS
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client), \
             patch.object(storage, 'save_long_term_token') as mock_save, \
             patch.object(pkce, 'clear_pkce') as mock_clear:

            result = await exchange_code_for_long_term_token("code", storage, pkce)

            # Verify result
            assert result["status"] == "success"
            assert "Long-term" in result["message"]
            assert result["access_token"] == "sk-ant-oat01-longterm"
            assert result["expires_in"] == ONE_YEAR_SECONDS

            # Verify long-term token was saved
            mock_save.assert_called_once_with(
                access_token="sk-ant-oat01-longterm",
                expires_in=ONE_YEAR_SECONDS
            )

            # Verify PKCE was cleared
            mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_long_term_token_requests_one_year(self):
        """Test that long-term token exchange requests 1-year expiry"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "verifier"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "expires_in": ONE_YEAR_SECONDS
        }

        mock_post = AsyncMock(return_value=mock_response)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = mock_post

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client), \
             patch.object(storage, 'save_long_term_token'), \
             patch.object(pkce, 'clear_pkce'):

            await exchange_code_for_long_term_token("code", storage, pkce)

            # Verify expires_in was included in request
            call_args = mock_post.call_args
            json_data = call_args[1]['json']
            assert json_data['expires_in'] == ONE_YEAR_SECONDS

    @pytest.mark.asyncio
    async def test_exchange_long_term_token_with_state(self):
        """Test long-term token exchange with code#state format"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "verifier"
        pkce.state = "original_state"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "expires_in": ONE_YEAR_SECONDS
        }

        mock_post = AsyncMock(return_value=mock_response)
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = mock_post

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client), \
             patch.object(storage, 'save_long_term_token'), \
             patch.object(pkce, 'clear_pkce'):

            await exchange_code_for_long_term_token("code#new_state", storage, pkce)

            # Verify state from code was used
            call_args = mock_post.call_args
            json_data = call_args[1]['json']
            assert json_data['state'] == "new_state"

    @pytest.mark.asyncio
    async def test_exchange_long_term_token_no_pkce_raises_error(self):
        """Test that missing PKCE raises ValueError for long-term token"""
        storage = TokenStorage()
        pkce = PKCEManager()

        with patch.object(pkce, 'load_pkce', return_value=(None, None)):
            with pytest.raises(ValueError, match="No PKCE verifier found"):
                await exchange_code_for_long_term_token("code", storage, pkce)

    @pytest.mark.asyncio
    async def test_exchange_long_term_token_http_error(self):
        """Test long-term token exchange with HTTP error"""
        storage = TokenStorage()
        pkce = PKCEManager()
        pkce.code_verifier = "verifier"

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Insufficient permissions"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        with patch('oauth.token_exchange.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(Exception, match="Token exchange failed: 403"):
                await exchange_code_for_long_term_token("code", storage, pkce)
