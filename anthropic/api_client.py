"""Anthropic API HTTP client for making requests"""

import logging
from typing import Dict, Any, Optional, AsyncIterator, TYPE_CHECKING

import httpx

from headers import USER_AGENT, X_APP_HEADER, STAINLESS_HEADERS
from settings import REQUEST_TIMEOUT, STREAM_TIMEOUT, CONNECT_TIMEOUT, READ_TIMEOUT
from .system_message import inject_claude_code_system_message
from .beta_headers import build_beta_headers

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stream_debug import StreamTracer


async def make_anthropic_request(
    anthropic_request: Dict[str, Any],
    access_token: str,
    client_beta_headers: Optional[str] = None
) -> httpx.Response:
    """Make a non-streaming request to Anthropic API

    Args:
        anthropic_request: The Anthropic API request data
        access_token: OAuth Bearer access token
        client_beta_headers: Optional client-provided beta headers

    Returns:
        HTTP response from Anthropic API
    """
    # Inject system message if not present
    if not anthropic_request.get("system"):
        anthropic_request = inject_claude_code_system_message(anthropic_request)

    # Build beta headers based on request features
    beta_header_value = build_beta_headers(
        anthropic_request,
        client_beta_headers=client_beta_headers,
        for_streaming=False
    )

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
    """Stream response from Anthropic API

    Args:
        request_id: Unique request identifier for logging
        anthropic_request: The Anthropic API request data
        access_token: OAuth Bearer access token
        client_beta_headers: Optional client-provided beta headers
        tracer: Optional stream tracer for debugging

    Yields:
        SSE event strings from the Anthropic API
    """
    # Inject system message if not present
    if not anthropic_request.get("system"):
        anthropic_request = inject_claude_code_system_message(anthropic_request)

    # Build beta headers based on request features
    beta_header_value = build_beta_headers(
        anthropic_request,
        client_beta_headers=client_beta_headers,
        request_id=request_id,
        for_streaming=True
    )

    # Remove internal metadata field before sending to API
    use_1m_context = anthropic_request.pop("_use_1m_context", False)

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
