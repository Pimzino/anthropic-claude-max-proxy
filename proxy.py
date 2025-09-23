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
    PORT, LOG_LEVEL, THINKING_FORCE_ENABLED, THINKING_DEFAULT_BUDGET, BIND_ADDRESS, REQUEST_TIMEOUT
)
from oauth import OAuthManager
from storage import TokenStorage

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
    """Inject Claude Code system message to bypass authentication detection (matches real Claude Code format)"""
    modified_request = request_data.copy()

    # The exact spoof message from Claude Code - must be first system message
    claude_code_spoof_element = {
        "type": "text",
        "text": "You are Claude Code, Anthropic's official CLI for Claude.",
        "cache_control": {"type": "ephemeral"}
    }

    # Claude Code uses array format for system messages
    if 'system' in modified_request and modified_request['system']:
        existing_system = modified_request['system']

        # If existing system is already an array, prepend our spoof
        if isinstance(existing_system, list):
            modified_request['system'] = [claude_code_spoof_element] + existing_system
        else:
            # Convert string system to array format with cache control
            existing_system_element = {
                "type": "text",
                "text": existing_system,
                "cache_control": {"type": "ephemeral"}
            }
            modified_request['system'] = [claude_code_spoof_element, existing_system_element]
    else:
        # No existing system message - create array with just the spoof
        modified_request['system'] = [claude_code_spoof_element]

    logger.debug(f"Injected Claude Code system message array for Anthropic authentication bypass")
    logger.debug(f"Final system message array length: {len(modified_request.get('system', []))}")
    return modified_request


async def make_anthropic_request(anthropic_request: Dict[str, Any], access_token: str, client_beta_headers: Optional[str] = None) -> httpx.Response:
    """Make a request to Anthropic API"""
    # Required beta headers for authentication flow
    required_betas = ["claude-code-20250219", "oauth-2025-04-20", "fine-grained-tool-streaming-2025-05-14"]

    # Merge client beta headers if provided
    if client_beta_headers:
        client_betas = [beta.strip() for beta in client_beta_headers.split(",")]
        # Combine and deduplicate
        all_betas = list(dict.fromkeys(required_betas + client_betas))
    else:
        all_betas = required_betas

    beta_header_value = ",".join(all_betas)

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=30.0)) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages?beta=true",
            json=anthropic_request,
            headers={
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
                "anthropic-version": "2023-06-01",
                "authorization": f"Bearer {access_token}",
                "x-app": "cli",
                "User-Agent": "claude-cli/1.0.113 (external, cli)",
                "content-type": "application/json",
                "anthropic-beta": beta_header_value,
                "x-stainless-helper-method": "stream",
                "accept-language": "*",
                "sec-fetch-mode": "cors"
            }
        )
        return response


async def stream_anthropic_response(request_id: str, anthropic_request: Dict[str, Any], access_token: str, client_beta_headers: Optional[str] = None) -> AsyncIterator[str]:
    """Stream response from Anthropic API"""
    # Required beta headers for authentication flow
    required_betas = ["claude-code-20250219", "oauth-2025-04-20", "fine-grained-tool-streaming-2025-05-14"]

    # Merge client beta headers if provided
    if client_beta_headers:
        client_betas = [beta.strip() for beta in client_beta_headers.split(",")]
        # Combine and deduplicate
        all_betas = list(dict.fromkeys(required_betas + client_betas))
    else:
        all_betas = required_betas

    beta_header_value = ",".join(all_betas)

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=30.0)) as client:
        async with client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages?beta=true",
            json=anthropic_request,
            headers={
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
                "anthropic-version": "2023-06-01",
                "authorization": f"Bearer {access_token}",
                "x-app": "cli",
                "User-Agent": "claude-cli/1.0.113 (external, cli)",
                "content-type": "application/json",
                "anthropic-beta": beta_header_value,
                "x-stainless-helper-method": "stream",
                "accept-language": "*",
                "sec-fetch-mode": "cors"
            }
        ) as response:
            if response.status_code != 200:
                # For error responses, stream them back as SSE events
                error_text = await response.aread()
                error_json = error_text.decode()
                logger.error(f"[{request_id}] Anthropic API error {response.status_code}: {error_json}")

                # Format error as SSE event for proper client handling
                error_event = f"event: error\ndata: {error_json}\n\n"
                yield error_event
                return

            # Stream successful response chunks
            try:
                async for chunk in response.aiter_text():
                    yield chunk
            except httpx.ReadTimeout:
                error_event = f"event: error\ndata: {{\"error\": \"Stream timeout after {REQUEST_TIMEOUT}s\"}}\n\n"
                yield error_event
            except httpx.RemoteProtocolError as e:
                error_event = f"event: error\ndata: {{\"error\": \"Connection closed: {str(e)}\"}}\n\n"
                yield error_event


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

    # Extract client beta headers
    client_beta_headers = headers_dict.get("anthropic-beta")

    # Log the final beta headers that will be sent
    required_betas = ["claude-code-20250219", "oauth-2025-04-20", "fine-grained-tool-streaming-2025-05-14"]
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
            return StreamingResponse(
                stream_anthropic_response(request_id, anthropic_request, access_token, client_beta_headers),
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

        # Get root logger and configure it for debug
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create file handler for debug log
        log_file = os.path.abspath('proxy_debug.log')
        file_handler = logging.FileHandler(log_file, mode='w')  # 'w' to overwrite each time
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

        logger.info(f"Debug logging enabled - writing to {log_file}")

    def run(self):
        """Run the proxy server (blocking)"""
        logger.info(f"Starting Anthropic Claude Max Proxy on http://{self.bind_address}:{PORT}")
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

    uvicorn.run(
        app,
        host=BIND_ADDRESS,
        port=PORT,
        log_level=LOG_LEVEL
    )