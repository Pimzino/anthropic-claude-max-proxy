"""Tests for system message injection"""
import pytest
from unittest.mock import patch

from anthropic.system_message import inject_claude_code_system_message


@pytest.mark.unit
class TestInjectClaudeCodeSystemMessage:
    """Test suite for system message injection"""

    def test_inject_when_no_system_message(self):
        """Test injection when no system message exists"""
        request = {"messages": [{"role": "user", "content": "Hello"}]}

        with patch('anthropic.system_message.CLAUDE_CODE_SPOOF_MESSAGE', 'SPOOF'):
            result = inject_claude_code_system_message(request)

            assert "system" in result
            assert isinstance(result["system"], list)
            assert len(result["system"]) == 1
            assert result["system"][0]["text"] == "SPOOF"

    def test_inject_with_existing_string_system(self):
        """Test injection with existing string system message"""
        request = {"system": "You are helpful"}

        with patch('anthropic.system_message.CLAUDE_CODE_SPOOF_MESSAGE', 'SPOOF'):
            result = inject_claude_code_system_message(request)

            assert isinstance(result["system"], list)
            assert len(result["system"]) == 2
            assert result["system"][0]["text"] == "SPOOF"
            assert result["system"][1]["text"] == "You are helpful"

    def test_inject_with_existing_list_system(self):
        """Test injection with existing list system message"""
        request = {"system": [{"type": "text", "text": "Existing"}]}

        with patch('anthropic.system_message.CLAUDE_CODE_SPOOF_MESSAGE', 'SPOOF'):
            result = inject_claude_code_system_message(request)

            assert len(result["system"]) == 2
            assert result["system"][0]["text"] == "SPOOF"
            assert result["system"][1]["text"] == "Existing"

    def test_no_duplicate_injection(self):
        """Test that spoof message is not injected twice"""
        with patch('anthropic.system_message.CLAUDE_CODE_SPOOF_MESSAGE', 'SPOOF'):
            request = {"system": [{"type": "text", "text": "SPOOF"}]}

            result = inject_claude_code_system_message(request)

            # Should not add duplicate
            assert len(result["system"]) == 1
            assert result["system"][0]["text"] == "SPOOF"

    def test_preserves_other_fields(self):
        """Test that other request fields are preserved"""
        request = {
            "model": "claude-3",
            "max_tokens": 1000,
            "messages": []
        }

        with patch('anthropic.system_message.CLAUDE_CODE_SPOOF_MESSAGE', 'SPOOF'):
            result = inject_claude_code_system_message(request)

            assert result["model"] == "claude-3"
            assert result["max_tokens"] == 1000
            assert result["messages"] == []
