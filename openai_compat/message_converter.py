"""
Message conversion between OpenAI and Anthropic formats.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .content_converter import convert_openai_content_to_anthropic
from .tool_converter import (
    convert_openai_tool_calls_to_anthropic,
    convert_openai_function_call_to_anthropic
)

logger = logging.getLogger(__name__)


def convert_openai_messages_to_anthropic(openai_messages: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    """
    Convert OpenAI messages to Anthropic format with proper role alternation.

    This function implements the critical requirements for Anthropic's Messages API:
    1. Messages must alternate between user and assistant roles
    2. First message must be a user message
    3. Consecutive messages of the same role are merged
    4. System messages are extracted and returned separately
    5. Tool/function messages are treated as user messages
    6. Final assistant message cannot have trailing whitespace

    Returns:
        tuple: (anthropic_messages, system_message_blocks)
    """
    logger.debug(f"[MESSAGE_CONVERSION] Converting {len(openai_messages)} OpenAI messages to Anthropic format")
    logger.debug(f"[MESSAGE_CONVERSION] Raw OpenAI messages: {json.dumps(openai_messages, indent=2)}")

    # Extract system messages first (they're sent separately in Anthropic API)
    system_message_blocks: List[Dict[str, Any]] = []
    non_system_messages: List[Dict[str, Any]] = []

    for msg in openai_messages:
        if msg.get("role") == "system":
            logger.debug(f"[MESSAGE_CONVERSION] Found system message: {json.dumps(msg, indent=2)}")
            # Preserve system message structure for cache_control support
            content = msg.get("content")
            if isinstance(content, str):
                block = {"type": "text", "text": content}
                # Preserve cache_control if present
                if "cache_control" in msg:
                    block["cache_control"] = msg["cache_control"]
                system_message_blocks.append(block)
            elif isinstance(content, list):
                # Handle array content for system messages
                for item in content:
                    if item.get("type") == "text":
                        block = {"type": "text", "text": item.get("text", "")}
                        # Preserve cache_control from individual blocks
                        if "cache_control" in item:
                            block["cache_control"] = item["cache_control"]
                        system_message_blocks.append(block)
        else:
            non_system_messages.append(msg)

    logger.debug(f"[MESSAGE_CONVERSION] Extracted {len(system_message_blocks)} system blocks, {len(non_system_messages)} non-system messages")

    # Now process non-system messages with role alternation
    anthropic_messages: List[Dict[str, Any]] = []
    user_message_types = {"user", "tool", "function"}

    msg_i = 0
    while msg_i < len(non_system_messages):
        # MERGE CONSECUTIVE USER/TOOL/FUNCTION MESSAGES
        user_content: List[Dict[str, Any]] = []

        while msg_i < len(non_system_messages) and non_system_messages[msg_i].get("role") in user_message_types:
            msg = non_system_messages[msg_i]
            role = msg.get("role")
            content = msg.get("content")

            if role == "user":
                # Handle user message content
                if isinstance(content, str):
                    if content:  # Only add non-empty content
                        user_content.append({"type": "text", "text": content})
                elif isinstance(content, list):
                    # Convert content array (handles images, text, etc.)
                    converted = convert_openai_content_to_anthropic(content)
                    user_content.extend(converted)

            elif role == "tool":
                # Convert tool response to tool_result block
                tool_use_id = msg.get("tool_call_id", "")
                tool_result_content = content if isinstance(content, str) else json.dumps(content)

                logger.debug(f"[MESSAGE_CONVERSION] Converting tool message: tool_call_id={tool_use_id}, content={tool_result_content[:100]}...")

                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": tool_result_content
                }
                user_content.append(tool_result_block)

            elif role == "function":
                # Convert function response (legacy) to tool_result block
                function_name = msg.get("name", "")
                function_content = content if isinstance(content, str) else json.dumps(content)

                logger.debug(f"[MESSAGE_CONVERSION] Converting function message (legacy): name={function_name}, content={function_content[:100]}...")

                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": f"func_{function_name}",
                    "content": function_content
                }
                user_content.append(tool_result_block)

            msg_i += 1

        # Add merged user message if we have content
        if user_content:
            logger.debug(f"[MESSAGE_CONVERSION] Adding merged user message with {len(user_content)} content blocks")
            anthropic_messages.append({
                "role": "user",
                "content": user_content
            })

        # MERGE CONSECUTIVE ASSISTANT MESSAGES
        assistant_content: List[Dict[str, Any]] = []

        while msg_i < len(non_system_messages) and non_system_messages[msg_i].get("role") == "assistant":
            msg = non_system_messages[msg_i]
            content = msg.get("content")

            # Handle text content
            if isinstance(content, str):
                if content:  # Only add non-empty content
                    assistant_content.append({"type": "text", "text": content})
            elif isinstance(content, list):
                # Content is already in array format
                assistant_content.extend(content)

            # Handle tool calls in assistant messages
            if "tool_calls" in msg and msg["tool_calls"]:
                logger.debug(f"[MESSAGE_CONVERSION] Assistant message has {len(msg['tool_calls'])} tool_calls")
                tool_use_blocks = convert_openai_tool_calls_to_anthropic(msg["tool_calls"])
                assistant_content.extend(tool_use_blocks)

            # Handle function calls (legacy OpenAI format)
            if "function_call" in msg and msg["function_call"]:
                logger.debug(f"[MESSAGE_CONVERSION] Assistant message has function_call (legacy): {msg['function_call']}")
                function_blocks = convert_openai_function_call_to_anthropic(msg["function_call"])
                assistant_content.extend(function_blocks)

            msg_i += 1

        # Add merged assistant message if we have content
        if assistant_content:
            logger.debug(f"[MESSAGE_CONVERSION] Adding merged assistant message with {len(assistant_content)} content blocks")
            anthropic_messages.append({
                "role": "assistant",
                "content": assistant_content
            })

    # CRITICAL: Ensure first message is always a user message
    if anthropic_messages and anthropic_messages[0]["role"] != "user":
        # Insert placeholder user message at the beginning
        logger.debug("First message was not user role, inserting placeholder user message")
        anthropic_messages.insert(0, {
            "role": "user",
            "content": [{"type": "text", "text": "."}]
        })

    # CRITICAL: Remove trailing whitespace from final assistant message
    if anthropic_messages and anthropic_messages[-1]["role"] == "assistant":
        for content_block in anthropic_messages[-1]["content"]:
            if isinstance(content_block, dict) and content_block.get("type") == "text":
                text = content_block.get("text", "")
                if text != text.rstrip():
                    content_block["text"] = text.rstrip()
                    logger.debug("Removed trailing whitespace from final assistant message")

    logger.debug(f"[MESSAGE_CONVERSION] Final result: {len(anthropic_messages)} Anthropic messages, {len(system_message_blocks) if system_message_blocks else 0} system blocks")

    # Return system blocks as array (or None if empty) to preserve structure
    return anthropic_messages, system_message_blocks if system_message_blocks else None
