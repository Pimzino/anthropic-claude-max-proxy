"""Tests for cli/auth_handlers module"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, Mock
import httpx
import __main__

from cli.auth_handlers import (
    check_and_refresh_auth,
    login,
    refresh_token,
    logout,
    setup_long_term_token
)


@pytest.mark.unit
class TestCheckAndRefreshAuth:
    """Test suite for check_and_refresh_auth function"""

    def test_no_tokens(self):
        """Test when no tokens are available"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": False,
            "is_expired": False,
            "time_until_expiry": None
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "NO_AUTH"
        assert "No authentication tokens found" in message

    def test_valid_token(self):
        """Test when token is valid"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is True
        assert status == "VALID"
        assert "2 hours" in message

    def test_expired_token_no_refresh_token(self):
        """Test when token is expired and no refresh token available"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "time_until_expiry": "expired"
        }
        storage.get_refresh_token.return_value = None
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "NO_REFRESH"
        assert "no refresh token available" in message.lower()

    def test_successful_token_refresh(self):
        """Test successful token refresh"""
        storage = MagicMock()
        storage.get_status.side_effect = [
            {"has_tokens": True, "is_expired": True, "time_until_expiry": "expired"},
            {"has_tokens": True, "is_expired": False, "time_until_expiry": "2 hours"}
        ]
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        oauth.refresh_tokens = AsyncMock(return_value=True)

        loop = MagicMock()
        loop.run_until_complete.return_value = True

        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is True
        assert status == "REFRESHED"
        assert "2 hours" in message

    def test_failed_token_refresh(self):
        """Test failed token refresh"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "time_until_expiry": "expired"
        }
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.return_value = False

        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "REFRESH_FAILED"
        assert "invalid or expired" in message.lower()

    def test_network_error_during_refresh(self):
        """Test network error during token refresh"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "time_until_expiry": "expired"
        }
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.side_effect = httpx.NetworkError("Connection failed")

        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "NETWORK_ERROR"
        assert "Network error" in message

    def test_http_401_error_during_refresh(self):
        """Test 401 error during token refresh"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "time_until_expiry": "expired"
        }
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()

        response = MagicMock()
        response.status_code = 401
        loop.run_until_complete.side_effect = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=response)

        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "INVALID_TOKEN"

    def test_http_500_error_during_refresh(self):
        """Test 500 error during token refresh"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "time_until_expiry": "expired"
        }
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()

        response = MagicMock()
        response.status_code = 500
        loop.run_until_complete.side_effect = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=response)

        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "SERVER_ERROR"
        assert "500" in message

    def test_unknown_error_during_refresh(self):
        """Test unknown error during token refresh"""
        storage = MagicMock()
        storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": True,
            "time_until_expiry": "expired"
        }
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.side_effect = Exception("Unknown error")

        console = MagicMock()

        success, status, message = check_and_refresh_auth(storage, oauth, loop, console)

        assert success is False
        assert status == "UNKNOWN_ERROR"
        assert "Unknown error" in message


@pytest.mark.unit
class TestLogin:
    """Test suite for login function"""

    @patch('cli.auth_handlers.input')
    def test_login_success(self, mock_input):
        """Test successful login"""
        mock_input.return_value = ""

        auth_flow = MagicMock()
        auth_flow.authenticate = AsyncMock(return_value=True)

        loop = MagicMock()
        loop.run_until_complete.return_value = True

        console = MagicMock()

        login(auth_flow, loop, console, debug=False)

        loop.run_until_complete.assert_called_once()
        console.print.assert_any_call("[green]Authentication successful![/green]")

    @patch('cli.auth_handlers.input')
    def test_login_failure(self, mock_input):
        """Test failed login"""
        mock_input.return_value = ""

        auth_flow = MagicMock()
        auth_flow.authenticate = AsyncMock(return_value=False)

        loop = MagicMock()
        loop.run_until_complete.return_value = False

        console = MagicMock()

        login(auth_flow, loop, console, debug=False)

        console.print.assert_any_call("[red]Authentication failed[/red]")

    @patch('cli.auth_handlers.input')
    def test_login_exception(self, mock_input):
        """Test login with exception"""
        mock_input.return_value = ""

        auth_flow = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.side_effect = Exception("Network error")

        console = MagicMock()

        login(auth_flow, loop, console, debug=False)

        # Verify error was printed
        assert any("ERROR" in str(call) for call in console.print.call_args_list)

    @patch('cli.auth_handlers.input')
    def test_login_with_debug(self, mock_input):
        """Test login with debug logging"""
        mock_input.return_value = ""
        __main__._proxy_debug_logger = MagicMock()

        auth_flow = MagicMock()
        auth_flow.authenticate = AsyncMock(return_value=True)

        loop = MagicMock()
        loop.run_until_complete.return_value = True

        console = MagicMock()

        login(auth_flow, loop, console, debug=True)

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')


