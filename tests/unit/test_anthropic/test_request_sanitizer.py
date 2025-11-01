"""Tests for request sanitizer"""
import pytest

from anthropic.request_sanitizer import sanitize_anthropic_request


@pytest.mark.unit
class TestSanitizeAnthropicRequest:
    """Test suite for request sanitization"""

    def test_remove_invalid_top_p(self):
        """Test removing invalid top_p values"""
        request = {
            "model": "claude-3",
            "messages": [],
            "top_p": 1.5  # Invalid - out of range
        }

        result = sanitize_anthropic_request(request)

        assert "top_p" not in result

    def test_remove_null_tools(self):
        """Test removing null tools parameter"""
        request = {
            "model": "claude-3",
            "messages": [],
            "tools": None
        }

        result = sanitize_anthropic_request(request)

        assert "tools" not in result

    def test_remove_empty_tools_list(self):
        """Test removing empty tools list"""
        request = {
            "model": "claude-3",
            "messages": [],
            "tools": []
        }

        result = sanitize_anthropic_request(request)

        assert "tools" not in result

    def test_preserve_valid_fields(self):
        """Test that valid fields are preserved"""
        request = {
            "model": "claude-3",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.7
        }

        result = sanitize_anthropic_request(request)

        assert result["model"] == "claude-3"
        assert result["max_tokens"] == 1000
        assert result["temperature"] == 0.7

    def test_adjust_temperature_for_thinking(self):
        """Test temperature adjustment when thinking is enabled"""
        request = {
            "model": "claude-3",
            "messages": [],
            "thinking": {"type": "enabled"},
            "temperature": 0.5
        }

        result = sanitize_anthropic_request(request)

        # Temperature should be adjusted to 1.0 for thinking
        assert result["temperature"] == 1.0

    def test_remove_top_k_for_thinking(self):
        """Test removing top_k when thinking is enabled"""
        request = {
            "model": "claude-3",
            "messages": [],
            "thinking": {"type": "enabled"},
            "top_k": 50
        }

        result = sanitize_anthropic_request(request)

        # top_k should be removed for thinking
        assert "top_k" not in result
