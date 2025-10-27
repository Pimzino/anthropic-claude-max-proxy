import asyncio
import json
import logging
import time
import uuid
import re
from typing import Dict, Any, List, Optional, AsyncIterator, Tuple

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from settings import (
    PORT,
    LOG_LEVEL,
    THINKING_FORCE_ENABLED,
    THINKING_DEFAULT_BUDGET,
    BIND_ADDRESS,
    REQUEST_TIMEOUT,
    STREAM_TRACE_ENABLED,
    STREAM_TRACE_DIR,
    STREAM_TRACE_MAX_BYTES,
)
from stream_debug import StreamTracer, maybe_create_stream_tracer
from oauth import OAuthManager
from storage import TokenStorage
from openai_compat import (
    convert_openai_request_to_anthropic,
    convert_anthropic_response_to_openai,
    convert_anthropic_stream_to_openai
)
from constants import OPENAI_MODELS_LIST

# Setup logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

# Global instances
oauth_manager = OAuthManager()
token_storage = TokenStorage()

# Create FastAPI app
app = FastAPI(title="Anthropic Claude Max Proxy", version="1.0.0")


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


# OpenAI compatibility models
class OpenAIFunction(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class OpenAITool(BaseModel):
    type: str = "function"
    function: OpenAIFunction


class OpenAIToolChoice(BaseModel):
    type: str
    function: Optional[Dict[str, str]] = None


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: Optional[int] = 4096
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: Optional[Any] = None  # Can be string or list
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None  # Can be string or dict
    functions: Optional[List[Dict[str, Any]]] = None  # Legacy
    function_call: Optional[Any] = None  # Legacy
    reasoning_effort: Optional[str] = None  # "low", "medium", "high" - maps to Anthropic thinking budget


# Thinking variant parsing removed - clients send thinking parameters directly


def log_request(request_id: str, request_data: Dict[str, Any], endpoint: str, headers: Optional[Dict[str, str]] = None):
    """Log incoming request details including headers"""
    logger.debug(f"[{request_id}] RAW REQUEST CAPTURE")
    logger.debug(f"[{request_id}] Endpoint: {endpoint}")
    logger.debug(f"[{request_id}] Model: {request_data.get('model', 'unknown')}")
    logger.debug(f"[{request_id}] Stream: {request_data.get('stream', False)}")
    logger.debug(f"[{request_id}] Max Tokens: {request_data.get('max_tokens', 'unknown')}")

    # Log incoming headers
    if headers:
        logger.debug(f"[{request_id}] ===== INCOMING HEADERS FROM CLIENT =====")
        for header_name, header_value in headers.items():
            # Redact sensitive headers
            if header_name.lower() in ['authorization', 'x-api-key', 'api-key']:
                logger.debug(f"[{request_id}] {header_name}: [REDACTED]")
            else:
                logger.debug(f"[{request_id}] {header_name}: {header_value}")

        # Specifically check for anthropic-beta header
        if 'anthropic-beta' in headers:
            logger.debug(f"[{request_id}] *** ANTHROPIC-BETA HEADER FOUND: {headers['anthropic-beta']} ***")

    # Log thinking parameters
    thinking = request_data.get('thinking')
    if thinking:
        logger.debug(f"[{request_id}] THINKING FIELDS DETECTED: {thinking}")

    # Check for alternative thinking fields
    alt_thinking_fields = ['max_thinking_tokens', 'thinking_enabled', 'thinking_budget']
    detected_fields = {field: request_data.get(field) for field in alt_thinking_fields if field in request_data}
    if detected_fields:
        logger.debug(f"[{request_id}] ALTERNATIVE THINKING FIELDS: {detected_fields}")


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

    # The exact spoof message from Claude Code - must be first
    claude_code_spoof = "You are Claude Code, Anthropic's official CLI for Claude."

    # Use simple string format (array format requires long context beta)
    if 'system' in modified_request and modified_request['system']:
        existing_system = modified_request['system']

        # Convert array format to string by extracting text
        if isinstance(existing_system, list):
            # Extract text from all array elements and join
            system_texts = []
            for element in existing_system:
                if isinstance(element, dict) and 'text' in element:
                    system_texts.append(element['text'])
                elif isinstance(element, str):
                    system_texts.append(element)
            existing_text = "\n\n".join(system_texts)
            modified_request['system'] = f"{claude_code_spoof}\n\n{existing_text}"
        else:
            # Already a string, just prepend
            modified_request['system'] = f"{claude_code_spoof}\n\n{existing_system}"
    else:
        # No existing system message - create simple string
        modified_request['system'] = claude_code_spoof

    logger.debug(f"Injected Claude Code system message (string format) for Anthropic authentication bypass")
    return modified_request


def strip_cache_control_from_messages(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip cache_control from user/assistant message content blocks.

    cache_control on message content requires context-1m-2025-08-07 beta (long context),
    which is not available to all Max subscriptions. System messages can keep cache_control.
    """
    modified_request = request_data.copy()

    if 'messages' not in modified_request:
        return modified_request

    modified_messages = []
    stripped_count = 0

    for message in modified_request['messages']:
        modified_message = message.copy()

        # Only process user and assistant messages (not system)
        if message.get('role') in ['user', 'assistant']:
            content = modified_message.get('content')

            if isinstance(content, list):
                # Content is an array of blocks - strip cache_control from each
                modified_content = []
                for block in content:
                    if isinstance(block, dict):
                        modified_block = block.copy()
                        if 'cache_control' in modified_block:
                            del modified_block['cache_control']
                            stripped_count += 1
                        modified_content.append(modified_block)
                    else:
                        modified_content.append(block)
                modified_message['content'] = modified_content

        modified_messages.append(modified_message)

    modified_request['messages'] = modified_messages

    if stripped_count > 0:
        logger.debug(f"Stripped cache_control from {stripped_count} message content blocks (long context beta not available)")

    return modified_request


async def make_anthropic_request(anthropic_request: Dict[str, Any], access_token: str, client_beta_headers: Optional[str] = None) -> httpx.Response:
    """Make a request to Anthropic API"""
    # Core required beta header for OAuth authentication
    required_betas = ["oauth-2025-04-20"]

    # Check for 1M context variant (custom metadata field set by model parsing)
    use_1m_context = anthropic_request.pop("_use_1m_context", False)
    if use_1m_context:
        required_betas.append("context-1m-2025-08-07")
        logger.debug("Adding context-1m beta (1M context model variant requested)")

    # Conditionally add thinking beta only if thinking is enabled
    if anthropic_request.get("thinking", {}).get("type") == "enabled":
        required_betas.append("interleaved-thinking-2025-05-14")
        logger.debug("Adding interleaved-thinking beta (thinking enabled)")

    # IGNORE client beta headers - they may request tier-4-only features
    # We control beta headers based on request features, not client requests
    if client_beta_headers:
        logger.debug(f"Ignoring client beta headers (not supported): {client_beta_headers}")

    beta_header_value = ",".join(required_betas)
    logger.debug(f"Final beta headers: {beta_header_value}")

    headers = {
        "host": "api.anthropic.com",
        "Accept": "application/json",
        "X-Stainless-Retry-Count": "0",
        "X-Stainless-Timeout": "600",
        "X-Stainless-Lang": "js",
        "X-Stainless-Package-Version": "0.60.0",
        "X-Stainless-OS": "Windows",
        "X-Stainless-Arch": "x64",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "v22.19.0",
        "anthropic-dangerous-direct-browser-access": "true",
        "authorization": f"Bearer {access_token}",
        "anthropic-version": "2023-06-01",
        "x-app": "cli",
        "User-Agent": "claude-cli/1.0.113 (external, cli)",
        "content-type": "application/json",
        "anthropic-beta": beta_header_value,
        "x-stainless-helper-method": "stream",
        "accept-language": "*",
        "sec-fetch-mode": "cors"
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=30.0)) as client:
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
    tracer: Optional[StreamTracer] = None,
) -> AsyncIterator[str]:
    """Stream response from Anthropic API"""
    # Core required beta header for OAuth authentication
    required_betas = ["oauth-2025-04-20"]

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
        "X-Stainless-Retry-Count": "0",
        "X-Stainless-Timeout": "600",
        "X-Stainless-Lang": "js",
        "X-Stainless-Package-Version": "0.60.0",
        "X-Stainless-OS": "Windows",
        "X-Stainless-Arch": "x64",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "v22.19.0",
        "anthropic-dangerous-direct-browser-access": "true",
        "authorization": f"Bearer {access_token}",
        "anthropic-version": "2023-06-01",
        "x-app": "cli",
        "User-Agent": "claude-cli/1.0.113 (external, cli)",
        "content-type": "application/json",
        "anthropic-beta": beta_header_value,
        "x-stainless-helper-method": "stream",
        "accept-language": "*",
        "sec-fetch-mode": "cors"
    }

    if tracer:
        tracer.log_note(f"dispatching POST {headers['host']}/v1/messages for streaming")

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=30.0)) as client:
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
                error_event = f"event: error\ndata: {{\"error\": \"Stream timeout after {REQUEST_TIMEOUT}s\"}}\n\n"
                if tracer:
                    tracer.log_error(f"anthropic stream timeout after {REQUEST_TIMEOUT}s")
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


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Only log API endpoints, not static files
    if request.url.path.startswith("/v1/"):
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

    return response


@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint with reasoning variants"""
    return {
        "object": "list",
        "data": [model.copy() for model in OPENAI_MODELS_LIST]
    }


@app.get("/auth/status")
async def auth_status():
    """Get token status without exposing secrets"""
    return token_storage.get_status()


@app.post("/v1/messages")
async def anthropic_messages(request: AnthropicMessageRequest, raw_request: Request):
    """Native Anthropic messages endpoint"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Capture raw request headers
    headers_dict = dict(raw_request.headers)

    logger.info(f"[{request_id}] ===== NEW ANTHROPIC MESSAGES REQUEST =====")
    log_request(request_id, request.model_dump(), "/v1/messages", headers_dict)

    # Get valid access token with automatic refresh
    access_token = await oauth_manager.get_valid_token_async()
    if not access_token:
        logger.error(f"[{request_id}] No valid token available")
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "OAuth expired; please authenticate using the CLI"}}
        )

    # Prepare Anthropic request (pass through client parameters directly)
    anthropic_request = request.model_dump()

    # Ensure max_tokens is sufficient if thinking is enabled
    thinking = anthropic_request.get("thinking")
    if thinking and thinking.get("type") == "enabled":
        thinking_budget = thinking.get("budget_tokens", 16000)
        min_response_tokens = 1024
        required_total = thinking_budget + min_response_tokens
        if anthropic_request["max_tokens"] < required_total:
            anthropic_request["max_tokens"] = required_total
            logger.debug(f"[{request_id}] Increased max_tokens to {required_total} (thinking: {thinking_budget} + response: {min_response_tokens})")

    # Sanitize request for Anthropic API constraints
    anthropic_request = sanitize_anthropic_request(anthropic_request)

    # Inject Claude Code system message to bypass authentication detection
    anthropic_request = inject_claude_code_system_message(anthropic_request)

    # Strip cache_control from message content blocks (requires long context beta)
    anthropic_request = strip_cache_control_from_messages(anthropic_request)

    # Extract client beta headers
    client_beta_headers = headers_dict.get("anthropic-beta")

    # Log the final beta headers that will be sent
    required_betas = ["claude-code-20250219", "interleaved-thinking-2025-05-14", "fine-grained-tool-streaming-2025-05-14"]
    if client_beta_headers:
        client_betas = [beta.strip() for beta in client_beta_headers.split(",")]
        all_betas = list(dict.fromkeys(required_betas + client_betas))
    else:
        all_betas = required_betas

    logger.debug(f"[{request_id}] FINAL ANTHROPIC REQUEST HEADERS: authorization=Bearer *****, anthropic-beta={','.join(all_betas)}, User-Agent=Claude-Code/1.0.0")
    logger.debug(f"[{request_id}] SYSTEM MESSAGE STRUCTURE: {json.dumps(anthropic_request.get('system', []), indent=2)}")
    logger.debug(f"[{request_id}] FULL REQUEST COMPARISON - Our request structure:")
    logger.debug(f"[{request_id}] - model: {anthropic_request.get('model')}")
    logger.debug(f"[{request_id}] - system: {type(anthropic_request.get('system'))} with {len(anthropic_request.get('system', []))} elements")
    logger.debug(f"[{request_id}] - messages: {len(anthropic_request.get('messages', []))} messages")
    logger.debug(f"[{request_id}] - stream: {anthropic_request.get('stream')}")
    logger.debug(f"[{request_id}] - temperature: {anthropic_request.get('temperature')}")
    logger.debug(f"[{request_id}] FULL REQUEST BODY: {json.dumps(anthropic_request, indent=2)}")

    try:
        if request.stream:
            # Handle streaming response
            logger.debug(f"[{request_id}] Initiating streaming request")
            tracer = maybe_create_stream_tracer(
                enabled=STREAM_TRACE_ENABLED,
                request_id=request_id,
                route="anthropic-messages",
                base_dir=STREAM_TRACE_DIR,
                max_bytes=STREAM_TRACE_MAX_BYTES,
            )

            async def raw_stream():
                try:
                    async for chunk in stream_anthropic_response(
                        request_id,
                        anthropic_request,
                        access_token,
                        client_beta_headers,
                        tracer=tracer,
                    ):
                        yield chunk
                finally:
                    if tracer:
                        tracer.close()

            return StreamingResponse(
                raw_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # Handle non-streaming response
            logger.debug(f"[{request_id}] Making non-streaming request")
            response = await make_anthropic_request(anthropic_request, access_token, client_beta_headers)

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{request_id}] Anthropic request completed in {elapsed_ms}ms status={response.status_code}")

            if response.status_code != 200:
                # Return the exact error from Anthropic API
                try:
                    error_json = response.json()
                except:
                    # If not JSON, return raw text
                    error_json = {"error": {"type": "api_error", "message": response.text}}

                logger.error(f"[{request_id}] Anthropic API error {response.status_code}: {json.dumps(error_json)}")

                # FastAPI will automatically set the status code and return this as JSON
                raise HTTPException(status_code=response.status_code, detail=error_json)

            # Return Anthropic response as-is (native format)
            anthropic_response = response.json()
            final_elapsed_ms = int((time.time() - start_time) * 1000)

            # Log usage information for debugging
            usage_info = anthropic_response.get("usage", {})
            input_tokens = usage_info.get("input_tokens", 0)
            output_tokens = usage_info.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            logger.debug(f"[{request_id}] [DEBUG] Response usage: input={input_tokens}, output={output_tokens}, total={total_tokens}")

            logger.info(f"[{request_id}] ===== ANTHROPIC MESSAGES FINISHED ===== Total time: {final_elapsed_ms}ms")
            return anthropic_response

    except HTTPException:
        final_elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] ===== ANTHROPIC MESSAGES FAILED ===== Total time: {final_elapsed_ms}ms")
        raise
    except Exception as e:
        final_elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] Request failed after {final_elapsed_ms}ms: {e}")
        raise HTTPException(status_code=500, detail={"error": {"message": str(e)}})


@app.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatCompletionRequest, raw_request: Request):
    """OpenAI-compatible chat completions endpoint"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] ===== NEW OPENAI CHAT COMPLETION REQUEST =====")
    logger.debug(f"[{request_id}] OpenAI Request: {request.model_dump()}")

    # Log HTTP headers to see if client is sending anthropic-beta
    headers_dict = dict(raw_request.headers)
    if "anthropic-beta" in headers_dict:
        logger.warning(f"[{request_id}] Client sent anthropic-beta header: {headers_dict['anthropic-beta']}")
    logger.debug(f"[{request_id}] All HTTP headers from client: {dict(raw_request.headers)}")

    # Get valid access token with automatic refresh
    access_token = await oauth_manager.get_valid_token_async()
    if not access_token:
        logger.error(f"[{request_id}] No valid token available")
        raise HTTPException(
            status_code=401,
            detail={"error": {"message": "OAuth expired; please authenticate using the CLI"}}
        )

    try:
        # Convert OpenAI request to Anthropic format
        openai_request_dict = request.model_dump()
        anthropic_request = convert_openai_request_to_anthropic(openai_request_dict)

        # Sanitize request for Anthropic API constraints
        anthropic_request = sanitize_anthropic_request(anthropic_request)

        # Inject Claude Code system message to bypass authentication detection
        anthropic_request = inject_claude_code_system_message(anthropic_request)

        # Strip cache_control from message content blocks (requires long context beta)
        anthropic_request = strip_cache_control_from_messages(anthropic_request)

        logger.debug(f"[{request_id}] Final Anthropic request (after stripping): {json.dumps(anthropic_request, indent=2)}")

        # Extract client beta headers (headers_dict already created at top of function)
        client_beta_headers = headers_dict.get("anthropic-beta")

        if request.stream:
            # Handle streaming response
            logger.debug(f"[{request_id}] Initiating streaming request (OpenAI format)")

            tracer = maybe_create_stream_tracer(
                enabled=STREAM_TRACE_ENABLED,
                request_id=request_id,
                route="openai-chat",
                base_dir=STREAM_TRACE_DIR,
                max_bytes=STREAM_TRACE_MAX_BYTES,
            )

            async def stream_with_conversion():
                """Wrapper to convert Anthropic stream to OpenAI format"""
                try:
                    anthropic_stream = stream_anthropic_response(
                        request_id,
                        anthropic_request,
                        access_token,
                        client_beta_headers,
                        tracer=tracer,
                    )
                    async for chunk in convert_anthropic_stream_to_openai(
                        anthropic_stream,
                        request.model,
                        request_id,
                        tracer=tracer,
                    ):
                        yield chunk
                finally:
                    if tracer:
                        tracer.close()

            return StreamingResponse(
                stream_with_conversion(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        else:
            # Handle non-streaming response
            logger.debug(f"[{request_id}] Making non-streaming request (OpenAI format)")
            response = await make_anthropic_request(anthropic_request, access_token, client_beta_headers)

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{request_id}] Anthropic request completed in {elapsed_ms}ms status={response.status_code}")

            if response.status_code != 200:
                # Return error in OpenAI format
                try:
                    error_json = response.json()
                    # Convert to OpenAI error format
                    openai_error = {
                        "error": {
                            "message": error_json.get("error", {}).get("message", "Unknown error"),
                            "type": error_json.get("error", {}).get("type", "api_error"),
                            "code": response.status_code
                        }
                    }
                except:
                    openai_error = {
                        "error": {
                            "message": response.text,
                            "type": "api_error",
                            "code": response.status_code
                        }
                    }

                logger.error(f"[{request_id}] Anthropic API error {response.status_code}: {json.dumps(openai_error)}")
                raise HTTPException(status_code=response.status_code, detail=openai_error)

            # Convert Anthropic response to OpenAI format
            anthropic_response = response.json()
            openai_response = convert_anthropic_response_to_openai(anthropic_response, request.model)

            final_elapsed_ms = int((time.time() - start_time) * 1000)

            # Log usage information for debugging
            usage_info = openai_response.get("usage", {})
            prompt_tokens = usage_info.get("prompt_tokens", 0)
            completion_tokens = usage_info.get("completion_tokens", 0)
            total_tokens = usage_info.get("total_tokens", 0)
            logger.debug(f"[{request_id}] [DEBUG] Response usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")

            logger.info(f"[{request_id}] ===== OPENAI CHAT COMPLETION FINISHED ===== Total time: {final_elapsed_ms}ms")
            return openai_response

    except HTTPException:
        final_elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] ===== OPENAI CHAT COMPLETION FAILED ===== Total time: {final_elapsed_ms}ms")
        raise
    except Exception as e:
        final_elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{request_id}] Request failed after {final_elapsed_ms}ms: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": 500
                }
            }
        )


