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
    STREAM_TIMEOUT,
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
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
from anthropic import (
    ThinkingParameter,
    AnthropicMessageRequest,
    sanitize_anthropic_request,
    inject_claude_code_system_message,
    add_prompt_caching,
    make_anthropic_request,
    stream_anthropic_response,
)
from constants import (
    OPENAI_MODELS_LIST,
    CLAUDE_CODE_SPOOF_MESSAGE,
    USER_AGENT,
    X_APP_HEADER,
    STAINLESS_HEADERS,
    is_custom_model,
    get_custom_model_config,
)
from custom_provider import (
    make_custom_provider_request,
    stream_custom_provider_response,
)

# Setup logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

# Global instances
oauth_manager = OAuthManager()
token_storage = TokenStorage()

# Create FastAPI app
app = FastAPI(title="Anthropic Claude Max Proxy", version="1.0.0")


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

    # Log model routing decision
    is_custom = is_custom_model(request.model)
    logger.info(f"[{request_id}] Model: {request.model} | Custom: {is_custom} | Routing to: {'custom provider' if is_custom else 'Anthropic'}")

    # Check if this is a custom model (non-Anthropic)
    if is_custom_model(request.model):
        logger.info(f"[{request_id}] Routing to custom provider for model: {request.model}")

        # Get custom model configuration
        model_config = get_custom_model_config(request.model)
        if not model_config:
            logger.error(f"[{request_id}] Custom model config not found: {request.model}")
            raise HTTPException(
                status_code=400,
                detail={"error": {"message": f"Custom model '{request.model}' not properly configured"}}
            )

        base_url = model_config["base_url"]
        api_key = model_config["api_key"]

        try:
            # Pass request directly to custom provider (no Anthropic conversion)
            openai_request_dict = request.model_dump()

            if request.stream:
                # Handle streaming response
                logger.debug(f"[{request_id}] Initiating streaming request to custom provider")

                tracer = maybe_create_stream_tracer(
                    enabled=STREAM_TRACE_ENABLED,
                    request_id=request_id,
                    route="custom-provider",
                    base_dir=STREAM_TRACE_DIR,
                    max_bytes=STREAM_TRACE_MAX_BYTES,
                )

                async def custom_stream():
                    try:
                        async for chunk in stream_custom_provider_response(
                            openai_request_dict,
                            base_url,
                            api_key,
                            request_id,
                            tracer=tracer,
                        ):
                            yield chunk
                    finally:
                        if tracer:
                            tracer.close()

                return StreamingResponse(
                    custom_stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
                )
            else:
                # Handle non-streaming response
                logger.debug(f"[{request_id}] Making non-streaming request to custom provider")
                response = await make_custom_provider_request(
                    openai_request_dict,
                    base_url,
                    api_key,
                    request_id
                )

                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[{request_id}] Custom provider request completed in {elapsed_ms}ms status={response.status_code}")

                if response.status_code != 200:
                    # Return error in OpenAI format
                    try:
                        error_json = response.json()
                    except:
                        error_json = {
                            "error": {
                                "message": response.text,
                                "type": "api_error",
                                "code": response.status_code
                            }
                        }

                    logger.error(f"[{request_id}] Custom provider error {response.status_code}: {error_json}")
                    raise HTTPException(status_code=response.status_code, detail=error_json)

                # Return response as-is (already in OpenAI format)
                openai_response = response.json()

                final_elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[{request_id}] ===== CUSTOM PROVIDER COMPLETION FINISHED ===== Total time: {final_elapsed_ms}ms")
                return openai_response

        except HTTPException:
            final_elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[{request_id}] ===== CUSTOM PROVIDER COMPLETION FAILED ===== Total time: {final_elapsed_ms}ms")
            raise
        except Exception as e:
            final_elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[{request_id}] Custom provider request failed after {final_elapsed_ms}ms: {e}")
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

    # Get valid access token with automatic refresh (for Anthropic models)
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

        # Add cache_control to message content blocks for optimal caching
        anthropic_request = add_prompt_caching(anthropic_request)

        logger.debug(f"[{request_id}] Final Anthropic request (after adding prompt caching): {json.dumps(anthropic_request, indent=2)}")

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