@pytest.mark.unit
class TestRefreshToken:
    """Test suite for refresh_token function"""

    @patch('cli.auth_handlers.input')
    @patch('cli.status_display.get_auth_status')
    def test_refresh_token_success(self, mock_get_auth_status, mock_input):
        """Test successful token refresh"""
        mock_input.return_value = ""
        mock_get_auth_status.return_value = ("VALID", "Expires in 2 hours")

        storage = MagicMock()
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.return_value = True

        console = MagicMock()

        refresh_token(storage, oauth, loop, console, debug=False)

        console.print.assert_any_call("[green]Token refreshed successfully![/green]")

    @patch('cli.auth_handlers.input')
    def test_refresh_token_no_refresh_token(self, mock_input):
        """Test refresh when no refresh token available"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_refresh_token.return_value = None

        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        refresh_token(storage, oauth, loop, console, debug=False)

        console.print.assert_any_call("[red]No refresh token available - please login first[/red]")

    @patch('cli.auth_handlers.input')
    def test_refresh_token_failure(self, mock_input):
        """Test failed token refresh"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.return_value = False

        console = MagicMock()

        refresh_token(storage, oauth, loop, console, debug=False)

        console.print.assert_any_call("[red]Token refresh failed - please login again[/red]")

    @patch('cli.auth_handlers.input')
    def test_refresh_token_exception(self, mock_input):
        """Test token refresh with exception"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_refresh_token.return_value = "refresh_token_123"

        oauth = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.side_effect = Exception("Network error")

        console = MagicMock()

        refresh_token(storage, oauth, loop, console, debug=False)

        # Verify error was printed
        assert any("ERROR" in str(call) for call in console.print.call_args_list)


@pytest.mark.unit
class TestLogout:
    """Test suite for logout function"""

    @patch('cli.auth_handlers.input')
    @patch('cli.auth_handlers.Confirm')
    def test_logout_confirmed(self, mock_confirm, mock_input):
        """Test logout when user confirms"""
        mock_confirm.ask.return_value = True
        mock_input.return_value = ""

        storage = MagicMock()
        console = MagicMock()

        logout(storage, console, debug=False)

        storage.clear_tokens.assert_called_once()
        console.print.assert_any_call("[green]Tokens cleared successfully[/green]")

    @patch('cli.auth_handlers.input')
    @patch('cli.auth_handlers.Confirm')
    def test_logout_cancelled(self, mock_confirm, mock_input):
        """Test logout when user cancels"""
        mock_confirm.ask.return_value = False
        mock_input.return_value = ""

        storage = MagicMock()
        console = MagicMock()

        logout(storage, console, debug=False)

        storage.clear_tokens.assert_not_called()
        console.print.assert_any_call("Logout cancelled")

    @patch('cli.auth_handlers.input')
    @patch('cli.auth_handlers.Confirm')
    def test_logout_exception(self, mock_confirm, mock_input):
        """Test logout with exception"""
        mock_confirm.ask.return_value = True
        mock_input.return_value = ""

        storage = MagicMock()
        storage.clear_tokens.side_effect = Exception("File error")
        console = MagicMock()

        logout(storage, console, debug=False)

        # Verify error was printed
        assert any("ERROR" in str(call) for call in console.print.call_args_list)

    @patch('cli.auth_handlers.input')
    @patch('cli.auth_handlers.Confirm')
    def test_logout_with_debug(self, mock_confirm, mock_input):
        """Test logout with debug logging"""
        mock_confirm.ask.return_value = True
        mock_input.return_value = ""
        __main__._proxy_debug_logger = MagicMock()

        storage = MagicMock()
        console = MagicMock()

        logout(storage, console, debug=True)

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')


@pytest.mark.unit
class TestSetupLongTermToken:
    """Test suite for setup_long_term_token function"""

    @patch('cli.auth_handlers.input')
    def test_setup_long_term_token_success(self, mock_input):
        """Test successful long-term token setup"""
        mock_input.return_value = ""

        storage = MagicMock()
        storage.get_status.return_value = {
            "expires_at": "2026-01-01T00:00:00",
            "time_until_expiry": "365 days"
        }
        storage.token_file = "/path/to/tokens.json"

        auth_flow = MagicMock()
        auth_flow.setup_long_term_token = AsyncMock(return_value="sk-ant-oat01-longterm123")

        loop = MagicMock()
        loop.run_until_complete.return_value = "sk-ant-oat01-longterm123"

        console = MagicMock()

        setup_long_term_token(storage, auth_flow, loop, console, debug=False)

        # Verify success messages
        assert any("generated and saved successfully" in str(call).lower() for call in console.print.call_args_list)

    @patch('cli.auth_handlers.input')
    def test_setup_long_term_token_failure(self, mock_input):
        """Test failed long-term token setup"""
        mock_input.return_value = ""

        storage = MagicMock()
        auth_flow = MagicMock()
        auth_flow.setup_long_term_token = AsyncMock(return_value=None)

        loop = MagicMock()
        loop.run_until_complete.return_value = None

        console = MagicMock()

        setup_long_term_token(storage, auth_flow, loop, console, debug=False)

        console.print.assert_any_call("[red]Failed to generate long-term token[/red]")

    @patch('cli.auth_handlers.input')
    def test_setup_long_term_token_exception(self, mock_input):
        """Test long-term token setup with exception"""
        mock_input.return_value = ""

        storage = MagicMock()
        auth_flow = MagicMock()
        loop = MagicMock()
        loop.run_until_complete.side_effect = Exception("Network error")

        console = MagicMock()

        setup_long_term_token(storage, auth_flow, loop, console, debug=False)

        # Verify error was printed
        assert any("ERROR" in str(call) for call in console.print.call_args_list)

    @patch('cli.auth_handlers.input')
    def test_setup_long_term_token_with_debug(self, mock_input):
        """Test long-term token setup with debug logging"""
        mock_input.return_value = ""
        __main__._proxy_debug_logger = MagicMock()

        storage = MagicMock()
        storage.get_status.return_value = {
            "expires_at": "2026-01-01T00:00:00",
            "time_until_expiry": "365 days"
        }
        storage.token_file = "/path/to/tokens.json"

        auth_flow = MagicMock()
        auth_flow.setup_long_term_token = AsyncMock(return_value="sk-ant-oat01-longterm123")

        loop = MagicMock()
        loop.run_until_complete.return_value = "sk-ant-oat01-longterm123"

        console = MagicMock()

        setup_long_term_token(storage, auth_flow, loop, console, debug=True)

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')
