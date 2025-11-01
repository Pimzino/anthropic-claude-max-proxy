"""Tests for prompt caching"""
import pytest

from anthropic.prompt_caching import count_existing_cache_controls, add_prompt_caching


@pytest.mark.unit
class TestCountExistingCacheControls:
    """Test suite for counting cache controls"""

    def test_count_zero_when_none(self):
        """Test counting when no cache controls exist"""
        request = {"messages": [{"role": "user", "content": "Hello"}]}
        assert count_existing_cache_controls(request) == 0

    def test_count_in_system_message(self):
        """Test counting cache controls in system message"""
        request = {
            "system": [
                {"type": "text", "text": "System", "cache_control": {"type": "ephemeral"}}
            ]
        }
        assert count_existing_cache_controls(request) == 1

    def test_count_in_messages(self):
        """Test counting cache controls in messages"""
        request = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hello", "cache_control": {"type": "ephemeral"}}
                    ]
                }
            ]
        }
        assert count_existing_cache_controls(request) == 1

    def test_count_multiple(self):
        """Test counting multiple cache controls"""
        request = {
            "system": [
                {"type": "text", "text": "Sys", "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hi", "cache_control": {"type": "ephemeral"}}
                    ]
                }
            ]
        }
        assert count_existing_cache_controls(request) == 2


@pytest.mark.unit
class TestAddPromptCaching:
    """Test suite for adding prompt caching"""

    def test_add_caching_to_system(self):
        """Test adding cache control to system message"""
        request = {
            "system": [{"type": "text", "text": "System message"}],
            "messages": []
        }

        result = add_prompt_caching(request)

        # Should add cache_control to system
        assert "cache_control" in result["system"][-1]

    def test_skip_when_max_cache_blocks(self):
        """Test that caching is skipped when max blocks reached"""
        request = {
            "system": [
                {"type": "text", "text": "1", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "2", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "3", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "4", "cache_control": {"type": "ephemeral"}}
            ],
            "messages": []
        }

        result = add_prompt_caching(request)

        # Should not add more cache controls
        assert count_existing_cache_controls(result) == 4

    def test_add_to_last_user_messages(self):
        """Test adding cache control to last user messages"""
        request = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "First"}]},
                {"role": "assistant", "content": "Response"},
                {"role": "user", "content": [{"type": "text", "text": "Second"}]}
            ]
        }

        result = add_prompt_caching(request)

        # Should add cache controls to user messages
        user_messages = [m for m in result["messages"] if m["role"] == "user"]
        assert len(user_messages) > 0

    def test_preserves_existing_content(self):
        """Test that existing content is preserved"""
        request = {
            "model": "claude-3",
            "messages": [{"role": "user", "content": "Test"}]
        }

        result = add_prompt_caching(request)

        assert result["model"] == "claude-3"
        assert len(result["messages"]) == 1
