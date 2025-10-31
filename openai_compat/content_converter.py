"""
Content block conversion between OpenAI and Anthropic formats.
"""
import json
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def convert_openai_content_to_anthropic(openai_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI content array to Anthropic content blocks."""
    anthropic_content = []

    for item in openai_content:
        item_type = item.get("type")

        if item_type == "text":
            anthropic_content.append({
                "type": "text",
                "text": item.get("text", "")
            })

        elif item_type == "tool_result":
            tool_result_content = item.get("content")

            if isinstance(tool_result_content, list):
                text_parts = []
                for part in tool_result_content:
                    if isinstance(part, dict):
                        part_type = part.get("type")
                        if part_type == "text":
                            text_parts.append(part.get("text", ""))
                        else:
                            text_parts.append(json.dumps(part))
                    else:
                        text_parts.append(str(part))
                result_content = "\n".join(text_parts)
            elif isinstance(tool_result_content, str):
                result_content = tool_result_content
            elif tool_result_content is None:
                result_content = ""
            else:
                result_content = json.dumps(tool_result_content)

            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": item.get("tool_use_id", ""),
                "content": result_content
            }

            if "status" in item:
                tool_result_block["status"] = item["status"]
            if "is_error" in item:
                tool_result_block["is_error"] = item["is_error"]

            anthropic_content.append(tool_result_block)

        elif item_type == "tool_use":
            # Cursor sometimes sends Anthropic-style tool_use blocks directly
            tool_use_block = {
                "type": "tool_use",
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "input": item.get("input", {})
            }

            # Preserve any additional fields if present (e.g., cache_control)
            for key, value in item.items():
                if key not in tool_use_block:
                    tool_use_block[key] = value

            anthropic_content.append(tool_use_block)

        elif item_type == "image_url":
            # Convert OpenAI image_url to Anthropic image format
            image_url = item.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else image_url

            # Check if it's a base64 data URI or a URL
            if url.startswith("data:image"):
                # Extract base64 data and media type
                match = re.match(r'data:image/(\w+);base64,(.+)', url)
                if match:
                    media_type = match.group(1)
                    base64_data = match.group(2)
                    anthropic_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": f"image/{media_type}",
                            "data": base64_data
                        }
                    })
            else:
                # Regular URL
                anthropic_content.append({
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": url
                    }
                })

    return anthropic_content


def convert_anthropic_content_to_openai(content: List[Dict[str, Any]]) -> tuple[
    Optional[str],
    Optional[List[Dict[str, Any]]],
    Optional[str],
    Optional[List[Dict[str, Any]]]
]:
    """
    Convert Anthropic content blocks to OpenAI message content, tool_calls, and reasoning.

    Returns:
        tuple: (text_content, tool_calls, reasoning_content, thinking_blocks)
    """
    logger.debug(f"[RESPONSE_CONVERSION] Converting {len(content)} Anthropic content blocks to OpenAI format")
    logger.debug(f"[RESPONSE_CONVERSION] Raw Anthropic content: {json.dumps(content, indent=2)}")

    text_parts = []
    tool_calls = []
    thinking_blocks = []
    reasoning_parts = []

    for idx, block in enumerate(content):
        block_type = block.get("type")
        logger.debug(f"[RESPONSE_CONVERSION] Processing block #{idx}: type={block_type}")

        if block_type == "text":
            text = block.get("text", "")
            logger.debug(f"[RESPONSE_CONVERSION]   - Text block: {text[:100]}...")
            text_parts.append(text)

        elif block_type == "tool_use":
            tool_id = block.get("id", "")
            tool_name = block.get("name", "")
            tool_input = block.get("input", {})

            logger.debug(f"[RESPONSE_CONVERSION]   - Tool use block:")
            logger.debug(f"[RESPONSE_CONVERSION]     - ID: {tool_id}")
            logger.debug(f"[RESPONSE_CONVERSION]     - Name: {tool_name}")
            logger.debug(f"[RESPONSE_CONVERSION]     - Input: {json.dumps(tool_input, indent=2)}")

            openai_tool_call = {
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_input)
                }
            }

            logger.debug(f"[RESPONSE_CONVERSION]     - Converted to OpenAI tool_call: {json.dumps(openai_tool_call, indent=2)}")
            tool_calls.append(openai_tool_call)

        elif block_type == "thinking" or block.get("thinking") is not None:
            # Extract thinking block (contains reasoning process)
            thinking_text = block.get("thinking", "")
            logger.debug(f"[RESPONSE_CONVERSION]   - Thinking block: {thinking_text[:100]}...")
            thinking_blocks.append(block)
            if thinking_text:
                reasoning_parts.append(thinking_text)

        elif block_type == "redacted_thinking":
            # Extract redacted thinking (no text content, but still a thinking block)
            logger.debug(f"[RESPONSE_CONVERSION]   - Redacted thinking block")
            thinking_blocks.append(block)
            # Note: redacted_thinking doesn't have text, so we don't add to reasoning_parts

    text_content = "".join(text_parts) if text_parts else None
    tool_calls_result = tool_calls if tool_calls else None
    reasoning_content = "".join(reasoning_parts) if reasoning_parts else None
    thinking_blocks_result = thinking_blocks if thinking_blocks else None

    logger.debug(f"[RESPONSE_CONVERSION] Conversion result:")
    logger.debug(f"[RESPONSE_CONVERSION]   - Text content: {text_content[:100] if text_content else 'None'}...")
    logger.debug(f"[RESPONSE_CONVERSION]   - Tool calls: {len(tool_calls_result) if tool_calls_result else 0}")
    logger.debug(f"[RESPONSE_CONVERSION]   - Reasoning content: {len(reasoning_content) if reasoning_content else 0} chars")

    return text_content, tool_calls_result, reasoning_content, thinking_blocks_result


def _ensure_thinking_prefix(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure every assistant message begins with a thinking block when reasoning is enabled."""
    updated_messages: List[Dict[str, Any]] = []

    for message in messages:
        if message.get("role") != "assistant":
            updated_messages.append(message)
            continue

        new_message = message.copy()
        content = new_message.get("content")

        if isinstance(content, str):
            blocks: List[Dict[str, Any]] = []
            blocks.append({"type": "thinking", "thinking": ""})
            if content:
                blocks.append({"type": "text", "text": content})
            new_message["content"] = blocks
        elif isinstance(content, list):
            if content and isinstance(content[0], dict) and content[0].get("type") in ("thinking", "redacted_thinking"):
                new_message["content"] = content
            else:
                new_content: List[Dict[str, Any]] = [{"type": "thinking", "thinking": ""}]
                for block in content:
                    new_content.append(block)
                new_message["content"] = new_content
        elif isinstance(content, dict):
            # Rare case: single dict, wrap it
            new_message["content"] = [{"type": "thinking", "thinking": ""}, content]
        else:
            new_message["content"] = [{"type": "thinking", "thinking": ""}]

        updated_messages.append(new_message)

    return updated_messages
