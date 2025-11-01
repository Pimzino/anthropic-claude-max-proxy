"""
Native Anthropic messages endpoint handler.
"""
import json
import logging
import time
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from anthropic import (
    AnthropicMessageRequest,
    sanitize_anthropic_request,
    inject_claude_code_system_message,
    add_prompt_caching,
    make_anthropic_request,
    stream_anthropic_response,
)
from oauth import OAuthManager
import settings
from stream_debug import maybe_create_stream_tracer
from ..logging_utils import log_request

logger = logging.getLogger(__name__)
router = APIRouter()
oauth_manager = OAuthManager()


@router.post("/v1/messages")
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

    # Add cache_control to message content blocks for optimal caching
    anthropic_request = add_prompt_caching(anthropic_request)

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
    system = anthropic_request.get('system')
    if system:
        logger.debug(f"[{request_id}] - system: {type(system)} with {len(system)} elements")
    else:
        logger.debug(f"[{request_id}] - system: None")
    logger.debug(f"[{request_id}] - messages: {len(anthropic_request.get('messages', []))} messages")
    logger.debug(f"[{request_id}] - stream: {anthropic_request.get('stream')}")
    logger.debug(f"[{request_id}] - temperature: {anthropic_request.get('temperature')}")
    logger.debug(f"[{request_id}] FULL REQUEST BODY: {json.dumps(anthropic_request, indent=2)}")

    try:
        if request.stream:
            # Handle streaming response
            logger.debug(f"[{request_id}] Initiating streaming request")
            tracer = maybe_create_stream_tracer(
                enabled=settings.STREAM_TRACE_ENABLED,
                request_id=request_id,
                route="anthropic-messages",
                base_dir=settings.STREAM_TRACE_DIR,
                max_bytes=settings.STREAM_TRACE_MAX_BYTES,
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
                try:
                    error_json = response.json()
                except Exception:
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

