"""
Custom provider request and streaming handlers.
"""
import logging
from typing import Dict, Any, Optional, AsyncIterator

from providers import (
    make_custom_provider_request,
    stream_custom_provider_response,
)
from stream_debug import StreamTracer

logger = logging.getLogger(__name__)


async def handle_custom_provider_request(
    openai_request: Dict[str, Any],
    base_url: str,
    api_key: str,
    request_id: str,
):
    """
    Handle a non-streaming request to a custom provider.

    Args:
        openai_request: OpenAI-format request
        base_url: Custom provider base URL
        api_key: Custom provider API key
        request_id: Request ID for logging

    Returns:
        HTTP response from custom provider
    """
    return await make_custom_provider_request(
        openai_request,
        base_url,
        api_key,
        request_id
    )


async def handle_custom_provider_stream(
    openai_request: Dict[str, Any],
    base_url: str,
    api_key: str,
    request_id: str,
    tracer: Optional[StreamTracer] = None,
) -> AsyncIterator[bytes]:
    """
    Handle a streaming request to a custom provider.

    Args:
        openai_request: OpenAI-format request
        base_url: Custom provider base URL
        api_key: Custom provider API key
        request_id: Request ID for logging
        tracer: Optional stream tracer for debugging

    Yields:
        SSE chunks from custom provider
    """
    async for chunk in stream_custom_provider_response(
        openai_request,
        base_url,
        api_key,
        request_id,
        tracer=tracer,
    ):
        yield chunk
