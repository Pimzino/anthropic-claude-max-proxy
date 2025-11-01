"""Tests for OAuthManager class"""
import pytest
from unittest.mock import patch, AsyncMock

from oauth import OAuthManager


@pytest.mark.unit
class TestOAuthManager:
    """Test suite for OAuthManager orchestration"""

    def test_oauth_manager_initialization(self):
        """Test that OAuthManager initializes all components"""
        manager = OAuthManager()

        # Verify components are initialized
        assert manager.storage is not None
        assert manager.pkce is not None
        assert manager.auth_builder is not None

    def test_is_long_term_token_format_static_method(self):
        """Test static method for long-term token format validation"""
        # Valid long-term token format
        assert OAuthManager.is_long_term_token_format("sk-ant-oat01-abcdefghijklmnopqrstuvwxyz") is True

        # Invalid formats
        assert OAuthManager.is_long_term_token_format("invalid") is False
        assert OAuthManager.is_long_term_token_format("") is False

    def test_validate_token_format_static_method(self):
        """Test static method for token format validation"""
        # Valid token
        assert OAuthManager.validate_token_format("sk-ant-oat01-abcdefghijklmnopqrstuvwxyz") is True

        # Invalid token
        assert OAuthManager.validate_token_format("invalid") is False

    def test_generate_pkce_delegates_to_pkce_manager(self):
        """Test that generate_pkce delegates to PKCEManager"""
        manager = OAuthManager()

        verifier, challenge = manager.generate_pkce()

        # Verify PKCE values were generated
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) >= 43
        assert len(challenge) > 0

    def test_get_authorize_url_delegates_to_auth_builder(self):
        """Test that get_authorize_url delegates to AuthorizationURLBuilder"""
        manager = OAuthManager()

        with patch.object(manager.auth_builder, 'get_authorize_url', return_value="https://test.url") as mock_method:
            url = manager.get_authorize_url()

            mock_method.assert_called_once()
            assert url == "https://test.url"

    def test_get_authorize_url_for_long_term_token_delegates(self):
        """Test that get_authorize_url_for_long_term_token delegates correctly"""
        manager = OAuthManager()

        with patch.object(manager.auth_builder, 'get_authorize_url_for_long_term_token',
                         return_value="https://test.url/longterm") as mock_method:
            url = manager.get_authorize_url_for_long_term_token()

            mock_method.assert_called_once()
            assert url == "https://test.url/longterm"

    def test_start_login_flow_delegates_to_auth_builder(self):
        """Test that start_login_flow delegates to AuthorizationURLBuilder"""
        manager = OAuthManager()

        with patch.object(manager.auth_builder, 'start_login_flow',
                         return_value="https://opened.url") as mock_method:
            url = manager.start_login_flow()

            mock_method.assert_called_once()
            assert url == "https://opened.url"

    @pytest.mark.asyncio
    async def test_exchange_code_delegates_correctly(self):
        """Test that exchange_code delegates with correct parameters"""
        manager = OAuthManager()

        with patch('oauth.exchange_code', new_callable=AsyncMock,
                  return_value={"status": "success"}) as mock_exchange:
            result = await manager.exchange_code("test_code")

            # Verify delegation with correct parameters
            mock_exchange.assert_called_once_with("test_code", manager.storage, manager.pkce)
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_exchange_code_for_long_term_token_delegates(self):
        """Test that exchange_code_for_long_term_token delegates correctly"""
        manager = OAuthManager()

        with patch('oauth.exchange_code_for_long_term_token', new_callable=AsyncMock,
                  return_value={"status": "success", "access_token": "token"}) as mock_exchange:
            result = await manager.exchange_code_for_long_term_token("test_code")

            # Verify delegation
            mock_exchange.assert_called_once_with("test_code", manager.storage, manager.pkce)
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_refresh_tokens_delegates_to_refresh_function(self):
        """Test that refresh_tokens delegates to refresh function"""
        manager = OAuthManager()

        with patch('oauth.refresh_tokens', new_callable=AsyncMock, return_value=True) as mock_refresh:
            result = await manager.refresh_tokens()

            # Verify delegation
            mock_refresh.assert_called_once_with(manager.storage)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_valid_token_async_delegates(self):
        """Test that get_valid_token_async delegates correctly"""
        manager = OAuthManager()

        with patch('oauth.get_valid_token_async', new_callable=AsyncMock,
                  return_value="valid_token") as mock_get:
            token = await manager.get_valid_token_async()

            # Verify delegation
            mock_get.assert_called_once_with(manager.storage)
            assert token == "valid_token"

    def test_get_valid_token_delegates(self):
        """Test that get_valid_token (sync) delegates correctly"""
        manager = OAuthManager()

        with patch('oauth.get_valid_token', return_value="valid_token") as mock_get:
            token = manager.get_valid_token()

            # Verify delegation
            mock_get.assert_called_once_with(manager.storage)
            assert token == "valid_token"

    @pytest.mark.asyncio
    async def test_full_oauth_flow_integration(self):
        """Test integration of full OAuth flow through manager"""
        manager = OAuthManager()

        # Step 1: Generate authorization URL
        with patch.object(manager.pkce, 'save_pkce'):
            auth_url = manager.get_authorize_url()
            assert "oauth/authorize" in auth_url

        # Step 2: Exchange code for tokens
        with patch('oauth.exchange_code', new_callable=AsyncMock,
                  return_value={"status": "success"}):
            result = await manager.exchange_code("auth_code")
            assert result["status"] == "success"

        # Step 3: Get valid token
        with patch('oauth.get_valid_token_async', new_callable=AsyncMock,
                  return_value="access_token"):
            token = await manager.get_valid_token_async()
            assert token == "access_token"

    def test_oauth_manager_uses_same_pkce_instance(self):
        """Test that auth_builder uses the same PKCE instance"""
        manager = OAuthManager()

        # Verify auth_builder uses manager's PKCE instance
        assert manager.auth_builder.pkce is manager.pkce

    def test_oauth_manager_uses_same_storage_instance(self):
        """Test that all operations use the same storage instance"""
        manager = OAuthManager()

        # All operations should use the same storage instance
        storage_id = id(manager.storage)

        # Verify storage instance is consistent
        assert id(manager.storage) == storage_id
