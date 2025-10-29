"""
OpenAI to Anthropic API compatibility layer.
Converts between OpenAI chat completion format and Anthropic messages format.
"""
import time
import json
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, AsyncIterator, Tuple, TYPE_CHECKING
import logging

from constants import REASONING_BUDGET_MAP, resolve_model_metadata
from thinking_cache import THINKING_CACHE

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stream_debug import StreamTracer


@dataclass
class _SSEEvent:
    """Represents a parsed Server-Sent Events frame."""
    event: Optional[str]
    data: str


class _SSEParser:
    """Incremental parser for text/event-stream payloads."""

    def __init__(self) -> None:
        self._buffer = ""
        self._current_event: Optional[str] = None
        self._current_data: List[str] = []

    def feed(self, chunk: str) -> List[_SSEEvent]:
        """Consume raw chunk text and yield completed events."""
        events: List[_SSEEvent] = []
        if not chunk:
            return events

        self._buffer += chunk

        while True:
            newline_idx = self._buffer.find("\n")
            if newline_idx == -1:
                break

            line = self._buffer[:newline_idx]
            self._buffer = self._buffer[newline_idx + 1:]

            # Trim CR from Windows-style endings
            if line.endswith("\r"):
                line = line[:-1]

            if line == "":
                # Blank line terminates the current event
                if self._current_event is not None or self._current_data:
                    data = "\n".join(self._current_data)
                    events.append(_SSEEvent(event=self._current_event, data=data))
                self._current_event = None
                self._current_data = []
                continue

            if line.startswith(":"):
                # Comment line - ignore
                continue

            if line.startswith("event:"):
                self._current_event = line[6:].lstrip()
                continue

            if line.startswith("data:"):
                data_value = line[5:]
                if data_value.startswith(" "):
                    data_value = data_value[1:]
                self._current_data.append(data_value)
                continue

            # Fallback: treat as data line (defensive)
            self._current_data.append(line)

        return events

    def flush(self) -> List[_SSEEvent]:
        """Flush any remaining buffered event (used at stream end)."""
        events: List[_SSEEvent] = []
        if self._current_event is not None or self._current_data:
            data = "\n".join(self._current_data)
            events.append(_SSEEvent(event=self._current_event, data=data))
        if self._buffer:
            events.append(_SSEEvent(event=None, data=self._buffer))
        self._current_event = None
        self._current_data = []
        self._buffer = ""
        return events


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


