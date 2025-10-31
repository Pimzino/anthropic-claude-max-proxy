"""
Request conversion from OpenAI to Anthropic format.
"""
import json
import logging
from typing import Dict, Any, Optional

from models import REASONING_BUDGET_MAP, resolve_model_metadata
from utils.thinking_cache import THINKING_CACHE
from .message_converter import convert_openai_messages_to_anthropic
from .tool_converter import convert_openai_tools_to_anthropic, convert_openai_functions_to_anthropic
from .thinking_utils import _last_assistant_has_tool_use, _last_assistant_starts_with_thinking

logger = logging.getLogger(__name__)


def convert_openai_request_to_anthropic(openai_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert full OpenAI chat completion request to Anthropic messages request.

    Args:
        openai_request: OpenAI chat completion request

    Returns:
        Anthropic messages request
    """
    logger.debug("[REQUEST_CONVERSION] ===== STARTING OPENAI TO ANTHROPIC CONVERSION =====")
    logger.debug(f"[REQUEST_CONVERSION] Full OpenAI request: {json.dumps(openai_request, indent=2)}")

    # Convert messages
    messages, system_blocks = convert_openai_messages_to_anthropic(openai_request.get("messages", []))

    logger.debug(f"[REQUEST_CONVERSION] Converted messages ({len(messages)} messages): {json.dumps(messages, indent=2)}")
    logger.debug(f"[REQUEST_CONVERSION] System blocks: {json.dumps(system_blocks, indent=2) if system_blocks else 'None'}")

    # Parse model name for reasoning and 1M context variants
    model_name = openai_request.get("model", "claude-sonnet-4-5-20250929")
    base_model, model_reasoning_level, use_1m_context = resolve_model_metadata(model_name)

    logger.debug(f"[REQUEST_CONVERSION] Model resolution: {model_name} -> base={base_model}, reasoning={model_reasoning_level}, 1m_context={use_1m_context}")

    # Build Anthropic request (use base model name, without variant suffixes)
    anthropic_request = {
        "model": base_model,
        "messages": messages,
        "max_tokens": openai_request.get("max_tokens", 4096),
        "stream": openai_request.get("stream", False)
    }

    # Store 1M context flag for beta header handling (custom metadata field)
    if use_1m_context:
        anthropic_request["_use_1m_context"] = True

    # Add system message blocks if present (as array, not string)
    # NOTE: The Claude Code spoof message will be injected by anthropic.py's inject_claude_code_system_message()
    # which handles both string and array formats, so we preserve the array format here
    if system_blocks:
        anthropic_request["system"] = system_blocks

    # Add optional parameters
    if "temperature" in openai_request:
        anthropic_request["temperature"] = openai_request["temperature"]

    if "top_p" in openai_request:
        anthropic_request["top_p"] = openai_request["top_p"]

    if "stop" in openai_request:
        # OpenAI supports stop sequences
        stop = openai_request["stop"]
        if isinstance(stop, str):
            anthropic_request["stop_sequences"] = [stop]
        elif isinstance(stop, list):
            anthropic_request["stop_sequences"] = stop

    # Convert tools
    if "tools" in openai_request and openai_request["tools"]:
        logger.debug(f"[REQUEST_CONVERSION] Found 'tools' field in OpenAI request with {len(openai_request['tools'])} tools")
        tools = convert_openai_tools_to_anthropic(openai_request["tools"])
        if tools:
            anthropic_request["tools"] = tools
            logger.debug(f"[REQUEST_CONVERSION] Added {len(tools)} tools to Anthropic request")
        else:
            logger.debug("[REQUEST_CONVERSION] No tools after conversion (empty result)")

    # Convert functions (legacy)
    if "functions" in openai_request and openai_request["functions"]:
        logger.debug(f"[REQUEST_CONVERSION] Found 'functions' field (legacy) in OpenAI request with {len(openai_request['functions'])} functions")
        tools = convert_openai_functions_to_anthropic(openai_request["functions"])
        if tools:
            anthropic_request["tools"] = tools
            logger.debug(f"[REQUEST_CONVERSION] Added {len(tools)} tools (from functions) to Anthropic request")

    # Handle tool_choice
    if "tool_choice" in openai_request:
        tool_choice = openai_request["tool_choice"]
        logger.debug(f"[REQUEST_CONVERSION] Processing tool_choice: {json.dumps(tool_choice, indent=2)}")

        if tool_choice == "none":
            # Don't include tools
            logger.debug("[REQUEST_CONVERSION] tool_choice='none' - removing tools from request")
            anthropic_request.pop("tools", None)
        elif tool_choice == "auto":
            # Default Anthropic behavior
            logger.debug("[REQUEST_CONVERSION] tool_choice='auto' - using default Anthropic behavior")
            pass
        elif isinstance(tool_choice, dict):
            # Handle dict format (Cursor sends {'type': 'auto'})
            choice_type = tool_choice.get("type")
            logger.debug(f"[REQUEST_CONVERSION] tool_choice is dict with type='{choice_type}'")

            if choice_type == "auto" or choice_type is None:
                # Auto mode - default Anthropic behavior
                logger.debug("[REQUEST_CONVERSION] tool_choice type is 'auto' or None - using default behavior")
                pass
            elif choice_type == "function":
                # Specific tool
                function_name = tool_choice.get("function", {}).get("name")
                logger.debug(f"[REQUEST_CONVERSION] tool_choice type is 'function' with name='{function_name}'")

                if function_name:
                    anthropic_request["tool_choice"] = {
                        "type": "tool",
                        "name": function_name
                    }
                    logger.debug(f"[REQUEST_CONVERSION] Set Anthropic tool_choice to force tool: {function_name}")

    # Handle function_call (legacy)
    if "function_call" in openai_request:
        function_call = openai_request["function_call"]
        if function_call == "none":
            anthropic_request.pop("tools", None)
        elif function_call == "auto":
            pass
        elif isinstance(function_call, dict):
            function_name = function_call.get("name")
            if function_name:
                anthropic_request["tool_choice"] = {
                    "type": "tool",
                    "name": function_name
                }

    # Before enabling thinking, try to prepend a previously signed thinking
    # block to the last assistant message when tools are present.
    def _maybe_prepend_signed_thinking_for_tools() -> None:
        msgs = anthropic_request.get("messages") or []
        if not msgs:
            return
        # find last assistant message
        last_idx = None
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("role") == "assistant":
                last_idx = i
                break
        if last_idx is None:
            logger.debug("[THINKING_CACHE] No assistant message found in history")
            return
        last_msg = msgs[last_idx]
        content = last_msg.get("content")
        if not isinstance(content, list) or not content:
            logger.debug("[THINKING_CACHE] Last assistant message has no content list")
            return
        first = content[0]
        if isinstance(first, dict) and first.get("type") in ("thinking", "redacted_thinking"):
            logger.debug("[THINKING_CACHE] Last assistant already starts with thinking block")
            return
        # collect tool_use ids
        tool_ids = [b.get("id") for b in content if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id")]
        if not tool_ids:
            logger.debug("[THINKING_CACHE] Last assistant message has no tool_use blocks")
            return
        logger.debug(f"[THINKING_CACHE] Looking for cached thinking for tool_use IDs: {tool_ids}")
        cached = None
        for tid in tool_ids:
            block = THINKING_CACHE.get(tid)
            logger.debug(f"[THINKING_CACHE] Cache lookup for {tid}: {'FOUND' if block else 'NOT FOUND'}")
            if block and isinstance(block.get("signature"), str) and block.get("signature").strip():
                cached = block
                break
        if cached:
            logger.debug(f"[THINKING_CACHE] Reattaching signed thinking block for tool_use id(s) {tool_ids}")
            last_msg["content"] = [cached] + content
            msgs[last_idx] = last_msg
            anthropic_request["messages"] = msgs
        else:
            logger.debug(f"[THINKING_CACHE] No valid cached thinking block found for tool_use id(s) {tool_ids}")

    _maybe_prepend_signed_thinking_for_tools()

    # Handle reasoning/thinking
    # Priority: reasoning_effort parameter > model variant > no thinking
    reasoning_level = None

    # Check for explicit reasoning_effort parameter (takes precedence)
    if "reasoning_effort" in openai_request and openai_request["reasoning_effort"]:
        reasoning_level = openai_request["reasoning_effort"]
        logger.debug(f"Using reasoning_effort parameter: {reasoning_level}")
    # Check for model-based reasoning variant
    elif model_reasoning_level:
        reasoning_level = model_reasoning_level
        logger.debug(f"Using model-based reasoning: {reasoning_level} (from {model_name})")

    # Enable thinking if reasoning level is specified
    if reasoning_level and reasoning_level in REASONING_BUDGET_MAP:
        thinking_budget = REASONING_BUDGET_MAP[reasoning_level]

        # Ensure max_tokens is sufficient for reasoning models
        # This must happen BEFORE we determine if thinking can be enabled,
        # because reasoning models need higher token limits even when thinking is disabled
        # Reserve at least 1024 tokens for the actual response content
        min_response_tokens = 1024
        required_total = thinking_budget + min_response_tokens

        if anthropic_request["max_tokens"] < required_total:
            logger.info(
                f"Reasoning model requested: overriding max_tokens from {anthropic_request['max_tokens']} to {required_total} "
                f"(thinking budget: {thinking_budget} + min response: {min_response_tokens}) for reasoning level '{reasoning_level}'"
            )
            anthropic_request["max_tokens"] = required_total

        # Check if we can safely enable thinking
        # Anthropic requires: if there's a last assistant message with tool_use, it must start with thinking
        # So we can only enable thinking if:
        # 1. There's no last assistant message, OR
        # 2. The last assistant message doesn't have tool_use, OR
        # 3. The last assistant message starts with thinking (we just prepended it from cache)
        can_enable_thinking = True
        last_assistant_has_tools = _last_assistant_has_tool_use(anthropic_request["messages"]) if anthropic_request.get("messages") else False
        last_assistant_has_thinking = _last_assistant_starts_with_thinking(anthropic_request["messages"]) if anthropic_request.get("messages") else False

        if last_assistant_has_tools and not last_assistant_has_thinking:
            # Do NOT remove messages; that breaks tool_result -> tool_use linking
            # Instead, disable thinking for this turn to satisfy Anthropic requirements
            logger.warning(
                "Thinking requested, but last assistant has tool_use and no thinking; "
                "disabling thinking for this turn to preserve tool linkage."
            )
        else:
            anthropic_request["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget
            }
            logger.debug(f"Enabled thinking with budget {thinking_budget} tokens (reasoning_effort: {reasoning_level})")

        if anthropic_request.get("thinking"):
            logger.debug(
                f"Enabled thinking with budget {thinking_budget} tokens (reasoning_effort: {reasoning_level}), "
                f"max_tokens: {anthropic_request['max_tokens']}"
            )

    logger.debug("[REQUEST_CONVERSION] ===== FINAL ANTHROPIC REQUEST =====")
    logger.debug(f"[REQUEST_CONVERSION] {json.dumps(anthropic_request, indent=2)}")
    logger.debug("[REQUEST_CONVERSION] ===== END CONVERSION =====")

    return anthropic_request
