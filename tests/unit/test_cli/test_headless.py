"""Tests for cli/headless module"""
import pytest
from unittest.mock import patch, MagicMock, call, ANY
import signal
import sys
import __main__

from cli.headless import run_headless


@pytest.mark.unit
class TestRunHeadless:
    """Test suite for run_headless function"""

    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_success(self, mock_check_auth, mock_signal, mock_thread, mock_sleep):
        """Test successful headless mode execution"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Make sleep raise exception to break the while loop
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            run_headless(
                proxy_server, storage, oauth, loop, console,
                "127.0.0.1", debug=False, auto_start=True
            )
        except KeyboardInterrupt:
            pass

        # Verify server was started
        mock_thread_instance.start.assert_called_once()

    @patch('cli.headless.sys.exit')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_auth_failure(self, mock_check_auth, mock_exit):
        """Test headless mode with authentication failure"""
        mock_check_auth.return_value = (False, "NO_AUTH", "No authentication tokens found")

        proxy_server = MagicMock()
        storage = MagicMock()
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        run_headless(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", debug=False, auto_start=True
        )

        # Verify error message was printed and exit was called
        assert any("Authentication Error" in str(call) for call in console.print.call_args_list)
        mock_exit.assert_called_once_with(1)

    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_no_auto_start(self, mock_check_auth):
        """Test headless mode without auto-start"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        run_headless(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", debug=False, auto_start=False
        )

        # Verify server was not started
        proxy_server.run.assert_not_called()
        assert any("Auto-start disabled" in str(call) for call in console.print.call_args_list)

    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_with_long_term_token(self, mock_check_auth, mock_signal, mock_thread, mock_sleep):
        """Test headless mode with long-term token"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "long_term",
            "time_until_expiry": "365 days"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Make sleep raise exception to break the while loop
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            run_headless(
                proxy_server, storage, oauth, loop, console,
                "127.0.0.1", debug=False, auto_start=True
            )
        except KeyboardInterrupt:
            pass

        # Verify long-term token type was displayed
        assert any("Long-term" in str(call) for call in console.print.call_args_list)

    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_signal_handlers(self, mock_check_auth, mock_signal, mock_thread, mock_sleep):
        """Test that signal handlers are registered"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Make sleep raise exception to break the while loop
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            run_headless(
                proxy_server, storage, oauth, loop, console,
                "127.0.0.1", debug=False, auto_start=True
            )
        except KeyboardInterrupt:
            pass

        # Verify signal handlers were registered
        assert mock_signal.call_count >= 2
        mock_signal.assert_any_call(signal.SIGINT, ANY)
        mock_signal.assert_any_call(signal.SIGTERM, ANY)

    @patch('cli.headless.sys.exit')
    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_server_exception(self, mock_check_auth, mock_signal, mock_thread, mock_sleep, mock_exit):
        """Test headless mode with server startup exception"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        # Make thread creation fail
        mock_thread.side_effect = Exception("Thread creation failed")

        run_headless(
            proxy_server, storage, oauth, loop, console,
            "127.0.0.1", debug=False, auto_start=True
        )

        # Verify error was printed and exit was called
        assert any("ERROR" in str(call) for call in console.print.call_args_list)
        mock_exit.assert_called_once_with(1)

    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_with_debug(self, mock_check_auth, mock_signal, mock_thread, mock_sleep):
        """Test headless mode with debug logging"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")
        __main__._proxy_debug_logger = MagicMock()

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Make sleep raise exception to break the while loop
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            run_headless(
                proxy_server, storage, oauth, loop, console,
                "127.0.0.1", debug=True, auto_start=True
            )
        except KeyboardInterrupt:
            pass

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')

    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_displays_endpoints(self, mock_check_auth, mock_signal, mock_thread, mock_sleep):
        """Test that headless mode displays API endpoints"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Make sleep raise exception to break the while loop
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            run_headless(
                proxy_server, storage, oauth, loop, console,
                "127.0.0.1", debug=False, auto_start=True
            )
        except KeyboardInterrupt:
            pass

        # Verify endpoints were displayed
        console_output = [str(call) for call in console.print.call_args_list]
        assert any("Native Anthropic API" in s for s in console_output)
        assert any("OpenAI-Compatible API" in s for s in console_output)
        assert any("/v1/messages" in s for s in console_output)
        assert any("/v1/chat/completions" in s for s in console_output)

    @patch('cli.headless.time.sleep')
    @patch('cli.headless.threading.Thread')
    @patch('cli.headless.signal.signal')
    @patch('cli.headless.check_and_refresh_auth')
    def test_run_headless_custom_bind_address(self, mock_check_auth, mock_signal, mock_thread, mock_sleep):
        """Test headless mode with custom bind address"""
        mock_check_auth.return_value = (True, "VALID", "Token valid")

        proxy_server = MagicMock()
        storage = MagicMock()
        storage.get_status.return_value = {
            "token_type": "oauth_flow",
            "time_until_expiry": "2 hours"
        }
        oauth = MagicMock()
        loop = MagicMock()
        console = MagicMock()

        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Make sleep raise exception to break the while loop
        mock_sleep.side_effect = KeyboardInterrupt()

        try:
            run_headless(
                proxy_server, storage, oauth, loop, console,
                "0.0.0.0", debug=False, auto_start=True
            )
        except KeyboardInterrupt:
            pass

        # Verify custom bind address was used in output
        console_output = [str(call) for call in console.print.call_args_list]
        assert any("0.0.0.0" in s for s in console_output)
