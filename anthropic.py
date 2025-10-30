"""
Anthropic API integration layer.
Handles request preparation, validation, and communication with Anthropic's Messages API.
"""
import logging
from typing import Dict, Any, List, Optional, AsyncIterator, TYPE_CHECKING
from pydantic import BaseModel, Field
import httpx

from constants import (
    CLAUDE_CODE_SPOOF_MESSAGE,
    USER_AGENT,
    X_APP_HEADER,
    STAINLESS_HEADERS,
)
from settings import REQUEST_TIMEOUT, STREAM_TIMEOUT, CONNECT_TIMEOUT, READ_TIMEOUT

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stream_debug import StreamTracer


# Pydantic models for native Anthropic API
class ThinkingParameter(BaseModel):
    type: str = Field(default="enabled")
    budget_tokens: int = Field(default=16000)


class AnthropicMessageRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: int
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    system: Optional[List[Dict[str, Any]]] = None
    stream: Optional[bool] = False
    thinking: Optional[ThinkingParameter] = None
    tools: Optional[List[Dict[str, Any]]] = None


def sanitize_anthropic_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize and validate request for Anthropic API"""
    sanitized = request_data.copy()

    # Universal parameter validation - clean invalid values regardless of thinking mode
    if 'top_p' in sanitized:
        top_p_val = sanitized['top_p']
        if top_p_val is None or top_p_val == "" or not isinstance(top_p_val, (int, float)):
            logger.debug(f"Removing invalid top_p value: {top_p_val} (type: {type(top_p_val)})")
            del sanitized['top_p']
        elif not (0.0 <= top_p_val <= 1.0):
            logger.debug(f"Removing out-of-range top_p value: {top_p_val}")
            del sanitized['top_p']

    if 'temperature' in sanitized:
        temp_val = sanitized['temperature']
        if temp_val is None or temp_val == "" or not isinstance(temp_val, (int, float)):
            logger.debug(f"Removing invalid temperature value: {temp_val} (type: {type(temp_val)})")
            del sanitized['temperature']

    if 'top_k' in sanitized:
        top_k_val = sanitized['top_k']
        if top_k_val is None or top_k_val == "" or not isinstance(top_k_val, int):
            logger.debug(f"Removing invalid top_k value: {top_k_val} (type: {type(top_k_val)})")
            del sanitized['top_k']
        elif top_k_val <= 0:
            logger.debug(f"Removing invalid top_k value (must be positive): {top_k_val}")
            del sanitized['top_k']

    # Handle tools parameter - remove if null or empty list
    if 'tools' in sanitized:
        tools_val = sanitized.get('tools')
        if tools_val is None:
            logger.debug("Removing null tools parameter (Anthropic API doesn't accept null values)")
            del sanitized['tools']
        elif isinstance(tools_val, list) and len(tools_val) == 0:
            logger.debug("Removing empty tools list (Anthropic API doesn't accept empty tools list)")
            del sanitized['tools']
        elif not isinstance(tools_val, list):
            logger.debug(f"Removing invalid tools parameter (must be a list): {type(tools_val)}")
            del sanitized['tools']

    # Handle thinking parameter - remove if null/None as Anthropic API doesn't accept null values
    thinking = sanitized.get('thinking')
    if thinking is None:
        logger.debug("Removing null thinking parameter (Anthropic API doesn't accept null values)")
        sanitized.pop('thinking', None)
    elif thinking and thinking.get('type') == 'enabled':
        logger.debug("Thinking enabled - applying Anthropic API constraints")

        # Apply Anthropic thinking constraints
        if 'temperature' in sanitized and sanitized['temperature'] is not None and sanitized['temperature'] != 1.0:
            logger.debug(f"Adjusting temperature from {sanitized['temperature']} to 1.0 (thinking enabled)")
            sanitized['temperature'] = 1.0

        if 'top_p' in sanitized and sanitized['top_p'] is not None and not (0.95 <= sanitized['top_p'] <= 1.0):
            adjusted_top_p = max(0.95, min(1.0, sanitized['top_p']))
            logger.debug(f"Adjusting top_p from {sanitized['top_p']} to {adjusted_top_p} (thinking constraints)")
            sanitized['top_p'] = adjusted_top_p

        # Remove top_k as it's not allowed with thinking
        if 'top_k' in sanitized:
            logger.debug("Removing top_k parameter (not allowed with thinking)")
            del sanitized['top_k']

    return sanitized


def inject_claude_code_system_message(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inject Claude Code system message to bypass authentication detection"""
    modified_request = request_data.copy()

    claude_code_spoof = CLAUDE_CODE_SPOOF_MESSAGE
    spoof_block = {"type": "text", "text": claude_code_spoof}

    existing_system = modified_request.get("system")

    if isinstance(existing_system, list):
        if existing_system and isinstance(existing_system[0], dict) and existing_system[0].get("text") == claude_code_spoof:
            return modified_request
        modified_request["system"] = [spoof_block] + existing_system
    elif isinstance(existing_system, str):
        if existing_system.startswith(claude_code_spoof):
            return modified_request
        modified_request["system"] = [spoof_block, {"type": "text", "text": existing_system}]
    elif existing_system is None:
        modified_request["system"] = [spoof_block]
    elif isinstance(existing_system, dict) and existing_system.get("text") == claude_code_spoof:
        modified_request["system"] = [existing_system]
    else:
        # Unrecognized format, wrap it to ensure spoof is first
        modified_request["system"] = [spoof_block, existing_system] if existing_system else [spoof_block]

    logger.debug("Injected Claude Code system message for Anthropic authentication bypass")
    return modified_request


