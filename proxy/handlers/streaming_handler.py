"""
Streaming response handlers for Anthropic and OpenAI formats.
"""
import logging
from typing import Dict, Any, Optional, AsyncIterator

from anthropic import stream_anthropic_response
from openai_compat import convert_anthropic_stream_to_openai
from stream_debug import StreamTracer

logger = logging.getLogger(__name__)


async def create_anthropic_stream(
    request_id: str,
    anthropic_request: Dict[str, Any],
    access_token: str,
    client_beta_headers: Optional[str],
    tracer: Optional[StreamTracer] = None,
) -> AsyncIterator[bytes]:
    """
    Create a streaming response in Anthropic format.

    Args:
        request_id: Request ID for logging
        anthropic_request: Prepared Anthropic request
        access_token: OAuth access token
        client_beta_headers: Beta feature headers from client
        tracer: Optional stream tracer for debugging

    Yields:
        Raw SSE chunks in bytes
    """
    async for chunk in stream_anthropic_response(
        request_id,
        anthropic_request,
        access_token,
        client_beta_headers,
        tracer=tracer,
    ):
        yield chunk


async def create_openai_stream(
    request_id: str,
    anthropic_request: Dict[str, Any],
    access_token: str,
    client_beta_headers: Optional[str],
    model: str,
    tracer: Optional[StreamTracer] = None,
) -> AsyncIterator[bytes]:
    """
    Create a streaming response in OpenAI format.

    Args:
        request_id: Request ID for logging
        anthropic_request: Prepared Anthropic request
        access_token: OAuth access token
        client_beta_headers: Beta feature headers from client
        model: Model name for OpenAI response
        tracer: Optional stream tracer for debugging

    Yields:
        SSE chunks in OpenAI format
    """
    # Get Anthropic stream
    anthropic_stream = stream_anthropic_response(
        request_id,
        anthropic_request,
        access_token,
        client_beta_headers,
        tracer=tracer,
    )

    # Convert to OpenAI format
    async for chunk in convert_anthropic_stream_to_openai(
        anthropic_stream,
        model,
        request_id,
        tracer=tracer,
    ):
        yield chunk
