"""
Custom provider integration layer.
Handles requests to custom OpenAI-compatible API endpoints (e.g., Z.AI, OpenRouter, etc.)
"""
import logging
from typing import Dict, Any, AsyncIterator, Optional, TYPE_CHECKING
import httpx

from settings import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stream_debug import StreamTracer


async def make_custom_provider_request(
    request_data: Dict[str, Any],
    base_url: str,
    api_key: str,
    request_id: str
) -> httpx.Response:
    """Make a non-streaming request to a custom OpenAI-compatible provider

    Args:
        request_data: The OpenAI-format request body
        base_url: The provider's base URL (e.g., https://api.z.ai/api/coding/paas/v4)
        api_key: The API key for authentication
        request_id: Request ID for logging

    Returns:
        The HTTP response from the provider
    """
    # Ensure the base_url ends with the correct path
    # Most OpenAI-compatible APIs use /chat/completions
    if not base_url.endswith('/chat/completions'):
        if base_url.endswith('/'):
            endpoint = f"{base_url}chat/completions"
        else:
            endpoint = f"{base_url}/chat/completions"
    else:
        endpoint = base_url

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    logger.debug(f"[{request_id}] Making custom provider request to {endpoint}")
    logger.debug(f"[{request_id}] Request body: {request_data}")

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=30.0)) as client:
        response = await client.post(
            endpoint,
            json=request_data,
            headers=headers
        )

        logger.debug(f"[{request_id}] Custom provider response status: {response.status_code}")
        return response


async def stream_custom_provider_response(
    request_data: Dict[str, Any],
    base_url: str,
    api_key: str,
    request_id: str,
    tracer: Optional["StreamTracer"] = None,
) -> AsyncIterator[str]:
    """Stream response from a custom OpenAI-compatible provider

    Args:
        request_data: The OpenAI-format request body
        base_url: The provider's base URL
        api_key: The API key for authentication
        request_id: Request ID for logging
        tracer: Optional stream tracer for debugging

    Yields:
        SSE chunks from the provider
    """
    # Ensure the base_url ends with the correct path
    if not base_url.endswith('/chat/completions'):
        if base_url.endswith('/'):
            endpoint = f"{base_url}chat/completions"
        else:
            endpoint = f"{base_url}/chat/completions"
    else:
        endpoint = base_url

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    if tracer:
        tracer.log_note(f"starting custom provider stream to {endpoint}")
        tracer.log_note(f"model={request_data.get('model')}")

    logger.debug(f"[{request_id}] Streaming from custom provider: {endpoint}")
    logger.debug(f"[{request_id}] Request body: {request_data}")

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=30.0)) as client:
        async with client.stream(
            "POST",
            endpoint,
            json=request_data,
            headers=headers
        ) as response:
            if tracer:
                tracer.log_note(f"custom provider responded with status={response.status_code}")

            if response.status_code != 200:
                # For error responses, stream them back as SSE events
                error_text = await response.aread()
                error_json = error_text.decode()
                logger.error(f"[{request_id}] Custom provider error {response.status_code}: {error_json}")

                if tracer:
                    tracer.log_error(f"custom provider error status={response.status_code} body={error_json}")

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
                        tracer.log_note(f"received custom provider chunk #{chunk_index}")
                        tracer.log_source_chunk(chunk)
                    yield chunk
            except httpx.ReadTimeout:
                error_event = f"event: error\ndata: {{\"error\": \"Stream timeout after {REQUEST_TIMEOUT}s\"}}\n\n"
                if tracer:
                    tracer.log_error(f"custom provider stream timeout after {REQUEST_TIMEOUT}s")
                    tracer.log_note("yielding timeout SSE event")
                yield error_event
            except httpx.RemoteProtocolError as e:
                error_event = f"event: error\ndata: {{\"error\": \"Connection closed: {str(e)}\"}}\n\n"
                if tracer:
                    tracer.log_error(f"custom provider stream closed unexpectedly: {str(e)}")
                    tracer.log_note("yielding remote protocol error SSE event")
                yield error_event
            finally:
                if tracer:
                    tracer.log_note("custom provider stream closed")