def convert_openai_tool_calls_to_anthropic(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI tool_calls to Anthropic tool_use content blocks."""
    logger.debug(f"[TOOL_CONVERSION] Converting {len(tool_calls)} OpenAI tool_calls to Anthropic format")
    logger.debug(f"[TOOL_CONVERSION] Raw OpenAI tool_calls: {json.dumps(tool_calls, indent=2)}")

    anthropic_content = []

    for idx, tool_call in enumerate(tool_calls):
        logger.debug(f"[TOOL_CONVERSION] Processing tool_call #{idx}: {json.dumps(tool_call, indent=2)}")

        function = tool_call.get("function", {})
        tool_id = tool_call.get("id", "")
        function_name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")

        logger.debug(f"[TOOL_CONVERSION]   - Tool ID: {tool_id}")
        logger.debug(f"[TOOL_CONVERSION]   - Function name: {function_name}")
        logger.debug(f"[TOOL_CONVERSION]   - Arguments (raw string): {arguments_str}")

        try:
            parsed_input = json.loads(arguments_str)
            logger.debug(f"[TOOL_CONVERSION]   - Parsed input: {json.dumps(parsed_input, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"[TOOL_CONVERSION]   - ERROR: Failed to parse arguments JSON: {e}")
            parsed_input = {}

        anthropic_block = {
            "type": "tool_use",
            "id": tool_id,
            "name": function_name,
            "input": parsed_input
        }

        logger.debug(f"[TOOL_CONVERSION]   - Converted to Anthropic block: {json.dumps(anthropic_block, indent=2)}")
        anthropic_content.append(anthropic_block)

    logger.debug(f"[TOOL_CONVERSION] Final Anthropic tool_use blocks: {json.dumps(anthropic_content, indent=2)}")
    return anthropic_content


def convert_openai_function_call_to_anthropic(function_call: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert OpenAI function_call (legacy) to Anthropic tool_use."""
    return [{
        "type": "tool_use",
        "id": f"func_{function_call.get('name', '')}",
        "name": function_call.get("name", ""),
        "input": json.loads(function_call.get("arguments", "{}"))
    }]


def convert_openai_tools_to_anthropic(openai_tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Convert OpenAI tools/functions to Anthropic tools format."""
    if not openai_tools:
        logger.debug("[TOOLS_SCHEMA] No tools to convert")
        return None

    logger.debug(f"[TOOLS_SCHEMA] Converting {len(openai_tools)} OpenAI tools to Anthropic format")
    logger.debug(f"[TOOLS_SCHEMA] Raw OpenAI tools: {json.dumps(openai_tools, indent=2)}")

    anthropic_tools = []

    for idx, tool in enumerate(openai_tools):
        logger.debug(f"[TOOLS_SCHEMA] Processing tool #{idx}: {json.dumps(tool, indent=2)}")

        # Check if it's already in Anthropic format (Cursor sends this)
        if "name" in tool and "description" in tool and "type" not in tool:
            # Already Anthropic format, pass through
            logger.debug(f"[TOOLS_SCHEMA]   - Tool already in Anthropic format: {tool.get('name')}")
            anthropic_tools.append(tool)
        elif tool.get("type") == "function":
            # Standard OpenAI format
            function = tool.get("function", {})
            tool_name = function.get("name", "")
            tool_description = function.get("description", "")
            tool_parameters = function.get("parameters", {})

            logger.debug(f"[TOOLS_SCHEMA]   - Converting OpenAI function tool")
            logger.debug(f"[TOOLS_SCHEMA]     - Name: {tool_name}")
            logger.debug(f"[TOOLS_SCHEMA]     - Description: {tool_description}")
            logger.debug(f"[TOOLS_SCHEMA]     - Parameters schema: {json.dumps(tool_parameters, indent=2)}")

            anthropic_tool = {
                "name": tool_name,
                "description": tool_description,
                "input_schema": tool_parameters
            }

            logger.debug(f"[TOOLS_SCHEMA]   - Converted to Anthropic tool: {json.dumps(anthropic_tool, indent=2)}")
            anthropic_tools.append(anthropic_tool)
        else:
            logger.warning(f"[TOOLS_SCHEMA]   - Unknown tool format (skipping): {json.dumps(tool, indent=2)}")

    logger.debug(f"[TOOLS_SCHEMA] Final Anthropic tools: {json.dumps(anthropic_tools, indent=2)}")
    return anthropic_tools if anthropic_tools else None


def convert_openai_functions_to_anthropic(openai_functions: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Convert OpenAI functions (legacy) to Anthropic tools format."""
    if not openai_functions:
        return None

    anthropic_tools = []

    for func in openai_functions:
        anthropic_tools.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {})
        })

    return anthropic_tools if anthropic_tools else None


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
            return
        last_msg = msgs[last_idx]
        content = last_msg.get("content")
        if not isinstance(content, list) or not content:
            return
        first = content[0]
        if isinstance(first, dict) and first.get("type") in ("thinking", "redacted_thinking"):
            return
        # collect tool_use ids
        tool_ids = [b.get("id") for b in content if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id")]
        if not tool_ids:
            return
        cached = None
        for tid in tool_ids:
            block = THINKING_CACHE.get(tid)
            if block and isinstance(block.get("signature"), str) and block.get("signature").strip():
                cached = block
                break
        if cached:
            logger.debug("Reattaching signed thinking block for tool_use id(s) %s", tool_ids)
            last_msg["content"] = [cached] + content
            msgs[last_idx] = last_msg
            anthropic_request["messages"] = msgs

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

        # If the conversation includes tool use but the last assistant message
        # does not begin with a signed thinking block, Anthropic will reject the
        # request. In that case, fall back to disabling thinking for this call.
        tools_in_history = _conversation_contains_tools(anthropic_request["messages"]) if anthropic_request.get("messages") else False
        last_assistant_has_thinking = _last_assistant_starts_with_thinking(anthropic_request["messages"]) if anthropic_request.get("messages") else False

        if tools_in_history and not last_assistant_has_thinking:
            logger.warning(
                "Thinking requested but missing signed thinking block on last assistant with tools; "
                "disabling thinking for this request to satisfy Anthropic requirements."
            )
        else:
            # Safe to enable thinking
            anthropic_request["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget
            }

        # Ensure max_tokens is sufficient for thinking + response
        # Reserve at least 1024 tokens for the actual response content
        min_response_tokens = 1024
        required_total = thinking_budget + min_response_tokens

        if anthropic_request.get("thinking") and anthropic_request["max_tokens"] < required_total:
            logger.warning(
                f"Increasing max_tokens from {anthropic_request['max_tokens']} to {required_total} "
                f"(thinking: {thinking_budget} + response: {min_response_tokens}) for reasoning level '{reasoning_level}'"
            )
            anthropic_request["max_tokens"] = required_total

        if anthropic_request.get("thinking"):
            logger.debug(
                f"Enabled thinking with budget {thinking_budget} tokens (reasoning_effort: {reasoning_level}), "
                f"max_tokens: {anthropic_request['max_tokens']}"
            )

    logger.debug("[REQUEST_CONVERSION] ===== FINAL ANTHROPIC REQUEST =====")
    logger.debug(f"[REQUEST_CONVERSION] {json.dumps(anthropic_request, indent=2)}")
    logger.debug("[REQUEST_CONVERSION] ===== END CONVERSION =====")

    return anthropic_request


def map_stop_reason_to_finish_reason(stop_reason: Optional[str]) -> str:
    """Map Anthropic stop_reason to OpenAI finish_reason."""
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls"
    }
    return mapping.get(stop_reason, "stop")


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

    # Build message
    message = {
        "role": "assistant",
        "content": text_content
    }

    if tool_calls:
        message["tool_calls"] = tool_calls

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


