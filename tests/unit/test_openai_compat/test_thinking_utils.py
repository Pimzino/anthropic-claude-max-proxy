"""Tests for thinking/reasoning utilities"""
import pytest

from openai_compat.thinking_utils import (
    _conversation_contains_tools,
    _last_assistant_starts_with_thinking,
    _last_assistant_has_tool_use
)


@pytest.mark.unit
class TestConversationContainsTools:
    """Test suite for _conversation_contains_tools"""

    def test_empty_messages(self):
        """Test with empty message list"""
        assert _conversation_contains_tools([]) is False

    def test_no_tools(self):
        """Test conversation without any tools"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        assert _conversation_contains_tools(messages) is False

    def test_assistant_with_tool_use(self):
        """Test detection of tool_use in assistant message"""
        messages = [
            {"role": "user", "content": "What's the weather?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tool_1", "name": "get_weather"}
                ]
            }
        ]
        assert _conversation_contains_tools(messages) is True

    def test_user_with_tool_result(self):
        """Test detection of tool_result in user message"""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool_1", "content": "Sunny"}
                ]
            }
        ]
        assert _conversation_contains_tools(messages) is True

    def test_mixed_content_with_tools(self):
        """Test messages with mixed content including tools"""
        messages = [
            {"role": "user", "content": "Check the weather"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check"},
                    {"type": "tool_use", "id": "tool_1", "name": "get_weather"}
                ]
            }
        ]
        assert _conversation_contains_tools(messages) is True

    def test_string_content_no_tools(self):
        """Test that string content doesn't trigger tool detection"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ]
        assert _conversation_contains_tools(messages) is False

    def test_non_dict_blocks_ignored(self):
        """Test that non-dict content blocks are ignored"""
        messages = [
            {"role": "user", "content": ["string", 123, None]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}
        ]
        assert _conversation_contains_tools(messages) is False


@pytest.mark.unit
class TestLastAssistantStartsWithThinking:
    """Test suite for _last_assistant_starts_with_thinking"""

    def test_empty_messages(self):
        """Test with empty message list"""
        assert _last_assistant_starts_with_thinking([]) is False

    def test_no_assistant_messages(self):
        """Test with no assistant messages"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        assert _last_assistant_starts_with_thinking(messages) is False

    def test_last_assistant_starts_with_thinking(self):
        """Test detection of thinking block at start"""
        messages = [
            {"role": "user", "content": "Solve this problem"},
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Let me think..."},
                    {"type": "text", "text": "The answer is..."}
                ]
            }
        ]
        assert _last_assistant_starts_with_thinking(messages) is True

    def test_last_assistant_starts_with_redacted_thinking(self):
        """Test detection of redacted_thinking block at start"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "redacted_thinking"},
                    {"type": "text", "text": "Answer"}
                ]
            }
        ]
        assert _last_assistant_starts_with_thinking(messages) is True

    def test_last_assistant_thinking_not_first(self):
        """Test when thinking block is not first"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me think"},
                    {"type": "thinking", "thinking": "Hmm..."}
                ]
            }
        ]
        assert _last_assistant_starts_with_thinking(messages) is False

    def test_last_assistant_no_thinking(self):
        """Test when last assistant has no thinking"""
        messages = [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Hi there"}
                ]
            }
        ]
        assert _last_assistant_starts_with_thinking(messages) is False

    def test_earlier_assistant_has_thinking(self):
        """Test that only last assistant is checked"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "First thought"}
                ]
            },
            {"role": "user", "content": "Continue"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "No thinking here"}
                ]
            }
        ]
        assert _last_assistant_starts_with_thinking(messages) is False

    def test_string_content(self):
        """Test with string content (not list)"""
        messages = [
            {"role": "assistant", "content": "Just text"}
        ]
        assert _last_assistant_starts_with_thinking(messages) is False


@pytest.mark.unit
class TestLastAssistantHasToolUse:
    """Test suite for _last_assistant_has_tool_use"""

    def test_empty_messages(self):
        """Test with empty message list"""
        assert _last_assistant_has_tool_use([]) is False

    def test_no_assistant_messages(self):
        """Test with no assistant messages"""
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        assert _last_assistant_has_tool_use(messages) is False

    def test_last_assistant_has_tool_use(self):
        """Test detection of tool_use in last assistant"""
        messages = [
            {"role": "user", "content": "Get weather"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tool_1", "name": "get_weather"}
                ]
            }
        ]
        assert _last_assistant_has_tool_use(messages) is True

    def test_last_assistant_tool_use_with_text(self):
        """Test tool_use mixed with text"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check"},
                    {"type": "tool_use", "id": "tool_1", "name": "get_weather"}
                ]
            }
        ]
        assert _last_assistant_has_tool_use(messages) is True

    def test_last_assistant_no_tool_use(self):
        """Test when last assistant has no tool_use"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Just text"}
                ]
            }
        ]
        assert _last_assistant_has_tool_use(messages) is False

    def test_earlier_assistant_has_tool_use(self):
        """Test that only last assistant is checked"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tool_1", "name": "func"}
                ]
            },
            {"role": "user", "content": "Result"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "No tools here"}
                ]
            }
        ]
        assert _last_assistant_has_tool_use(messages) is False

    def test_string_content(self):
        """Test with string content"""
        messages = [
            {"role": "assistant", "content": "Text only"}
        ]
        assert _last_assistant_has_tool_use(messages) is False

    def test_non_dict_blocks(self):
        """Test with non-dict content blocks"""
        messages = [
            {"role": "assistant", "content": ["string", 123]}
        ]
        assert _last_assistant_has_tool_use(messages) is False
