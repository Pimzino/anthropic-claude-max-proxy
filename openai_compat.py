"""
OpenAI to Anthropic API compatibility layer.
Converts between OpenAI chat completion format and Anthropic messages format.
"""
import time
import json
import re
from typing import Dict, Any, List, Optional, AsyncIterator, Tuple
import logging

logger = logging.getLogger(__name__)

# Reasoning effort to thinking budget mapping
# Maps OpenAI's reasoning_effort levels to Anthropic's thinking budget_tokens
REASONING_BUDGET_MAP = {
    "low": 8000,
    "medium": 16000,
    "high": 32000
}


def parse_reasoning_model(model_name: str) -> Tuple[str, Optional[str]]:
    """
    Parse model name to extract base model and reasoning level.

    Args:
        model_name: Model name, potentially with -reasoning-{level} suffix

    Returns:
        tuple: (base_model_name, reasoning_level) where reasoning_level is None if not a reasoning model

    Examples:
        "claude-sonnet-4-20250514" -> ("claude-sonnet-4-20250514", None)
        "claude-sonnet-4-20250514-reasoning-high" -> ("claude-sonnet-4-20250514", "high")
    """
    if "-reasoning-" in model_name:
        parts = model_name.rsplit("-reasoning-", 1)
        base_model = parts[0]
        reasoning_level = parts[1] if len(parts) > 1 else None

        # Validate reasoning level
        if reasoning_level and reasoning_level in REASONING_BUDGET_MAP:
            return base_model, reasoning_level
        else:
            logger.warning(f"Invalid reasoning level in model name: {reasoning_level}. Valid values: {list(REASONING_BUDGET_MAP.keys())}")
            return model_name, None

    return model_name, None


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
                anthropic_msg["content"] = convert_openai_tool_calls_to_anthropic(msg["tool_calls"])

            # Handle function calls (legacy OpenAI format)
            if role == "assistant" and "function_call" in msg:
                anthropic_msg["content"] = convert_openai_function_call_to_anthropic(msg["function_call"])

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
        if tool.get("type") == "function":
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

    # Parse model name for reasoning variants
    model_name = openai_request.get("model", "claude-sonnet-4-5-20250929")
    base_model, model_reasoning_level = parse_reasoning_model(model_name)

    # Build Anthropic request (use base model name, not the reasoning variant)
    anthropic_request = {
        "model": base_model,
        "messages": messages,
        "max_tokens": openai_request.get("max_tokens", 4096),
        "stream": openai_request.get("stream", False)
    }

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
        elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
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
    request_id: str
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

    # Track content blocks
    current_text = ""
    tool_calls = []
    tool_call_index = 0

    try:
        async for chunk in anthropic_stream:
            # Parse SSE events
            if not chunk.strip():
                continue

            # Split into lines
            lines = chunk.strip().split('\n')
            event_type = None
            data = None

            for line in lines:
                if line.startswith('event:'):
                    event_type = line.split(':', 1)[1].strip()
                elif line.startswith('data:'):
                    data_str = line.split(':', 1)[1].strip()
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

            if not data:
                continue

            # Handle different event types
            if event_type == "message_start":
                # Send initial chunk
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
                yield f"data: {json.dumps(initial_chunk)}\n\n"

            elif event_type == "content_block_start":
                # Check if it's a tool use block
                content_block = data.get("content_block", {})
                if content_block.get("type") == "tool_use":
                    # Start a new tool call
                    tool_calls.append({
                        "index": tool_call_index,
                        "id": content_block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": content_block.get("name", ""),
                            "arguments": ""
                        }
                    })

            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                delta_type = delta.get("type")

                if delta_type == "text_delta":
                    # Text content delta
                    text = delta.get("text", "")
                    current_text += text

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
                    yield f"data: {json.dumps(delta_chunk)}\n\n"

                elif delta_type == "input_json_delta":
                    # Tool use arguments delta
                    if tool_calls:
                        partial_json = delta.get("partial_json", "")
                        tool_calls[-1]["function"]["arguments"] += partial_json

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
                                                "index": tool_calls[-1]["index"],
                                                "function": {
                                                    "arguments": partial_json
                                                }
                                            }
                                        ]
                                    },
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield f"data: {json.dumps(delta_chunk)}\n\n"

            elif event_type == "content_block_stop":
                # Content block finished
                if tool_calls:
                    tool_call_index += 1

            elif event_type == "message_delta":
                # Message finished
                delta = data.get("delta", {})
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
                    yield f"data: {json.dumps(final_chunk)}\n\n"

            elif event_type == "message_stop":
                # Stream complete
                break

            elif event_type == "error":
                # Error occurred
                error_chunk = {
                    "error": {
                        "message": data.get("error", {}).get("message", "Unknown error"),
                        "type": data.get("error", {}).get("type", "api_error")
                    }
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                break

    except Exception as e:
        logger.error(f"[{request_id}] Error converting stream: {e}")
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "conversion_error"
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

    # Send [DONE] marker
    yield "data: [DONE]\n\n"