async def convert_anthropic_stream_to_openai(
    anthropic_stream: AsyncIterator[str],
    model: str,
    request_id: str,
    tracer: Optional["StreamTracer"] = None,
) -> AsyncIterator[str]:
    """
    Convert Anthropic SSE stream to OpenAI chat completion stream format.

    Args:
        anthropic_stream: Anthropic SSE stream
        model: Model name
        request_id: Request ID for logging

    Yields:
        OpenAI-formatted SSE chunks
    """
    completion_id = f"chatcmpl-{int(time.time())}"
    created = int(time.time())

    parser = _SSEParser()
    converted_index = 0

    # Track tool call state: map Anthropic block index -> OpenAI tool call metadata
    tool_call_states: Dict[int, Dict[str, Any]] = {}
    next_tool_index = 0
    thinking_states: Dict[int, Dict[str, Any]] = {}

    if tracer:
        tracer.log_note("starting OpenAI stream conversion")

    def emit(payload: Dict[str, Any]) -> str:
        nonlocal converted_index
        converted_index += 1
        chunk_str = f"data: {json.dumps(payload)}\n\n"
        if tracer:
            tracer.log_note(f"emitting OpenAI chunk #{converted_index}")
            tracer.log_converted_chunk(chunk_str)
        return chunk_str

    def emit_reasoning(text: str) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "reasoning": {
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": text
                                }
                            ]
                        }
                    },
                    "finish_reason": None
                }
            ]
        }
        return emit(payload)

    # Capture signed thinking + tool_use ids for potential reattachment
    current_tool_use_ids: List[str] = []
    # Map content_block index -> accumulator {thinking: str, signature: str | None}
    current_thinking_blocks: Dict[int, Dict[str, Any]] = {}

    try:
        stream_finished = False
        async for chunk in anthropic_stream:
            for event in parser.feed(chunk):
                event_name = (event.event or "").strip()
                raw_data = event.data.strip()

                if not raw_data:
                    continue

                # Skip keepalive pings early
                if event_name == "ping":
                    continue

                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    logger.warning(f"[{request_id}] Failed to decode SSE data: {raw_data}")
                    continue

                data_type = data.get("type") or event_name

                if data_type == "ping":
                    continue

                if data_type == "message_start":
                    initial_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": ""},
                                "finish_reason": None
                            }
                        ]
                    }
                    yield emit(initial_chunk)
                    continue

                if data_type == "content_block_start":
                    content_block = data.get("content_block", {}) or {}
                    block_type = content_block.get("type")

                    if block_type == "tool_use":
                        sse_index = data.get("index")
                        if sse_index is None:
                            logger.warning(f"[{request_id}] Tool use block missing index: {data}")
                            continue

                        logger.debug(f"[{request_id}] [STREAM_TOOL] Starting tool_use block at index {sse_index}")
                        logger.debug(f"[{request_id}] [STREAM_TOOL] Content block: {json.dumps(content_block, indent=2)}")

                        call_state = {
                            "openai_index": next_tool_index,
                            "id": content_block.get("id", ""),
                            "name": content_block.get("name", ""),
                            "arguments": ""
                        }
                        tool_call_states[sse_index] = call_state
                        next_tool_index += 1

                        logger.debug(f"[{request_id}] [STREAM_TOOL] Created call_state: {json.dumps(call_state, indent=2)}")

                        delta_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "tool_calls": [
                                            {
                                                "index": call_state["openai_index"],
                                                "id": call_state["id"],
                                                "type": "function",
                                                "function": {
                                                    "name": call_state["name"],
                                                    "arguments": ""
                                                }
                                            }
                                        ]
                                    },
                                    "finish_reason": None
                                }
                            ]
                        }

                        logger.debug(f"[{request_id}] [STREAM_TOOL] Emitting initial tool_call delta: {json.dumps(delta_chunk, indent=2)}")
                        yield emit(delta_chunk)
                        # Track tool_use ids for this assistant message
                        tool_id = content_block.get("id")
                        if tool_id:
                            current_tool_use_ids.append(tool_id)
                        continue

                    if block_type in ("thinking", "redacted_thinking"):
                        sse_index = data.get("index")
                        if sse_index is not None:
                            thinking_states[sse_index] = {
                                "type": block_type
                            }
                            # Initialize accumulator for this thinking block (capture signature if present)
                            signature = content_block.get("signature")
                            current_thinking_blocks[sse_index] = {
                                "thinking": "",
                                "signature": signature,
                            }
                        continue

                if data_type == "content_block_delta":
                    delta = data.get("delta", {}) or {}
                    delta_type = delta.get("type")

                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            delta_chunk = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": text},
                                        "finish_reason": None
                                    }
                                ]
                            }
                            yield emit(delta_chunk)
                        continue

                    if delta_type == "input_json_delta":
                        sse_index = data.get("index")
                        if sse_index is None:
                            logger.warning(f"[{request_id}] input_json_delta missing index: {data}")
                            continue

                        call_state = tool_call_states.get(sse_index)
                        if not call_state:
                            logger.warning(f"[{request_id}] input_json_delta for unknown tool index {sse_index}")
                            continue

                        partial_json = delta.get("partial_json", "")
                        call_state["arguments"] += partial_json

                        logger.debug(f"[{request_id}] [STREAM_TOOL] Received input_json_delta for index {sse_index}: {partial_json[:100]}...")
                        logger.debug(f"[{request_id}] [STREAM_TOOL] Accumulated arguments so far: {call_state['arguments'][:200]}...")

                        delta_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "tool_calls": [
                                            {
                                                "index": call_state["openai_index"],
                                                "id": call_state["id"],
                                                "type": "function",
                                                "function": {
                                                    "name": call_state["name"],
                                                    "arguments": partial_json
                                                }
                                            }
                                        ]
                                    },
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield emit(delta_chunk)
                        continue

                    if delta_type in ("thinking_delta", "redacted_thinking_delta"):
                        sse_index = data.get("index")
                        if sse_index is None:
                            logger.debug(f"[{request_id}] thinking delta missing index: {data}")
                            continue
                        if sse_index not in thinking_states:
                            thinking_states[sse_index] = {"type": delta_type}
                        reasoning_text = (
                            delta.get("text")
                            or delta.get("thinking")
                            or delta.get("partial_text")
                            or ""
                        )
                        if reasoning_text:
                            yield emit_reasoning(reasoning_text)
                            # Accumulate full thinking text for later reattachment
                            acc = current_thinking_blocks.get(sse_index)
                            if acc is not None:
                                acc["thinking"] = (acc.get("thinking", "") + reasoning_text)
                        continue

                if data_type == "content_block_stop":
                    sse_index = data.get("index")
                    if sse_index is not None:
                        tool_call_states.pop(sse_index, None)
                        thinking_states.pop(sse_index, None)
                    continue

                if data_type == "message_stop":
                    # On assistant message completion, persist signed thinking (if available) keyed by tool ids
                    # so we can reattach on the next request.
                    # Use the first thinking block captured.
                    saved_block = None
                    for acc in current_thinking_blocks.values():
                        sig = acc.get("signature")
                        if acc.get("thinking") and isinstance(sig, str) and sig.strip():
                            saved_block = {"type": "thinking", "thinking": acc["thinking"], "signature": sig}
                            break
                    if saved_block and current_tool_use_ids:
                        for tid in current_tool_use_ids:
                            THINKING_CACHE.put(tid, saved_block)
                    # Reset accumulators for safety in case of continued streaming
                    current_tool_use_ids.clear()
                    current_thinking_blocks.clear()

                if data_type == "message_delta":
                    delta = data.get("delta", {}) or {}
                    stop_reason = delta.get("stop_reason")

                    if stop_reason:
                        finish_reason = map_stop_reason_to_finish_reason(stop_reason)

                        final_chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": finish_reason
                                }
                            ]
                        }
                        yield emit(final_chunk)
                    continue

                if data_type == "message_stop":
                    if tracer:
                        tracer.log_note("received message_stop event")
                    stream_finished = True
                    break

                if data_type == "error":
                    # Handle error events - error can be a string or a dict
                    error_value = data.get("error", {})
                    if isinstance(error_value, str):
                        # Simple string error (e.g., from timeout)
                        error_chunk = {
                            "error": {
                                "message": error_value,
                                "type": "api_error"
                            }
                        }
                    elif isinstance(error_value, dict):
                        # Structured error from Anthropic
                        error_chunk = {
                            "error": {
                                "message": error_value.get("message", "Unknown error"),
                                "type": error_value.get("type", "api_error")
                            }
                        }
                    else:
                        # Fallback for unexpected format
                        error_chunk = {
                            "error": {
                                "message": str(error_value),
                                "type": "api_error"
                            }
                        }

                    if tracer:
                        tracer.log_error(f"anthropic error event: {error_chunk}")
                    yield emit(error_chunk)
                    stream_finished = True
                    break

            if stream_finished:
                break

    except Exception as e:
        logger.error(f"[{request_id}] Error converting stream: {e}")
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "conversion_error"
            }
        }
        if tracer:
            tracer.log_error(f"conversion exception: {e}")
        yield emit(error_chunk)

    # Send [DONE] marker
    done_chunk = "data: [DONE]\n\n"
    if tracer:
        tracer.log_note("emitting [DONE] marker")
        tracer.log_converted_chunk(done_chunk)
    yield done_chunk
