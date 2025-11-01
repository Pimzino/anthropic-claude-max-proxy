"""Tests for message conversion"""
import pytest

from openai_compat.message_converter import convert_openai_messages_to_anthropic


@pytest.mark.unit
class TestConvertOpenAIMessagesToAnthropic:
    """Test suite for message conversion"""

    def test_convert_simple_messages(self):
        """Test converting simple user/assistant messages"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]

        result, system = convert_openai_messages_to_anthropic(messages)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert system is None

    def test_extract_system_message(self):
        """Test extracting system message"""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"}
        ]

        result, system = convert_openai_messages_to_anthropic(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert system is not None
        assert len(system) == 1

    def test_merge_consecutive_user_messages(self):
        """Test merging consecutive messages of same role"""
        messages = [
            {"role": "user", "content": "First"},
            {"role": "user", "content": "Second"}
        ]

        result, system = convert_openai_messages_to_anthropic(messages)

        # Should merge into one message
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_ensure_starts_with_user(self):
        """Test that result starts with user message"""
        messages = [
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "Hi"}
        ]

        result, system = convert_openai_messages_to_anthropic(messages)

        # Should start with user
        assert result[0]["role"] == "user"

    def test_convert_tool_messages(self):
        """Test converting tool result messages"""
        messages = [
            {"role": "user", "content": "Check weather"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "function": {}}]},
            {"role": "tool", "content": "Sunny", "tool_call_id": "1"}
        ]

        result, system = convert_openai_messages_to_anthropic(messages)

        # Tool messages become user messages
        assert all(m["role"] in ["user", "assistant"] for m in result)
