"""
Request preparation and conversion logic.
"""
import logging
from typing import Dict, Any

from openai_compat import convert_openai_request_to_anthropic
from anthropic import (
    sanitize_anthropic_request,
    inject_claude_code_system_message,
    add_prompt_caching,
)

logger = logging.getLogger(__name__)


def prepare_anthropic_request(
    openai_request: Dict[str, Any],
    request_id: str,
    is_native_anthropic: bool = False
) -> Dict[str, Any]:
    """
    Prepare an Anthropic API request from OpenAI or native format.

    Args:
        openai_request: The request data (OpenAI or Anthropic format)
        request_id: Request ID for logging
        is_native_anthropic: If True, skip OpenAI conversion

    Returns:
        Prepared Anthropic request dict
    """
    # Convert from OpenAI format if needed
    if not is_native_anthropic:
        anthropic_request = convert_openai_request_to_anthropic(openai_request)
    else:
        anthropic_request = openai_request.copy()

    # Ensure max_tokens is sufficient if thinking is enabled
    thinking = anthropic_request.get("thinking")
    if thinking and thinking.get("type") == "enabled":
        thinking_budget = thinking.get("budget_tokens", 16000)
        min_response_tokens = 1024
        required_total = thinking_budget + min_response_tokens
        if anthropic_request["max_tokens"] < required_total:
            anthropic_request["max_tokens"] = required_total
            logger.debug(
                f"[{request_id}] Increased max_tokens to {required_total} "
                f"(thinking: {thinking_budget} + response: {min_response_tokens})"
            )

    # Sanitize request for Anthropic API constraints
    anthropic_request = sanitize_anthropic_request(anthropic_request)

    # Inject Claude Code system message to bypass authentication detection
    anthropic_request = inject_claude_code_system_message(anthropic_request)

    # Add cache_control to message content blocks for optimal caching
    anthropic_request = add_prompt_caching(anthropic_request)

    return anthropic_request
