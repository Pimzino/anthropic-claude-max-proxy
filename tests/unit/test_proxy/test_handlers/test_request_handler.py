"""Unit tests for proxy.handlers.request_handler"""
from unittest.mock import patch, MagicMock
import pytest

from proxy.handlers.request_handler import prepare_anthropic_request


@pytest.mark.unit
class TestPrepareAnthropicRequest:
    """Test suite for prepare_anthropic_request function"""

    @patch('proxy.handlers.request_handler.convert_openai_request_to_anthropic')
    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_from_openai_request(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize,
        mock_convert
    ):
        """Test preparing request from OpenAI format"""
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        # Setup mocks to pass through
        mock_convert.return_value = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }
        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            openai_request,
            request_id="test-123",
            is_native_anthropic=False
        )

        # Verify conversion was called
        mock_convert.assert_called_once_with(openai_request)
        mock_sanitize.assert_called_once()
        mock_inject_system.assert_called_once()
        mock_add_caching.assert_called_once()

        assert "model" in result
        assert "messages" in result

    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_from_native_anthropic_request(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize
    ):
        """Test preparing native Anthropic request (skip conversion)"""
        anthropic_request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            anthropic_request,
            request_id="test-123",
            is_native_anthropic=True
        )

        # Should skip conversion but still process
        mock_sanitize.assert_called_once()
        mock_inject_system.assert_called_once()
        mock_add_caching.assert_called_once()

    @patch('proxy.handlers.request_handler.convert_openai_request_to_anthropic')
    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_with_thinking_adjusts_max_tokens(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize,
        mock_convert
    ):
        """Test that max_tokens is adjusted when thinking is enabled"""
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 100,
            "reasoning_effort": "high"
        }

        # Mock converter to add thinking parameter
        mock_convert.return_value = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 100,
            "thinking": {"type": "enabled", "budget_tokens": 16000}
        }
        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            openai_request,
            request_id="test-123",
            is_native_anthropic=False
        )

        # max_tokens should be increased to thinking_budget + min_response_tokens
        # 16000 + 1024 = 17024
        assert result["max_tokens"] == 17024

    @patch('proxy.handlers.request_handler.convert_openai_request_to_anthropic')
    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_with_sufficient_max_tokens_for_thinking(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize,
        mock_convert
    ):
        """Test that max_tokens is NOT adjusted when already sufficient"""
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 20000
        }

        mock_convert.return_value = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 20000,
            "thinking": {"type": "enabled", "budget_tokens": 16000}
        }
        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            openai_request,
            request_id="test-123",
            is_native_anthropic=False
        )

        # max_tokens should remain unchanged (20000 > 17024)
        assert result["max_tokens"] == 20000

    @patch('proxy.handlers.request_handler.convert_openai_request_to_anthropic')
    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_without_thinking(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize,
        mock_convert
    ):
        """Test preparing request without thinking parameter"""
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        mock_convert.return_value = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }
        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            openai_request,
            request_id="test-123",
            is_native_anthropic=False
        )

        # max_tokens should remain unchanged
        assert result["max_tokens"] == 100

    @patch('proxy.handlers.request_handler.convert_openai_request_to_anthropic')
    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_with_custom_thinking_budget(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize,
        mock_convert
    ):
        """Test with custom thinking budget_tokens"""
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 100
        }

        mock_convert.return_value = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 100,
            "thinking": {"type": "enabled", "budget_tokens": 8000}
        }
        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            openai_request,
            request_id="test-123",
            is_native_anthropic=False
        )

        # max_tokens should be 8000 + 1024 = 9024
        assert result["max_tokens"] == 9024

    @patch('proxy.handlers.request_handler.convert_openai_request_to_anthropic')
    @patch('proxy.handlers.request_handler.sanitize_anthropic_request')
    @patch('proxy.handlers.request_handler.inject_claude_code_system_message')
    @patch('proxy.handlers.request_handler.add_prompt_caching')
    def test_prepare_preserves_other_fields(
        self,
        mock_add_caching,
        mock_inject_system,
        mock_sanitize,
        mock_convert
    ):
        """Test that other request fields are preserved"""
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "temperature": 0.7,
            "top_p": 0.9
        }

        mock_convert.return_value = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "temperature": 0.7,
            "top_p": 0.9
        }
        mock_sanitize.side_effect = lambda x: x
        mock_inject_system.side_effect = lambda x: x
        mock_add_caching.side_effect = lambda x: x

        result = prepare_anthropic_request(
            openai_request,
            request_id="test-123",
            is_native_anthropic=False
        )

        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9