def count_existing_cache_controls(request_data: Dict[str, Any]) -> int:
    """Count existing cache_control blocks in the request."""
    count = 0

    # Count in system message
    if 'system' in request_data:
        system = request_data['system']
        if isinstance(system, list):
            for block in system:
                if isinstance(block, dict) and 'cache_control' in block:
                    count += 1

    # Count in messages
    if 'messages' in request_data:
        for message in request_data['messages']:
            content = message.get('content')
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and 'cache_control' in block:
                        count += 1

    return count


def add_prompt_caching(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add prompt caching breakpoints following Anthropic's best practices.

    Strategy:
    - Add cache_control to system message (if present)
    - Add cache_control to the last 2 user messages to cache recent conversation
    - Only mark the last content block in each cached message
    - Respect Anthropic's limit of 4 cache_control blocks maximum

    Anthropic prompt caching docs: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    """
    modified_request = request_data.copy()
    MAX_CACHE_BLOCKS = 4

    # Count existing cache_control blocks
    existing_count = count_existing_cache_controls(modified_request)
    cache_added_count = 0

    if existing_count >= MAX_CACHE_BLOCKS:
        logger.debug(f"Request already has {existing_count} cache_control blocks (max: {MAX_CACHE_BLOCKS}), skipping auto-caching")
        return modified_request

    remaining_slots = MAX_CACHE_BLOCKS - existing_count
    logger.debug(f"Found {existing_count} existing cache_control blocks, {remaining_slots} slots available")

    # Add cache_control to system message if present and we have room
    if 'system' in modified_request and remaining_slots > 0:
        system = modified_request['system']

        # System can be a string or array of content blocks
        if isinstance(system, list) and len(system) > 0:
            # Mark the last system block for caching
            last_block = system[-1]
            if isinstance(last_block, dict) and 'cache_control' not in last_block:
                last_block['cache_control'] = {'type': 'ephemeral'}
                cache_added_count += 1
                remaining_slots -= 1
                logger.debug("Added cache_control to system message (last block)")
        elif isinstance(system, str):
            # Convert string system to array format with cache_control
            modified_request['system'] = [
                {
                    'type': 'text',
                    'text': system,
                    'cache_control': {'type': 'ephemeral'}
                }
            ]
            cache_added_count += 1
            remaining_slots -= 1
            logger.debug("Added cache_control to system message (converted from string)")

    # Add cache_control to the last 2 user messages for conversation caching
    if 'messages' in modified_request and remaining_slots > 0:
        messages = modified_request['messages']

        # Find the last 2 user messages
        user_message_indices = [i for i, msg in enumerate(messages) if msg.get('role') == 'user']

        # Cache the last 2 user messages (or fewer if there aren't 2 or we don't have room)
        num_to_cache = min(2, len(user_message_indices), remaining_slots)
        cache_indices = user_message_indices[-num_to_cache:] if num_to_cache > 0 else []

        for idx in cache_indices:
            if remaining_slots <= 0:
                break

            message = messages[idx]
            content = message.get('content')

            if isinstance(content, list) and len(content) > 0:
                # Mark the last content block for caching
                last_block = content[-1]
                if isinstance(last_block, dict) and 'cache_control' not in last_block:
                    last_block['cache_control'] = {'type': 'ephemeral'}
                    cache_added_count += 1
                    remaining_slots -= 1
            elif isinstance(content, str):
                # Convert string content to array format with cache_control
                messages[idx]['content'] = [
                    {
                        'type': 'text',
                        'text': content,
                        'cache_control': {'type': 'ephemeral'}
                    }
                ]
                cache_added_count += 1
                remaining_slots -= 1

    if cache_added_count > 0:
        total_count = existing_count + cache_added_count
        logger.debug(f"Added prompt caching to {cache_added_count} locations (total: {total_count}/{MAX_CACHE_BLOCKS})")

    return modified_request


async def make_anthropic_request(anthropic_request: Dict[str, Any], access_token: str, client_beta_headers: Optional[str] = None) -> httpx.Response:
    """Make a non-streaming request to Anthropic API"""
    # Core required beta header for OAuth authentication
    required_betas = ["oauth-2025-04-20"]

    if not anthropic_request.get("system"):
        anthropic_request = inject_claude_code_system_message(anthropic_request)

    # Check if thinking is enabled
    thinking = anthropic_request.get("thinking")
    if thinking and thinking.get("type") == "enabled":
        required_betas.append("interleaved-thinking-2025-05-14")

    # Check if tools are present
    if anthropic_request.get("tools"):
        required_betas.append("fine-grained-tool-streaming-2025-05-14")

    # Merge with client beta headers if provided
    if client_beta_headers:
        client_betas = [beta.strip() for beta in client_beta_headers.split(",")]
        all_betas = list(dict.fromkeys(required_betas + client_betas))
    else:
        all_betas = required_betas

    beta_header_value = ",".join(all_betas)

    headers = {
        "authorization": f"Bearer {access_token}",
        "anthropic-version": "2023-06-01",
        "x-app": X_APP_HEADER,
        **STAINLESS_HEADERS,
        "User-Agent": USER_AGENT,
        "content-type": "application/json",
        "anthropic-beta": beta_header_value,
        "x-stainless-helper-method": "stream",
        "accept-language": "*",
        "sec-fetch-mode": "cors"
    }

    # Use REQUEST_TIMEOUT for non-streaming with industry-standard CONNECT_TIMEOUT
    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=anthropic_request,
            headers=headers
        )
        return response


async def stream_anthropic_response(
    request_id: str,
    anthropic_request: Dict[str, Any],
    access_token: str,
    client_beta_headers: Optional[str] = None,
    tracer: Optional["StreamTracer"] = None,
) -> AsyncIterator[str]:
    """Stream response from Anthropic API"""
    # Core required beta header for OAuth authentication
    required_betas = ["oauth-2025-04-20"]

    if not anthropic_request.get("system"):
        anthropic_request = inject_claude_code_system_message(anthropic_request)

    # Check for 1M context variant (custom metadata field set by model parsing)
    use_1m_context = anthropic_request.pop("_use_1m_context", False)
    if use_1m_context:
        required_betas.append("context-1m-2025-08-07")
        logger.debug(f"[{request_id}] Adding context-1m beta (1M context model variant requested)")

    # Conditionally add thinking beta only if thinking is enabled
    if anthropic_request.get("thinking", {}).get("type") == "enabled":
        required_betas.append("interleaved-thinking-2025-05-14")
        logger.debug(f"[{request_id}] Adding interleaved-thinking beta (thinking enabled)")

    # IGNORE client beta headers - they may request tier-4-only features
    # We control beta headers based on request features, not client requests
    if client_beta_headers:
        logger.debug(f"[{request_id}] Ignoring client beta headers (not supported): {client_beta_headers}")

    beta_header_value = ",".join(required_betas)
    logger.debug(f"[{request_id}] Final beta headers: {beta_header_value}")

    if tracer:
        tracer.log_note(
            f"starting Anthropic stream: model={anthropic_request.get('model')} "
            f"use_1m={use_1m_context} thinking={anthropic_request.get('thinking')}"
        )
        tracer.log_note(f"anthropic beta header={beta_header_value}")

    headers = {
        "host": "api.anthropic.com",
        "Accept": "application/json",
        **STAINLESS_HEADERS,
        "anthropic-dangerous-direct-browser-access": "true",
        "authorization": f"Bearer {access_token}",
        "anthropic-version": "2023-06-01",
        "x-app": X_APP_HEADER,
        "User-Agent": USER_AGENT,
        "content-type": "application/json",
        "anthropic-beta": beta_header_value,
        "x-stainless-helper-method": "stream",
        "accept-language": "*",
        "sec-fetch-mode": "cors"
    }

    if tracer:
        tracer.log_note(f"dispatching POST {headers['host']}/v1/messages for streaming")

    # Use STREAM_TIMEOUT for streaming requests with READ_TIMEOUT between chunks
    async with httpx.AsyncClient(timeout=httpx.Timeout(STREAM_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            json=anthropic_request,
            headers=headers
        ) as response:
            if tracer:
                tracer.log_note(f"anthropic responded with status={response.status_code}")

            if response.status_code != 200:
                # For error responses, stream them back as SSE events
                error_text = await response.aread()
                error_json = error_text.decode()
                logger.error(f"[{request_id}] Anthropic API error {response.status_code}: {error_json}")
                if tracer:
                    tracer.log_error(f"anthropic error status={response.status_code} body={error_json}")

                # Format error as SSE event for proper client handling
                error_event = f"event: error\ndata: {error_json}\n\n"
                if tracer:
                    tracer.log_note("yielding synthetic error SSE event (non-200 response)")
                yield error_event
                return

            # Stream successful response chunks
            chunk_index = 0
            try:
                async for chunk in response.aiter_text():
                    chunk_index += 1
                    if tracer:
                        tracer.log_note(f"received anthropic chunk #{chunk_index}")
                        tracer.log_source_chunk(chunk)
                    yield chunk
            except httpx.ReadTimeout:
                error_event = f"event: error\ndata: {{\"error\": \"Stream timeout after {STREAM_TIMEOUT}s\"}}\n\n"
                if tracer:
                    tracer.log_error(f"anthropic stream timeout after {STREAM_TIMEOUT}s")
                    tracer.log_note("yielding timeout SSE event")
                yield error_event
            except httpx.RemoteProtocolError as e:
                error_event = f"event: error\ndata: {{\"error\": \"Connection closed: {str(e)}\"}}\n\n"
                if tracer:
                    tracer.log_error(f"anthropic stream closed unexpectedly: {str(e)}")
                    tracer.log_note("yielding remote protocol error SSE event")
                yield error_event
            finally:
                if tracer:
                    tracer.log_note("anthropic stream closed")