class ProxyServer:
    """Proxy server wrapper for CLI control"""

    def __init__(self, debug: bool = False, debug_sse: bool = False, bind_address: str = None):
        self.server = None
        self.config = None
        self.debug = debug
        self.debug_sse = debug_sse
        self.bind_address = bind_address or BIND_ADDRESS

        # Configure debug logging if enabled
        if debug:
            self._setup_debug_logging()

    def _setup_debug_logging(self):
        """Setup debug logging for the proxy server"""
        import os
        from debug_console import setup_debug_logger

        # Get root logger and configure it for debug
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create file handler for debug log with append mode
        log_file = os.path.abspath('proxy_debug.log')
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')  # 'a' to append
        file_handler.setLevel(logging.DEBUG)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Set up debug console logger for Rich console output capture
        self.debug_console_logger = setup_debug_logger(log_file)

        # Store debug info globally for CLI access
        import __main__
        __main__._proxy_debug_enabled = True
        __main__._proxy_debug_logger = self.debug_console_logger

        logger.info(f"Debug logging enabled - appending to {log_file}")
        logger.info("Rich console output will be captured to debug log")

    def run(self):
        """Run the proxy server (blocking)"""
        logger.info(f"Starting Anthropic Claude Max Proxy on http://{self.bind_address}:{PORT}")
        logger.info(f"Available endpoints: /v1/messages (Anthropic), /v1/chat/completions (OpenAI)")
        if STREAM_TRACE_ENABLED:
            logger.warning(
                "Stream tracing is ENABLED - raw SSE chunks will be written inside '%s'",
                STREAM_TRACE_DIR,
            )
        self.config = uvicorn.Config(
            app,
            host=self.bind_address,
            port=PORT,
            log_level=LOG_LEVEL,
            access_log=False  # Reduce noise in CLI
        )
        self.server = uvicorn.Server(self.config)
        self.server.run()

    def stop(self):
        """Stop the proxy server"""
        if self.server:
            self.server.should_exit = True


if __name__ == "__main__":
    # If run directly, just start the server (for backward compatibility)
    logger.info(f"Starting Anthropic Claude Max Proxy on http://{BIND_ADDRESS}:{PORT}")
    logger.info("Note: Use 'python cli.py' for the interactive CLI interface")
    logger.info(f"Available endpoints: /v1/messages (Anthropic), /v1/chat/completions (OpenAI)")

    uvicorn.run(
        app,
        host=BIND_ADDRESS,
        port=PORT,
        log_level=LOG_LEVEL
    )
