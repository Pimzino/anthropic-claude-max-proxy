"""Tests for cli/main module"""
import pytest
import sys
from unittest.mock import patch, MagicMock, Mock
import __main__

from cli.main import main


@pytest.mark.unit
class TestMain:
    """Test suite for main function"""

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py'])
    def test_main_default_arguments(self, mock_cli_class):
        """Test main with default arguments"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        # Verify CLI was initialized with defaults
        mock_cli_class.assert_called_once()
        call_args = mock_cli_class.call_args[1]
        assert call_args['debug'] is False
        assert call_args['debug_sse'] is False
        mock_cli.run.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--debug'])
    def test_main_with_debug_flag(self, mock_cli_class):
        """Test main with debug flag"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['debug'] is True
        mock_cli.run.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--debug-sse'])
    def test_main_with_debug_sse_flag(self, mock_cli_class):
        """Test main with debug-sse flag"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['debug_sse'] is True
        mock_cli.run.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--bind', '0.0.0.0'])
    def test_main_with_bind_address(self, mock_cli_class):
        """Test main with custom bind address"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['bind_address'] == '0.0.0.0'
        mock_cli.run.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--stream-trace'])
    def test_main_with_stream_trace_enabled(self, mock_cli_class):
        """Test main with stream trace enabled"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['stream_trace_enabled'] is True
        mock_cli.run.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--no-stream-trace'])
    def test_main_with_stream_trace_disabled(self, mock_cli_class):
        """Test main with stream trace disabled"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['stream_trace_enabled'] is False
        mock_cli.run.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--headless'])
    def test_main_headless_mode(self, mock_cli_class):
        """Test main in headless mode"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        mock_cli.run_headless_mode.assert_called_once_with(auto_start=True)
        mock_cli.run.assert_not_called()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--headless', '--no-auto-start'])
    def test_main_headless_mode_no_auto_start(self, mock_cli_class):
        """Test main in headless mode without auto-start"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        mock_cli.run_headless_mode.assert_called_once_with(auto_start=False)

    @patch('cli.main.OAuthManager')
    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--token', 'sk-ant-oat01-validtoken123'])
    def test_main_with_valid_token(self, mock_cli_class, mock_oauth_manager):
        """Test main with valid token argument"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        mock_oauth_manager.validate_token_format.return_value = True

        main()

        mock_cli.storage.save_long_term_token.assert_called_once_with('sk-ant-oat01-validtoken123')
        mock_cli.run.assert_called_once()

    @patch('cli.main.OAuthManager')
    @patch('cli.main.AnthropicProxyCLI')
    @patch('cli.main.sys.exit')
    @patch('sys.argv', ['cli.py', '--token', 'invalid-token'])
    def test_main_with_invalid_token(self, mock_exit, mock_cli_class, mock_oauth_manager):
        """Test main with invalid token argument"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli
        mock_oauth_manager.validate_token_format.return_value = False

        main()

        mock_exit.assert_called_once_with(1)

    @patch('cli.main.setup_long_term_token')
    @patch('cli.main.AnthropicProxyCLI')
    @patch('cli.main.sys.exit')
    @patch('sys.argv', ['cli.py', '--setup-token'])
    def test_main_setup_token_command(self, mock_exit, mock_cli_class, mock_setup):
        """Test main with setup-token command"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        mock_setup.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py'])
    def test_main_keyboard_interrupt(self, mock_cli_class):
        """Test main with keyboard interrupt"""
        mock_cli = MagicMock()
        mock_cli.run.side_effect = KeyboardInterrupt()
        mock_cli_class.return_value = mock_cli

        # Should not raise exception
        main()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py'])
    def test_main_general_exception(self, mock_cli_class):
        """Test main with general exception"""
        mock_cli = MagicMock()
        mock_cli.run.side_effect = Exception("Something went wrong")
        mock_cli_class.return_value = mock_cli

        # Should not raise exception
        main()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('cli.main.traceback')
    @patch('sys.argv', ['cli.py', '--debug'])
    def test_main_exception_with_debug(self, mock_traceback, mock_cli_class):
        """Test main exception handling with debug enabled"""
        mock_cli = MagicMock()
        mock_cli.run.side_effect = Exception("Something went wrong")
        mock_cli_class.return_value = mock_cli

        main()

        # Verify traceback was printed in debug mode
        mock_traceback.print_exc.assert_called_once()

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '--debug', '--debug-sse'])
    def test_main_stream_trace_auto_enabled_with_debug(self, mock_cli_class):
        """Test that stream trace is auto-enabled with debug flags"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        # Stream trace should be enabled when debug is on
        assert call_args['stream_trace_enabled'] is True

    @patch('cli.main.settings')
    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py'])
    def test_main_uses_config_stream_trace_setting(self, mock_cli_class, mock_settings):
        """Test main uses config stream trace setting when no CLI arg"""
        mock_settings.STREAM_TRACE_ENABLED = True
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['stream_trace_enabled'] is True

    @patch('cli.main.OAuthManager')
    @patch('cli.main.settings')
    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py'])
    def test_main_uses_env_token(self, mock_cli_class, mock_settings, mock_oauth_manager):
        """Test main uses environment variable for token"""
        mock_settings.ANTHROPIC_OAUTH_TOKEN = 'sk-ant-oat01-envtoken123'
        mock_oauth_manager.validate_token_format.return_value = True
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        mock_cli.storage.save_long_term_token.assert_called_once_with('sk-ant-oat01-envtoken123')

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '-d'])
    def test_main_short_debug_flag(self, mock_cli_class):
        """Test main with short debug flag -d"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['debug'] is True

    @patch('cli.main.AnthropicProxyCLI')
    @patch('sys.argv', ['cli.py', '-b', '192.168.1.1'])
    def test_main_short_bind_flag(self, mock_cli_class):
        """Test main with short bind flag -b"""
        mock_cli = MagicMock()
        mock_cli_class.return_value = mock_cli

        main()

        call_args = mock_cli_class.call_args[1]
        assert call_args['bind_address'] == '192.168.1.1'
