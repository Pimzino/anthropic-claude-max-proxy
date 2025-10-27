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


def convert_openai_messages_to_anthropic(openai_messages: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Convert OpenAI messages to Anthropic format.

    Returns:
        tuple: (anthropic_messages, system_message)
    """
    anthropic_messages = []
    system_messages = []

    for msg in openai_messages:
        role = msg.get("role")
        content = msg.get("content")

        # Extract system messages
        if role == "system":
            if isinstance(content, str):
                system_messages.append(content)
            elif isinstance(content, list):
                # Handle array content for system messages
                for item in content:
                    if item.get("type") == "text":
                        system_messages.append(item.get("text", ""))
            continue

        # Convert user/assistant messages
        if role in ["user", "assistant"]:
            anthropic_msg = {"role": role}

            # Handle content - can be string or array
            if isinstance(content, str):
                anthropic_msg["content"] = content
            elif isinstance(content, list):
                # Convert content array (handles images, text, etc.)
                anthropic_msg["content"] = convert_openai_content_to_anthropic(content)
            else:
                anthropic_msg["content"] = ""

            # Handle tool calls in assistant messages
            if role == "assistant" and "tool_calls" in msg:
                # Convert existing content to array format if needed
                existing_content = anthropic_msg["content"]
                if isinstance(existing_content, str):
                    if existing_content:
                        content_array = [{"type": "text", "text": existing_content}]
                    else:
                        content_array = []
                elif isinstance(existing_content, list):
                    content_array = existing_content
                else:
                    content_array = []

                # Append tool_use blocks to existing content
                tool_use_blocks = convert_openai_tool_calls_to_anthropic(msg["tool_calls"])
                content_array.extend(tool_use_blocks)
                anthropic_msg["content"] = content_array

            # Handle function calls (legacy OpenAI format)
            if role == "assistant" and "function_call" in msg:
                # Convert existing content to array format if needed
                existing_content = anthropic_msg["content"]
                if isinstance(existing_content, str):
                    if existing_content:
                        content_array = [{"type": "text", "text": existing_content}]
                    else:
                        content_array = []
                elif isinstance(existing_content, list):
                    content_array = existing_content
                else:
                    content_array = []

                # Append function call block to existing content
                function_blocks = convert_openai_function_call_to_anthropic(msg["function_call"])
                content_array.extend(function_blocks)
                anthropic_msg["content"] = content_array

            anthropic_messages.append(anthropic_msg)

        # Handle tool response messages
        elif role == "tool":
            # OpenAI tool responses need to be converted to user messages with tool_result
            tool_use_id = msg.get("tool_call_id", "")
            anthropic_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": content if isinstance(content, str) else json.dumps(content)
                    }
                ]
            })

        # Handle function response messages (legacy)
        elif role == "function":
            function_name = msg.get("name", "")
            anthropic_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"func_{function_name}",
                        "content": content if isinstance(content, str) else json.dumps(content)
                    }
                ]
            })

    # Combine system messages
    system_text = "\n\n".join(system_messages) if system_messages else None

    return anthropic_messages, system_text


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
    anthropic_content = []

    for tool_call in tool_calls:
        function = tool_call.get("function", {})
        anthropic_content.append({
            "type": "tool_use",
            "id": tool_call.get("id", ""),
            "name": function.get("name", ""),
            "input": json.loads(function.get("arguments", "{}"))
        })

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
        return None

    anthropic_tools = []

    for tool in openai_tools:
        # Check if it's already in Anthropic format (Cursor sends this)
        if "name" in tool and "description" in tool and "type" not in tool:
            # Already Anthropic format, pass through
            anthropic_tools.append(tool)
            logger.debug(f"Tool already in Anthropic format: {tool.get('name')}")
        elif tool.get("type") == "function":
            # Standard OpenAI format
            function = tool.get("function", {})
            anthropic_tools.append({
                "name": function.get("name", ""),
                "description": function.get("description", ""),
                "input_schema": function.get("parameters", {})
            })

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
    # Convert messages
    messages, system_text = convert_openai_messages_to_anthropic(openai_request.get("messages", []))

    # Parse model name for reasoning and 1M context variants
    model_name = openai_request.get("model", "claude-sonnet-4-5-20250929")
    base_model, model_reasoning_level, use_1m_context = resolve_model_metadata(model_name)

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

    # Add system message if present
    if system_text:
        anthropic_request["system"] = system_text

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
    if "tools" in openai_request:
        tools = convert_openai_tools_to_anthropic(openai_request["tools"])
        if tools:
            anthropic_request["tools"] = tools

    # Convert functions (legacy)
    if "functions" in openai_request:
        tools = convert_openai_functions_to_anthropic(openai_request["functions"])
        if tools:
            anthropic_request["tools"] = tools

    # Handle tool_choice
    if "tool_choice" in openai_request:
        tool_choice = openai_request["tool_choice"]
        if tool_choice == "none":
            # Don't include tools
            anthropic_request.pop("tools", None)
        elif tool_choice == "auto":
            # Default Anthropic behavior
            pass
        elif isinstance(tool_choice, dict):
            # Handle dict format (Cursor sends {'type': 'auto'})
            choice_type = tool_choice.get("type")
            if choice_type == "auto" or choice_type is None:
                # Auto mode - default Anthropic behavior
                pass
            elif choice_type == "function":
                # Specific tool
                function_name = tool_choice.get("function", {}).get("name")
                if function_name:
                    anthropic_request["tool_choice"] = {
                        "type": "tool",
                        "name": function_name
                    }

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
        # Do NOT inject a thinking content block into messages; Anthropic expects
        # thinking blocks to be model-generated and signed. Use top-level parameter only.
        anthropic_request["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget
        }

        # Ensure max_tokens is sufficient for thinking + response
        # Reserve at least 1024 tokens for the actual response content
        min_response_tokens = 1024
        required_total = thinking_budget + min_response_tokens

        if anthropic_request["max_tokens"] < required_total:
            logger.warning(
                f"Increasing max_tokens from {anthropic_request['max_tokens']} to {required_total} "
                f"(thinking: {thinking_budget} + response: {min_response_tokens}) for reasoning level '{reasoning_level}'"
            )
            anthropic_request["max_tokens"] = required_total

        logger.debug(
            f"Enabled thinking with budget {thinking_budget} tokens (reasoning_effort: {reasoning_level}), "
            f"max_tokens: {anthropic_request['max_tokens']}"
        )

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


def convert_anthropic_content_to_openai(content: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    """
    Convert Anthropic content blocks to OpenAI message content and tool_calls.

    Returns:
        tuple: (text_content, tool_calls)
    """
    text_parts = []
    tool_calls = []

    for block in content:
        block_type = block.get("type")

        if block_type == "text":
            text_parts.append(block.get("text", ""))

        elif block_type == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {}))
                }
            })

    text_content = "".join(text_parts) if text_parts else None
    tool_calls_result = tool_calls if tool_calls else None

    return text_content, tool_calls_result


def convert_anthropic_response_to_openai(anthropic_response: Dict[str, Any], model: str) -> Dict[str, Any]:
    """
    Convert Anthropic message response to OpenAI chat completion format.

    Args:
        anthropic_response: Anthropic API response
        model: Model name to include in response

    Returns:
        OpenAI chat completion response
    """
    # Extract content
    content = anthropic_response.get("content", [])
    text_content, tool_calls = convert_anthropic_content_to_openai(content)

    # Build message
    message = {
        "role": "assistant",
        "content": text_content
    }

    if tool_calls:
        message["tool_calls"] = tool_calls

    # Map stop reason
    finish_reason = map_stop_reason_to_finish_reason(anthropic_response.get("stop_reason"))

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
        "usage": {
            "prompt_tokens": anthropic_response.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": anthropic_response.get("usage", {}).get("output_tokens", 0),
            "total_tokens": (
                anthropic_response.get("usage", {}).get("input_tokens", 0) +
                anthropic_response.get("usage", {}).get("output_tokens", 0)
            )
        }
    }

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

                        call_state = {
                            "openai_index": next_tool_index,
                            "id": content_block.get("id", ""),
                            "name": content_block.get("name", ""),
                            "arguments": ""
                        }
                        tool_call_states[sse_index] = call_state
                        next_tool_index += 1

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
                        yield emit(delta_chunk)
                        continue

                    if block_type in ("thinking", "redacted_thinking"):
                        sse_index = data.get("index")
                        if sse_index is not None:
                            thinking_states[sse_index] = {
                                "type": block_type
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
                        continue

                if data_type == "content_block_stop":
                    sse_index = data.get("index")
                    if sse_index is not None:
                        tool_call_states.pop(sse_index, None)
                        thinking_states.pop(sse_index, None)
                    continue

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
                    error_chunk = {
                        "error": {
                            "message": data.get("error", {}).get("message", "Unknown error"),
                            "type": data.get("error", {}).get("type", "api_error")
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
