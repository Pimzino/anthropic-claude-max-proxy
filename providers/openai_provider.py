"""
OpenAI-compatible provider implementation.
Handles requests to OpenAI API format endpoints.
"""
import logging
from typing import Dict, Any, Optional, AsyncIterator
import httpx

from settings import REQUEST_TIMEOUT, STREAM_TIMEOUT, CONNECT_TIMEOUT, READ_TIMEOUT
from providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """Provider implementation for OpenAI-compatible APIs"""

    def _get_endpoint(self) -> str:
        """Build the chat completions endpoint URL"""
        base_url = self.base_url
        if not base_url.endswith('/chat/completions'):
            if base_url.endswith('/'):
                endpoint = f"{base_url}chat/completions"
            else:
                endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = base_url
        return endpoint

    def _get_headers(self, accept: str = "application/json") -> Dict[str, str]:
        """Build request headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": accept,
        }

    async def make_request(
        self,
        request_data: Dict[str, Any],
        request_id: str
    ) -> httpx.Response:
        """Make a non-streaming request to an OpenAI-compatible provider

        Args:
            request_data: The OpenAI-format request body
            request_id: Request ID for logging

        Returns:
            The HTTP response from the provider
        """
        endpoint = self._get_endpoint()
        headers = self._get_headers()

        logger.debug(f"[{request_id}] Making custom provider request to {endpoint}")
        logger.debug(f"[{request_id}] Request body: {request_data}")

        # Use REQUEST_TIMEOUT for non-streaming with industry-standard CONNECT_TIMEOUT
        async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)) as client:
            response = await client.post(
                endpoint,
                json=request_data,
                headers=headers
            )

            logger.debug(f"[{request_id}] Custom provider response status: {response.status_code}")
            return response

    async def stream_response(
        self,
        request_data: Dict[str, Any],
        request_id: str,
        tracer: Optional["StreamTracer"] = None,
    ) -> AsyncIterator[str]:
        """Stream response from an OpenAI-compatible provider

        Args:
            request_data: The OpenAI-format request body
            request_id: Request ID for logging
            tracer: Optional stream tracer for debugging

        Yields:
            SSE chunks from the provider
        """
        endpoint = self._get_endpoint()
        headers = self._get_headers(accept="text/event-stream")

        if tracer:
            tracer.log_note(f"starting custom provider stream to {endpoint}")
            tracer.log_note(f"model={request_data.get('model')}")

        logger.debug(f"[{request_id}] Streaming from custom provider: {endpoint}")
        logger.debug(f"[{request_id}] Request body: {request_data}")

        # Use STREAM_TIMEOUT for streaming requests with READ_TIMEOUT between chunks
        async with httpx.AsyncClient(timeout=httpx.Timeout(STREAM_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)) as client:
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
                    error_event = f"event: error\ndata: {{\"error\": \"Stream timeout after {STREAM_TIMEOUT}s\"}}\n\n"
                    if tracer:
                        tracer.log_error(f"custom provider stream timeout after {STREAM_TIMEOUT}s")
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
