"""Tests for auth_cli module"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, Mock
import __main__

from auth_cli import CLIAuthFlow


@pytest.mark.unit
class TestCLIAuthFlow:
    """Test suite for CLIAuthFlow class"""

    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    def test_initialization(self, mock_storage, mock_oauth):
        """Test CLIAuthFlow initialization"""
        flow = CLIAuthFlow()

        assert flow.oauth is not None
        assert flow.storage is not None
        mock_oauth.assert_called_once()
        mock_storage.assert_called_once()

    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    @patch('auth_cli.hasattr')
    def test_setup_debug_console_when_debug_enabled(self, mock_hasattr, mock_storage, mock_oauth):
        """Test debug console setup when debug mode is enabled"""
        # Setup mock for debug mode
        mock_hasattr.side_effect = lambda obj, attr: attr in ['_proxy_debug_enabled', '_proxy_debug_logger']
        __main__._proxy_debug_enabled = True
        __main__._proxy_debug_logger = MagicMock()

        flow = CLIAuthFlow()

        # Verify debug logger was called
        __main__._proxy_debug_logger.debug.assert_called()

        # Cleanup
        delattr(__main__, '_proxy_debug_enabled')
        delattr(__main__, '_proxy_debug_logger')

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_success(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test successful authentication flow"""
        # Setup mocks
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.return_value = "https://auth.url"
        mock_oauth_instance.exchange_code = AsyncMock(return_value={"status": "success"})
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "valid_auth_code_1234567890"

        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.get_status.return_value = {
            "expires_at": "2025-01-01T00:00:00"
        }

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        assert result is True
        mock_oauth_instance.get_authorize_url.assert_called_once()
        mock_webbrowser.open.assert_called_once_with("https://auth.url")
        mock_oauth_instance.exchange_code.assert_called_once_with("valid_auth_code_1234567890")

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_browser_open_failure(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test authentication when browser fails to open"""
        # Setup mocks
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.return_value = "https://auth.url"
        mock_oauth_instance.exchange_code = AsyncMock(return_value={"status": "success"})
        mock_webbrowser.open.return_value = False
        mock_input.return_value = "valid_auth_code_1234567890"

        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.get_status.return_value = {"expires_at": "2025-01-01T00:00:00"}

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        assert result is True
        mock_oauth_instance.exchange_code.assert_called_once()

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_invalid_code(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test authentication with invalid code"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.return_value = "https://auth.url"
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "short"  # Too short

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        assert result is False
        mock_oauth_instance.exchange_code.assert_not_called()

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_keyboard_interrupt(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test authentication cancelled by user"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.return_value = "https://auth.url"
        mock_webbrowser.open.return_value = True
        mock_input.side_effect = KeyboardInterrupt()

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        assert result is False

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.Prompt')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_exchange_failure(self, mock_storage, mock_oauth, mock_prompt, mock_input, mock_webbrowser):
        """Test authentication when code exchange fails"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.return_value = "https://auth.url"
        mock_oauth_instance.exchange_code = AsyncMock(return_value={"status": "error"})
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "valid_auth_code_1234567890"
        mock_prompt.ask.return_value = "n"

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        assert result is False

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.Prompt')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_exception_with_retry(self, mock_storage, mock_oauth, mock_prompt, mock_input, mock_webbrowser):
        """Test authentication exception handling with retry"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.side_effect = [
            Exception("Network error"),
            "https://auth.url"
        ]
        mock_oauth_instance.exchange_code = AsyncMock(return_value={"status": "success"})
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "valid_auth_code_1234567890"

        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.get_status.return_value = {"expires_at": "2025-01-01T00:00:00"}

        # First attempt fails, user retries, second attempt succeeds
        mock_prompt.ask.return_value = "y"

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        # First call raises exception, triggers retry
        mock_prompt.ask.assert_called_once()

    @pytest.mark.asyncio
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_refresh_token_success(self, mock_storage, mock_oauth):
        """Test successful token refresh"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.refresh_tokens = AsyncMock(return_value=True)

        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.get_status.return_value = {
            "expires_at": "2025-01-01T00:00:00"
        }

        flow = CLIAuthFlow()
        result = await flow.refresh_token()

        assert result is True
        mock_oauth_instance.refresh_tokens.assert_called_once()

    @pytest.mark.asyncio
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_refresh_token_failure(self, mock_storage, mock_oauth):
        """Test token refresh failure"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.refresh_tokens = AsyncMock(return_value=False)

        flow = CLIAuthFlow()
        result = await flow.refresh_token()

        assert result is False

    @pytest.mark.asyncio
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_refresh_token_exception(self, mock_storage, mock_oauth):
        """Test token refresh with exception"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.refresh_tokens = AsyncMock(side_effect=Exception("Network error"))

        flow = CLIAuthFlow()
        result = await flow.refresh_token()

        assert result is False

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_setup_long_term_token_success(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test successful long-term token setup"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url_for_long_term_token.return_value = "https://auth.url"
        mock_oauth_instance.exchange_code_for_long_term_token = AsyncMock(return_value={
            "status": "success",
            "access_token": "sk-ant-oat01-longterm123",
            "expires_in": 31536000
        })
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "valid_auth_code_1234567890"

        flow = CLIAuthFlow()
        result = await flow.setup_long_term_token()

        assert result == "sk-ant-oat01-longterm123"
        mock_oauth_instance.exchange_code_for_long_term_token.assert_called_once()

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_setup_long_term_token_failure(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test long-term token setup failure"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url_for_long_term_token.return_value = "https://auth.url"
        mock_oauth_instance.exchange_code_for_long_term_token = AsyncMock(return_value={"status": "error"})
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "valid_auth_code_1234567890"

        flow = CLIAuthFlow()
        result = await flow.setup_long_term_token()

        assert result is None

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_setup_long_term_token_keyboard_interrupt(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test long-term token setup cancelled by user"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url_for_long_term_token.return_value = "https://auth.url"
        mock_webbrowser.open.return_value = True
        mock_input.side_effect = KeyboardInterrupt()

        flow = CLIAuthFlow()
        result = await flow.setup_long_term_token()

        assert result is None

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.Prompt')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_setup_long_term_token_exception_with_retry(self, mock_storage, mock_oauth, mock_prompt, mock_input, mock_webbrowser):
        """Test long-term token setup exception with retry"""
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url_for_long_term_token.side_effect = Exception("Network error")

        mock_prompt.ask.return_value = "n"

        flow = CLIAuthFlow()
        result = await flow.setup_long_term_token()

        assert result is None
        mock_prompt.ask.assert_called_once()

    @pytest.mark.asyncio
    @patch('auth_cli.webbrowser')
    @patch('auth_cli.input')
    @patch('auth_cli.OAuthManager')
    @patch('auth_cli.TokenStorage')
    async def test_authenticate_with_debug_logging(self, mock_storage, mock_oauth, mock_input, mock_webbrowser):
        """Test authentication with debug logging enabled"""
        # Setup debug logger
        __main__._proxy_debug_logger = MagicMock()

        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.get_authorize_url.return_value = "https://auth.url"
        mock_oauth_instance.exchange_code = AsyncMock(return_value={"status": "success"})
        mock_webbrowser.open.return_value = True
        mock_input.return_value = "valid_auth_code_1234567890"

        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.get_status.return_value = {"expires_at": "2025-01-01T00:00:00"}

        flow = CLIAuthFlow()
        result = await flow.authenticate()

        assert result is True
        # Verify debug logging was called
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')
