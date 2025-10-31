"""
Stream conversion from Anthropic SSE format to OpenAI streaming format.
"""
import time
import json
import logging
from typing import Dict, Any, List, AsyncIterator, Optional, TYPE_CHECKING

from utils.thinking_cache import THINKING_CACHE
from .sse_parser import SSEParser
from .response_converter import map_stop_reason_to_finish_reason

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stream_debug import StreamTracer


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

    parser = SSEParser()
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
                        "reasoning_content": text
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

                        # CRITICAL FIX: Do NOT stream partial JSON arguments character-by-character
                        # This causes clients like Cursor to parse incomplete JSON values
                        # (e.g., {"name": "A"} instead of {"name": "Add OpenRouter Example"})
                        # Instead, we buffer the complete arguments and send them at content_block_stop
                        #
                        # Original buggy code that streamed partial JSON:
                        # delta_chunk = {
                        #     "id": completion_id,
                        #     "object": "chat.completion.chunk",
                        #     "created": created,
                        #     "model": model,
                        #     "choices": [
                        #         {
                        #             "index": 0,
                        #             "delta": {
                        #                 "tool_calls": [
                        #                     {
                        #                         "index": call_state["openai_index"],
                        #                         "id": call_state["id"],
                        #                         "type": "function",
                        #                         "function": {
                        #                             "name": call_state["name"],
                        #                             "arguments": partial_json  # <-- BUG: partial JSON
                        #                         }
                        #                     }
                        #                 ]
                        #             },
                        #             "finish_reason": None
                        #         }
                        #     ]
                        # }
                        # yield emit(delta_chunk)

                        # Just accumulate the arguments, don't emit anything yet
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
                        # If this was a tool call, send the complete arguments now
                        call_state = tool_call_states.get(sse_index)
                        if call_state and call_state.get("arguments"):
                            logger.debug(f"[{request_id}] [STREAM_TOOL] Tool block stopped, sending complete arguments")
                            logger.debug(f"[{request_id}] [STREAM_TOOL] Complete arguments: {call_state['arguments']}")

                            # Send the complete arguments in one chunk
                            final_args_chunk = {
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
                                                        "arguments": call_state["arguments"]
                                                    }
                                                }
                                            ]
                                        },
                                        "finish_reason": None
                                    }
                                ]
                            }
                            yield emit(final_args_chunk)

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
                        logger.debug(f"[THINKING_CACHE] Storing signed thinking block for tool_use IDs: {current_tool_use_ids}")
                        for tid in current_tool_use_ids:
                            THINKING_CACHE.put(tid, saved_block)
                            logger.debug(f"[THINKING_CACHE] Stored thinking block for tool_use ID: {tid}")
                    elif saved_block and not current_tool_use_ids:
                        logger.debug("[THINKING_CACHE] Have signed thinking block but no tool_use IDs to cache it with")
                    elif not saved_block and current_tool_use_ids:
                        logger.debug(f"[THINKING_CACHE] Have tool_use IDs {current_tool_use_ids} but no signed thinking block to cache")
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
