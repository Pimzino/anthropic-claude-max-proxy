"""
Utilities for handling thinking/reasoning blocks in messages.
"""
from typing import Dict, Any, List


def _conversation_contains_tools(messages: List[Dict[str, Any]]) -> bool:
    """Return True if any assistant has tool_use or any user has tool_result blocks."""
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if role == "assistant" and btype == "tool_use":
                    return True
                if role == "user" and btype == "tool_result":
                    return True
    return False


def _last_assistant_starts_with_thinking(messages: List[Dict[str, Any]]) -> bool:
    """Check if the last assistant message begins with a thinking/redacted_thinking block."""
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and first.get("type") in ("thinking", "redacted_thinking"):
                return True
        # Found last assistant but doesn't start with thinking
        return False
    return False


def _last_assistant_has_tool_use(messages: List[Dict[str, Any]]) -> bool:
    """Check if the last assistant message contains any tool_use blocks."""
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return True
        # Found last assistant, checked its content
        return False
    return False
