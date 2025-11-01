"""Tests for cli/server_handlers module"""
import pytest
from unittest.mock import patch, MagicMock, Mock
import threading
import __main__

from cli.server_handlers import start_proxy_server, stop_proxy_server


@pytest.mark.unit
class TestStartProxyServer:
    """Test suite for start_proxy_server function"""

    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.time.sleep')
    @patch('cli.server_handlers.threading.Thread')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_success(self, mock_check_auth, mock_thread, mock_sleep, mock_input):
        """Test successful server start"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=False
        )

        assert server_running is True
        assert server_thread == mock_thread_instance
        mock_thread_instance.start.assert_called_once()
        proxy_server.run.assert_not_called()  # Should be in thread

    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_already_running(self, mock_check_auth, mock_input):
        """Test starting server when already running"""
        mock_input.return_value = ""

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        server_thread = MagicMock()

        server_running, returned_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", True, server_thread, debug=False
        )

        assert server_running is True
        assert returned_thread == server_thread
        console.print.assert_any_call("[yellow]Server is already running[/yellow]")
        mock_check_auth.assert_not_called()

    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_auth_failure(self, mock_check_auth, mock_input):
        """Test server start with authentication failure"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (False, "NO_AUTH", "No authentication tokens found")

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=False
        )

        assert server_running is False
        assert server_thread is None
        assert any("ERROR" in str(call) for call in console.print.call_args_list)

    @patch('cli.server_handlers.Prompt')
    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_network_error_with_retry(self, mock_check_auth, mock_input, mock_prompt):
        """Test server start with network error and retry"""
        mock_input.return_value = ""
        mock_check_auth.side_effect = [
            (False, "NETWORK_ERROR", "Network error during token refresh"),
            (True, "VALID", "Token valid")
        ]
        mock_prompt.ask.return_value = "1"  # Retry

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        with patch('cli.server_handlers.threading.Thread'):
            with patch('cli.server_handlers.time.sleep'):
                server_running, server_thread = start_proxy_server(
                    proxy_server, storage, oauth, loop, console,
                    "127.0.0.1", False, None, debug=False, max_retries=3
                )

        # Should have retried
        assert mock_check_auth.call_count == 2

    @patch('cli.server_handlers.Prompt')
    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_network_error_cancel_retry(self, mock_check_auth, mock_input, mock_prompt):
        """Test server start with network error and cancel retry"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (False, "NETWORK_ERROR", "Network error during token refresh")
        mock_prompt.ask.return_value = "2"  # Cancel

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=False
        )

        assert server_running is False
        assert server_thread is None

    @patch('cli.server_handlers.Prompt')
    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_max_retries_reached(self, mock_check_auth, mock_input, mock_prompt):
        """Test server start with max retries reached"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (False, "NETWORK_ERROR", "Network error during token refresh")
        mock_prompt.ask.return_value = "1"  # Always retry

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=False, max_retries=2, retry_count=2
        )

        # Max retries reached, should show message
        assert any("Maximum retry attempts" in str(call) for call in console.print.call_args_list)

    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.time.sleep')
    @patch('cli.server_handlers.threading.Thread')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_with_token_refresh(self, mock_check_auth, mock_thread, mock_sleep, mock_input):
        """Test server start with automatic token refresh"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (True, "REFRESHED", "Token refreshed successfully")

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=False
        )

        assert server_running is True
        # Verify refresh message was printed
        assert any("refreshed" in str(call).lower() for call in console.print.call_args_list)

    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.time.sleep')
    @patch('cli.server_handlers.threading.Thread')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_exception(self, mock_check_auth, mock_thread, mock_sleep, mock_input):
        """Test server start with exception"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (True, "VALID", "Token valid")
        mock_thread.side_effect = Exception("Thread creation failed")

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=False
        )

        assert server_running is False
        assert any("ERROR" in str(call) for call in console.print.call_args_list)

    @patch('cli.server_handlers.input')
    @patch('cli.server_handlers.time.sleep')
    @patch('cli.server_handlers.threading.Thread')
    @patch('cli.server_handlers.check_and_refresh_auth')
    def test_start_server_with_debug(self, mock_check_auth, mock_thread, mock_sleep, mock_input):
        """Test server start with debug logging"""
        mock_input.return_value = ""
        mock_check_auth.return_value = (True, "VALID", "Token valid")
        __main__._proxy_debug_logger = MagicMock()

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        server_running, server_thread = start_proxy_server(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", False, None, debug=True
        )

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')


@pytest.mark.unit
class TestStopProxyServer:
    """Test suite for stop_proxy_server function"""

    @patch('cli.server_handlers.input')
    def test_stop_server_success(self, mock_input):
        """Test successful server stop"""
        mock_input.return_value = ""

        proxy_server = MagicMock()
        console = MagicMock()

        server_running = stop_proxy_server(proxy_server, True, console, debug=False)

        assert server_running is False
        proxy_server.stop.assert_called_once()
        console.print.assert_any_call("[green][OK][/green] Server stopped")

    @patch('cli.server_handlers.input')
    def test_stop_server_not_running(self, mock_input):
        """Test stopping server when not running"""
        mock_input.return_value = ""

        proxy_server = MagicMock()
        console = MagicMock()

        server_running = stop_proxy_server(proxy_server, False, console, debug=False)

        assert server_running is False
        proxy_server.stop.assert_not_called()
        console.print.assert_any_call("[yellow]Server is not running[/yellow]")

    @patch('cli.server_handlers.input')
    def test_stop_server_exception(self, mock_input):
        """Test server stop with exception"""
        mock_input.return_value = ""

        proxy_server = MagicMock()
        proxy_server.stop.side_effect = Exception("Stop failed")
        console = MagicMock()

        server_running = stop_proxy_server(proxy_server, True, console, debug=False)

        assert any("ERROR" in str(call) for call in console.print.call_args_list)

    @patch('cli.server_handlers.input')
    def test_stop_server_with_debug(self, mock_input):
        """Test server stop with debug logging"""
        mock_input.return_value = ""
        __main__._proxy_debug_logger = MagicMock()

        proxy_server = MagicMock()
        console = MagicMock()

        server_running = stop_proxy_server(proxy_server, True, console, debug=True)

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')
