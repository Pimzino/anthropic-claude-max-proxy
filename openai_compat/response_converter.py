"""
Response conversion from Anthropic to OpenAI format.
"""
import time
import json
import logging
from typing import Dict, Any, Optional

from .content_converter import convert_anthropic_content_to_openai
from utils.thinking_cache import THINKING_CACHE

logger = logging.getLogger(__name__)


def map_stop_reason_to_finish_reason(stop_reason: Optional[str]) -> str:
    """Map Anthropic stop_reason to OpenAI finish_reason."""
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls"
    }
    return mapping.get(stop_reason, "stop")


def convert_anthropic_response_to_openai(anthropic_response: Dict[str, Any], model: str) -> Dict[str, Any]:
    """
    Convert Anthropic message response to OpenAI chat completion format.

    Args:
        anthropic_response: Anthropic API response
        model: Model name to include in response

    Returns:
        OpenAI chat completion response
    """
    logger.debug("[RESPONSE_CONVERSION] ===== CONVERTING ANTHROPIC RESPONSE TO OPENAI =====")
    logger.debug(f"[RESPONSE_CONVERSION] Full Anthropic response: {json.dumps(anthropic_response, indent=2)}")

    # Extract content with thinking/reasoning
    content = anthropic_response.get("content", [])
    text_content, tool_calls, reasoning_content, thinking_blocks = convert_anthropic_content_to_openai(content)

    # Cache signed thinking blocks for tool_use (non-streaming path)
    if thinking_blocks and tool_calls:
        # Find first thinking block with a signature
        signed_thinking = None
        for tb in thinking_blocks:
            sig = tb.get("signature")
            if tb.get("thinking") and isinstance(sig, str) and sig.strip():
                signed_thinking = {"type": "thinking", "thinking": tb["thinking"], "signature": sig}
                break

        if signed_thinking:
            tool_ids = [tc["id"] for tc in tool_calls if tc.get("id")]
            if tool_ids:
                logger.debug(f"[THINKING_CACHE] Storing signed thinking block for tool_use IDs: {tool_ids}")
                for tid in tool_ids:
                    THINKING_CACHE.put(tid, signed_thinking)
                    logger.debug(f"[THINKING_CACHE] Stored thinking block for tool_use ID: {tid}")

    # Build message
    message = {
        "role": "assistant",
        "content": text_content
    }

    if tool_calls:
        message["tool_calls"] = tool_calls

    # Include reasoning content and thinking blocks if present
    if reasoning_content:
        message["reasoning_content"] = reasoning_content

    if thinking_blocks:
        message["thinking_blocks"] = thinking_blocks

    # Map stop reason
    finish_reason = map_stop_reason_to_finish_reason(anthropic_response.get("stop_reason"))

    # Calculate usage with reasoning tokens
    usage_obj = anthropic_response.get("usage", {})
    prompt_tokens = usage_obj.get("input_tokens", 0)
    completion_tokens = usage_obj.get("output_tokens", 0)

    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens
    }

    # Add reasoning tokens if thinking content exists
    # Note: Anthropic's output_tokens already includes thinking tokens
    # We report them separately in completion_tokens_details for transparency
    if reasoning_content:
        # Estimate reasoning tokens (4 characters per token is a rough estimate)
        # For more accuracy, could use tiktoken: len(tiktoken.get_encoding("cl100k_base").encode(reasoning_content))
        reasoning_tokens = len(reasoning_content) // 4

        usage["completion_tokens_details"] = {
            "reasoning_tokens": reasoning_tokens
        }

        logger.debug(f"Extracted reasoning content: {len(reasoning_content)} chars, ~{reasoning_tokens} tokens")

    # Build OpenAI response
    openai_response = {
        "id": f"chatcmpl-{anthropic_response.get('id', 'unknown').replace('msg_', '')}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason
            }
        ],
        "usage": usage
    }

    logger.debug(f"[RESPONSE_CONVERSION] Final OpenAI response: {json.dumps(openai_response, indent=2)}")
    logger.debug("[RESPONSE_CONVERSION] ===== END RESPONSE CONVERSION =====")

    return openai_response
