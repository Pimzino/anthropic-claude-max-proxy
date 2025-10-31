"""
Custom provider integration for non-Anthropic models.
Provides a unified interface for OpenAI-compatible API endpoints.

Public API maintains backward compatibility with function-based interface.
"""
from typing import Dict, Any, Optional, AsyncIterator, TYPE_CHECKING

from providers.openai_provider import OpenAIProvider

if TYPE_CHECKING:
    from stream_debug import StreamTracer

# Public API exports - maintain backward compatibility
__all__ = [
    'make_custom_provider_request',
    'stream_custom_provider_response',
]


async def make_custom_provider_request(
    request_data: Dict[str, Any],
    base_url: str,
    api_key: str,
    request_id: str
):
    """Make a non-streaming request to a custom OpenAI-compatible provider

    Args:
        request_data: The OpenAI-format request body
        base_url: The provider's base URL (e.g., https://api.z.ai/api/coding/paas/v4)
        api_key: The API key for authentication
        request_id: Request ID for logging

    Returns:
        The HTTP response from the provider
    """
    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return await provider.make_request(request_data, request_id)


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
    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    async for chunk in provider.stream_response(request_data, request_id, tracer):
        yield chunk
