"""Tests for request conversion"""
import pytest
from unittest.mock import patch

from openai_compat.request_converter import convert_openai_request_to_anthropic


@pytest.mark.unit
class TestConvertOpenAIRequestToAnthropic:
    """Test suite for request conversion"""

    def test_convert_basic_request(self):
        """Test converting basic request"""
        request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000
        }

        with patch('openai_compat.request_converter.convert_openai_messages_to_anthropic',
                  return_value=([{"role": "user", "content": "Hello"}], None)):
            result = convert_openai_request_to_anthropic(request)

            assert result["model"] == "claude-sonnet-4-20250514"
            assert result["max_tokens"] == 1000
            assert "messages" in result

    def test_convert_with_reasoning_effort(self):
        """Test converting request with reasoning_effort"""
        request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Solve this"}],
            "max_tokens": 4000,
            "reasoning_effort": "high"
        }

        with patch('openai_compat.request_converter.convert_openai_messages_to_anthropic',
                  return_value=([{"role": "user", "content": "Solve this"}], None)):
            result = convert_openai_request_to_anthropic(request)

            assert "thinking" in result
            assert result["thinking"]["type"] == "enabled"
            assert result["thinking"]["budget_tokens"] == 32000

    def test_convert_with_reasoning_model_variant(self):
        """Test converting request with reasoning model variant"""
        request = {
            "model": "claude-sonnet-4-20250514-reasoning-medium",
            "messages": [{"role": "user", "content": "Think"}],
            "max_tokens": 4000
        }

        with patch('openai_compat.request_converter.convert_openai_messages_to_anthropic',
                  return_value=([{"role": "user", "content": "Think"}], None)):
            result = convert_openai_request_to_anthropic(request)

            # Should extract reasoning from model name
            assert result["model"] == "claude-sonnet-4-20250514"
            assert "thinking" in result

    def test_convert_with_1m_context(self):
        """Test converting request with 1M context variant"""
        request = {
            "model": "claude-sonnet-4-20250514-1m",
            "messages": [{"role": "user", "content": "Long context"}],
            "max_tokens": 1000
        }

        with patch('openai_compat.request_converter.convert_openai_messages_to_anthropic',
                  return_value=([{"role": "user", "content": "Long context"}], None)):
            result = convert_openai_request_to_anthropic(request)

            assert result["model"] == "claude-sonnet-4-20250514"
            assert result.get("_use_1m_context") is True

    def test_convert_with_tools(self):
        """Test converting request with tools"""
        request = {
            "model": "claude-3",
            "messages": [{"role": "user", "content": "Use tool"}],
            "max_tokens": 1000,
            "tools": [{"type": "function", "function": {"name": "test"}}]
        }

        with patch('openai_compat.request_converter.convert_openai_messages_to_anthropic',
                  return_value=([{"role": "user", "content": "Use tool"}], None)), \
             patch('openai_compat.request_converter.convert_openai_tools_to_anthropic',
                  return_value=[{"name": "test"}]):
            result = convert_openai_request_to_anthropic(request)

            assert "tools" in result
