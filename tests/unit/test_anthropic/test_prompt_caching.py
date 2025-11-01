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

    def test_count_in_tools(self):
        """Test counting cache controls in tools"""
        request = {
            "tools": [
                {"name": "tool1", "description": "Tool 1"},
                {"name": "tool2", "description": "Tool 2", "cache_control": {"type": "ephemeral"}}
            ]
        }
        assert count_existing_cache_controls(request) == 1

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

    def test_count_across_all_sections(self):
        """Test counting cache controls across tools, system, and messages"""
        request = {
            "tools": [
                {"name": "tool1", "description": "Tool 1", "cache_control": {"type": "ephemeral"}}
            ],
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
        assert count_existing_cache_controls(request) == 3


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

    def test_add_caching_to_tools(self):
        """Test adding cache control to last tool"""
        request = {
            "tools": [
                {"name": "tool1", "description": "Tool 1", "input_schema": {"type": "object"}},
                {"name": "tool2", "description": "Tool 2", "input_schema": {"type": "object"}},
                {"name": "tool3", "description": "Tool 3", "input_schema": {"type": "object"}}
            ],
            "messages": []
        }

        result = add_prompt_caching(request)

        # Should add cache_control to last tool only
        assert "cache_control" not in result["tools"][0]
        assert "cache_control" not in result["tools"][1]
        assert "cache_control" in result["tools"][2]
        assert result["tools"][2]["cache_control"] == {"type": "ephemeral"}

    def test_tools_cached_before_system(self):
        """Test that tools are cached before system (cache hierarchy)"""
        request = {
            "tools": [
                {"name": "tool1", "description": "Tool 1"}
            ],
            "system": [{"type": "text", "text": "System"}],
            "messages": []
        }

        result = add_prompt_caching(request)

        # Both should have cache_control
        assert "cache_control" in result["tools"][0]
        assert "cache_control" in result["system"][0]

    def test_no_tools_works_as_before(self):
        """Test that requests without tools work as before"""
        request = {
            "system": [{"type": "text", "text": "System"}],
            "messages": [{"role": "user", "content": "Hello"}]
        }

        result = add_prompt_caching(request)

        # Should add cache_control to system
        assert "cache_control" in result["system"][-1]
        # Should not have tools key or it should be unchanged
        assert "tools" not in result or result.get("tools") == request.get("tools")

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

    def test_respects_4_slot_limit_with_tools(self):
        """Test that the 4-slot limit is respected when tools are present"""
        request = {
            "tools": [
                {"name": "tool1", "description": "Tool 1"}
            ],
            "system": [
                {"type": "text", "text": "System"}
            ],
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "First"}]},
                {"role": "assistant", "content": "Response"},
                {"role": "user", "content": [{"type": "text", "text": "Second"}]},
                {"role": "assistant", "content": "Response 2"},
                {"role": "user", "content": [{"type": "text", "text": "Third"}]}
            ]
        }

        result = add_prompt_caching(request)

        # Should have exactly 4 cache controls (tool + system + 2 user messages)
        total_cache_controls = count_existing_cache_controls(result)
        assert total_cache_controls <= 4

    def test_skip_tool_caching_if_already_cached(self):
        """Test that tool caching is skipped if already present"""
        request = {
            "tools": [
                {"name": "tool1", "description": "Tool 1", "cache_control": {"type": "ephemeral"}}
            ],
            "messages": []
        }

        result = add_prompt_caching(request)

        # Should still have exactly 1 cache control (not add another)
        assert count_existing_cache_controls(result) == 1

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

    def test_empty_tools_array(self):
        """Test handling of empty tools array"""
        request = {
            "tools": [],
            "messages": [{"role": "user", "content": "Hello"}]
        }

        result = add_prompt_caching(request)

        # Should not crash, and tools should remain empty
        assert result["tools"] == []
