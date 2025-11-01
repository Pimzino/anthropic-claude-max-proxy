"""Tests for Anthropic to OpenAI response conversion"""
import pytest
from unittest.mock import patch

from openai_compat.response_converter import (
    map_stop_reason_to_finish_reason,
    convert_anthropic_response_to_openai
)


@pytest.mark.unit
class TestMapStopReason:
    """Test suite for stop reason mapping"""

    def test_map_end_turn(self):
        """Test mapping end_turn to stop"""
        assert map_stop_reason_to_finish_reason("end_turn") == "stop"

    def test_map_max_tokens(self):
        """Test mapping max_tokens to length"""
        assert map_stop_reason_to_finish_reason("max_tokens") == "length"

    def test_map_stop_sequence(self):
        """Test mapping stop_sequence to stop"""
        assert map_stop_reason_to_finish_reason("stop_sequence") == "stop"

    def test_map_tool_use(self):
        """Test mapping tool_use to tool_calls"""
        assert map_stop_reason_to_finish_reason("tool_use") == "tool_calls"

    def test_map_unknown_defaults_to_stop(self):
        """Test that unknown stop reasons default to stop"""
        assert map_stop_reason_to_finish_reason("unknown_reason") == "stop"
        assert map_stop_reason_to_finish_reason(None) == "stop"


@pytest.mark.unit
class TestConvertAnthropicResponseToOpenAI:
    """Test suite for response conversion"""

    def test_convert_simple_text_response(self):
        """Test converting simple text response"""
        anthropic_response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello, world!"}
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5
            }
        }

        with patch('openai_compat.response_converter.convert_anthropic_content_to_openai',
                  return_value=("Hello, world!", [], None, [])):
            result = convert_anthropic_response_to_openai(anthropic_response, "claude-3")

            assert result["object"] == "chat.completion"
            assert result["model"] == "claude-3"
            assert result["choices"][0]["message"]["role"] == "assistant"
            assert result["choices"][0]["message"]["content"] == "Hello, world!"
            assert result["choices"][0]["finish_reason"] == "stop"
            assert result["usage"]["prompt_tokens"] == 10
            assert result["usage"]["completion_tokens"] == 5
            assert result["usage"]["total_tokens"] == 15

    def test_convert_response_with_tool_calls(self):
        """Test converting response with tool calls"""
        anthropic_response = {
            "id": "msg_456",
            "content": [
                {"type": "tool_use", "id": "tool_1", "name": "get_weather"}
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 20, "output_tokens": 10}
        }

        tool_calls = [{"id": "tool_1", "type": "function", "function": {"name": "get_weather"}}]

        with patch('openai_compat.response_converter.convert_anthropic_content_to_openai',
                  return_value=("", tool_calls, None, [])):
            result = convert_anthropic_response_to_openai(anthropic_response, "claude-3")

            assert result["choices"][0]["message"]["tool_calls"] == tool_calls
            assert result["choices"][0]["finish_reason"] == "tool_calls"

    def test_convert_response_with_reasoning(self):
        """Test converting response with reasoning content"""
        anthropic_response = {
            "id": "msg_789",
            "content": [
                {"type": "thinking", "thinking": "Let me think..."},
                {"type": "text", "text": "The answer is 42"}
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 15, "output_tokens": 50}
        }

        with patch('openai_compat.response_converter.convert_anthropic_content_to_openai',
                  return_value=("The answer is 42", [], "Let me think...", [])):
            result = convert_anthropic_response_to_openai(anthropic_response, "claude-3")

            assert result["choices"][0]["message"]["reasoning_content"] == "Let me think..."
            assert "completion_tokens_details" in result["usage"]
            assert "reasoning_tokens" in result["usage"]["completion_tokens_details"]

    def test_response_id_format(self):
        """Test that response ID is properly formatted"""
        anthropic_response = {
            "id": "msg_abc123",
            "content": [],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 0, "output_tokens": 0}
        }

        with patch('openai_compat.response_converter.convert_anthropic_content_to_openai',
                  return_value=("", [], None, [])):
            result = convert_anthropic_response_to_openai(anthropic_response, "claude-3")

            assert result["id"].startswith("chatcmpl-")
            assert "abc123" in result["id"]
