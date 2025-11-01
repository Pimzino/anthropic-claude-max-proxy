"""Tests for cli/cli_app module"""
import pytest
from unittest.mock import patch, MagicMock, Mock
import asyncio
import __main__

from cli.cli_app import AnthropicProxyCLI


@pytest.mark.unit
class TestAnthropicProxyCLI:
    """Test suite for AnthropicProxyCLI class"""

    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_initialization_default(self, mock_storage, mock_oauth, mock_auth_flow,
                                    mock_proxy, mock_event_loop, mock_debug_console):
        """Test CLI initialization with default parameters"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console

        cli = AnthropicProxyCLI()

        assert cli.debug is False
        assert cli.debug_sse is False
        assert cli.server_running is False
        assert cli.server_thread is None
        mock_storage.assert_called_once()
        mock_oauth.assert_called_once()
        mock_auth_flow.assert_called_once()
        mock_proxy.assert_called_once()

    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_initialization_with_debug(self, mock_storage, mock_oauth, mock_auth_flow,
                                       mock_proxy, mock_event_loop, mock_debug_console):
        """Test CLI initialization with debug enabled"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console

        cli = AnthropicProxyCLI(debug=True, debug_sse=True)

        assert cli.debug is True
        assert cli.debug_sse is True
        # Verify debug messages were printed
        assert mock_console.print.call_count > 0

    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_initialization_with_bind_address(self, mock_storage, mock_oauth, mock_auth_flow,
                                              mock_proxy, mock_event_loop, mock_debug_console):
        """Test CLI initialization with custom bind address"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console

        cli = AnthropicProxyCLI(bind_address="0.0.0.0")

        # Verify ProxyServer was initialized with bind_address
        mock_proxy.assert_called_once_with(
            debug=False,
            debug_sse=False,
            bind_address="0.0.0.0"
        )

    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_exit_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                            mock_event_loop, mock_debug_console, mock_clear, mock_header,
                            mock_menu, mock_prompt):
        """Test CLI run loop with exit option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.return_value = "7"  # Exit option

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify loop was closed
        mock_loop.close.assert_called_once()
        mock_console.print.assert_any_call("Goodbye!")

    @patch('cli.cli_app.start_proxy_server')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_start_server_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                     mock_event_loop, mock_debug_console, mock_clear, mock_header,
                                     mock_menu, mock_prompt, mock_start_server):
        """Test CLI run with start server option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["1", "7"]  # Start server, then exit
        mock_start_server.return_value = (True, MagicMock())

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify start_proxy_server was called
        mock_start_server.assert_called_once()

    @patch('cli.cli_app.stop_proxy_server')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_stop_server_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                    mock_event_loop, mock_debug_console, mock_clear, mock_header,
                                    mock_menu, mock_prompt, mock_stop_server):
        """Test CLI run with stop server option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["1", "7"]  # Stop server (when running), then exit
        mock_stop_server.return_value = False

        cli = AnthropicProxyCLI()
        cli.server_running = True
        cli.run()

        # Verify stop_proxy_server was called
        mock_stop_server.assert_called()

    @patch('cli.cli_app.login')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_login_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                             mock_event_loop, mock_debug_console, mock_clear, mock_header,
                             mock_menu, mock_prompt, mock_login):
        """Test CLI run with login option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["2", "7"]  # Login, then exit

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify login was called
        mock_login.assert_called_once()

    @patch('cli.cli_app.refresh_token')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_refresh_token_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                      mock_event_loop, mock_debug_console, mock_clear, mock_header,
                                      mock_menu, mock_prompt, mock_refresh):
        """Test CLI run with refresh token option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["3", "7"]  # Refresh token, then exit

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify refresh_token was called
        mock_refresh.assert_called_once()

    @patch('cli.cli_app.show_token_status')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_token_status_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                     mock_event_loop, mock_debug_console, mock_clear, mock_header,
                                     mock_menu, mock_prompt, mock_show_status):
        """Test CLI run with token status option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["4", "7"]  # Show status, then exit

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify show_token_status was called
        mock_show_status.assert_called_once()

    @patch('cli.cli_app.logout')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_logout_option(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                               mock_event_loop, mock_debug_console, mock_clear, mock_header,
                               mock_menu, mock_prompt, mock_logout):
        """Test CLI run with logout option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["5", "7"]  # Logout, then exit

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify logout was called
        mock_logout.assert_called_once()

    @patch('cli.cli_app.setup_long_term_token')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_setup_long_term_token_option(self, mock_storage, mock_oauth, mock_auth_flow,
                                              mock_proxy, mock_event_loop, mock_debug_console,
                                              mock_clear, mock_header, mock_menu, mock_prompt,
                                              mock_setup_token):
        """Test CLI run with setup long-term token option"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.side_effect = ["6", "7"]  # Setup token, then exit

        cli = AnthropicProxyCLI()
        cli.run()

        # Verify setup_long_term_token was called
        mock_setup_token.assert_called_once()

    @patch('cli.cli_app.stop_proxy_server')
    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_exit_stops_server(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                   mock_event_loop, mock_debug_console, mock_clear, mock_header,
                                   mock_menu, mock_prompt, mock_stop_server):
        """Test that exit option stops running server"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.return_value = "7"  # Exit
        mock_stop_server.return_value = False

        cli = AnthropicProxyCLI()
        cli.server_running = True
        cli.run()

        # Verify server was stopped before exit
        mock_stop_server.assert_called_once()

    @patch('cli.cli_app.run_headless')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_headless_mode(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                               mock_event_loop, mock_debug_console, mock_run_headless):
        """Test run_headless_mode method"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console

        cli = AnthropicProxyCLI()
        cli.run_headless_mode(auto_start=True)

        # Verify run_headless was called with correct parameters
        mock_run_headless.assert_called_once()
        call_args = mock_run_headless.call_args[0]
        assert call_args[7] is True  # auto_start parameter

    @patch('cli.cli_app.Prompt')
    @patch('cli.cli_app.display_menu')
    @patch('cli.cli_app.display_header')
    @patch('cli.cli_app.clear_screen')
    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_run_with_debug_logging(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                    mock_event_loop, mock_debug_console, mock_clear, mock_header,
                                    mock_menu, mock_prompt):
        """Test CLI run with debug logging"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console
        mock_prompt.ask.return_value = "7"  # Exit
        __main__._proxy_debug_logger = MagicMock()

        cli = AnthropicProxyCLI(debug=True)
        cli.run()

        # Verify debug logging
        assert __main__._proxy_debug_logger.debug.call_count > 0

        # Cleanup
        delattr(__main__, '_proxy_debug_logger')

    @patch('cli.cli_app.setup_debug_console')
    @patch('cli.cli_app.asyncio.new_event_loop')
    @patch('cli.cli_app.ProxyServer')
    @patch('cli.cli_app.CLIAuthFlow')
    @patch('cli.cli_app.OAuthManager')
    @patch('cli.cli_app.TokenStorage')
    def test_max_retries_constant(self, mock_storage, mock_oauth, mock_auth_flow, mock_proxy,
                                  mock_event_loop, mock_debug_console):
        """Test MAX_RETRIES class constant"""
        mock_loop = MagicMock()
        mock_event_loop.return_value = mock_loop
        mock_console = MagicMock()
        mock_debug_console.return_value = mock_console

        cli = AnthropicProxyCLI()

        assert cli.MAX_RETRIES == 3
