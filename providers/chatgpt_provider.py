"""
ChatGPT provider implementation for Responses API.
Handles requests to ChatGPT Plus/Pro subscription models via OAuth.
"""
import json
import logging
import time
from typing import Dict, Any, Optional, AsyncIterator, TYPE_CHECKING

import httpx

from settings import (
    CHATGPT_API_ENDPOINT,
    CHATGPT_DEFAULT_REASONING_EFFORT,
    CHATGPT_DEFAULT_REASONING_SUMMARY,
    STREAM_TIMEOUT,
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    REQUEST_TIMEOUT,
)
from providers.base_provider import BaseProvider
from chatgpt_oauth import (
    ChatGPTOAuthManager,
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
)
from chatgpt_oauth.session import ensure_session_id
from models import get_chatgpt_default_instructions, get_openai_model_id

if TYPE_CHECKING:
    from stream_debug import StreamTracer

logger = logging.getLogger(__name__)


class ChatGPTProvider(BaseProvider):
    """Provider implementation for ChatGPT Responses API"""

    def __init__(self, oauth_manager: Optional[ChatGPTOAuthManager] = None):
        """Initialize ChatGPT provider

        Args:
            oauth_manager: OAuth manager for token management (creates new if None)
        """
        # Don't call super().__init__ as we don't use base_url/api_key pattern
        self.oauth_manager = oauth_manager or ChatGPTOAuthManager()
        self.endpoint = CHATGPT_API_ENDPOINT

    def _get_headers(
        self,
        access_token: str,
        account_id: str,
        session_id: str,
        accept: str = "text/event-stream"
    ) -> Dict[str, str]:
        """Build request headers for Responses API

        Args:
            access_token: OAuth access token
            account_id: ChatGPT account ID
            session_id: Session ID for prompt caching
            accept: Accept header value

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": accept,
            "chatgpt-account-id": account_id,
            "OpenAI-Beta": "responses=experimental",
            "session_id": session_id,
        }

    def _build_responses_payload(
        self,
        request_data: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """Build Responses API payload from OpenAI format request

        Args:
            request_data: OpenAI format request data
            session_id: Session ID for prompt caching

        Returns:
            Responses API format payload
        """
        # Extract OpenAI parameters
        model = request_data.get("model", "gpt5")
        messages = request_data.get("messages", [])
        tools = request_data.get("tools")
        tool_choice = request_data.get("tool_choice", "auto")
        parallel_tool_calls = request_data.get("parallel_tool_calls", False)

        # Always use default instructions for the model (matching ChatMock behavior)
        # User system messages are handled by convert_chat_messages_to_responses_input
        instructions = get_chatgpt_default_instructions(model)

        # Convert messages to Responses API format
        input_items = convert_chat_messages_to_responses_input(messages)

        # Convert tools to Responses API format
        responses_tools = convert_tools_chat_to_responses(tools) if tools else []

        # Handle reasoning parameters
        reasoning_param = None
        reasoning_effort = request_data.get("reasoning_effort")
        reasoning_summary = request_data.get("reasoning_summary")

        # Get the actual OpenAI model ID to send to the API
        openai_model = get_openai_model_id(model)

        # Extract reasoning effort from OpenAI model ID if present (e.g., gpt-5-high)
        model_lower = openai_model.lower()
        for effort in ["minimal", "low", "medium", "high"]:
            if model_lower.endswith(f"-{effort}"):
                reasoning_effort = reasoning_effort or effort
                # Remove effort suffix from model name for API call
                openai_model = openai_model[:-len(f"-{effort}")]
                break

        # Build reasoning parameter if needed (matching ChatMock format)
        # ChatMock format: {"effort": "medium", "summary": "auto"}
        # NOT: {"type": "enabled", "effort": "medium", "summary": "auto"}
        if reasoning_effort or reasoning_summary:
            effort = reasoning_effort or CHATGPT_DEFAULT_REASONING_EFFORT
            summary = reasoning_summary or CHATGPT_DEFAULT_REASONING_SUMMARY

            # Validate effort
            if effort not in ["minimal", "low", "medium", "high"]:
                effort = "medium"

            # Validate summary
            if summary not in ["auto", "concise", "detailed", "none"]:
                summary = "auto"

            reasoning_param = {"effort": effort}
            if summary != "none":
                reasoning_param["summary"] = summary

        # Build Responses API payload
        # Instructions should be None or a non-empty string (matching ChatMock's logic)
        payload = {
            "model": openai_model,
            "input": input_items,
            "tools": responses_tools,
            "tool_choice": tool_choice if tool_choice in ("auto", "none") else "auto",
            "parallel_tool_calls": bool(parallel_tool_calls),
            "store": False,
            "stream": True,
            "prompt_cache_key": session_id,
        }

        # Only include instructions if we have a non-empty string
        if isinstance(instructions, str) and instructions.strip():
            payload["instructions"] = instructions

        if reasoning_param:
            payload["reasoning"] = reasoning_param
            payload["include"] = ["reasoning.encrypted_content"]

        return payload

    async def make_request(
        self,
        request_data: Dict[str, Any],
        request_id: str
    ) -> httpx.Response:
        """Make a non-streaming request to ChatGPT Responses API

        Args:
            request_data: The OpenAI-format request body
            request_id: Request ID for logging

        Returns:
            The HTTP response from ChatGPT
        """
        # Get valid OAuth credentials
        access_token, account_id = await self.oauth_manager.get_auth_credentials_async()
        if not access_token or not account_id:
            raise ValueError("No valid ChatGPT OAuth credentials available")

        # Generate session ID for prompt caching
        messages = request_data.get("messages", [])
        instructions = None
        for msg in messages:
            if msg.get("role") == "system":
                instructions = msg.get("content", "")
                break

        input_items = convert_chat_messages_to_responses_input(messages)
        session_id = ensure_session_id(instructions, input_items)

        # Build Responses API payload
        payload = self._build_responses_payload(request_data, session_id)
        payload["stream"] = False  # Non-streaming

        headers = self._get_headers(access_token, account_id, session_id, accept="application/json")

        logger.debug(f"[{request_id}] Making ChatGPT request to {self.endpoint}")
        logger.debug(f"[{request_id}] Request payload: {json.dumps(payload, indent=2)}")

        async with httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=headers
            )

            logger.debug(f"[{request_id}] ChatGPT response status: {response.status_code}")
            return response

    async def stream_response(
        self,
        request_data: Dict[str, Any],
        request_id: str,
        tracer: Optional["StreamTracer"] = None,
    ) -> AsyncIterator[str]:
        """Stream response from ChatGPT Responses API

        Translates Responses API SSE format to OpenAI SSE format.

        Args:
            request_data: The OpenAI-format request body
            request_id: Request ID for logging
            tracer: Optional stream tracer for debugging

        Yields:
            SSE chunks in OpenAI format
        """
        # Get valid OAuth credentials
        access_token, account_id = await self.oauth_manager.get_auth_credentials_async()
        if not access_token or not account_id:
            error_event = 'data: {"error": {"message": "No valid ChatGPT OAuth credentials available"}}\n\n'
            if tracer:
                tracer.log_error("No valid ChatGPT OAuth credentials")
            yield error_event
            return

        # Generate session ID for prompt caching
        messages = request_data.get("messages", [])
        instructions = None
        for msg in messages:
            if msg.get("role") == "system":
                instructions = msg.get("content", "")
                break

        input_items = convert_chat_messages_to_responses_input(messages)
        session_id = ensure_session_id(instructions, input_items)

        # Build Responses API payload
        payload = self._build_responses_payload(request_data, session_id)

        headers = self._get_headers(access_token, account_id, session_id)

        if tracer:
            tracer.log_note(f"starting ChatGPT stream to {self.endpoint}")
            tracer.log_note(f"model={payload.get('model')}")

        logger.debug(f"[{request_id}] Streaming from ChatGPT: {self.endpoint}")
        logger.debug(f"[{request_id}] Request payload: {json.dumps(payload, indent=2)}")

        async with httpx.AsyncClient(timeout=httpx.Timeout(STREAM_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)) as client:
            try:
                async with client.stream(
                    "POST",
                    self.endpoint,
                    json=payload,
                    headers=headers
                ) as response:
                    if tracer:
                        tracer.log_note(f"ChatGPT responded with status={response.status_code}")

                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_json = error_text.decode()
                        logger.error(f"[{request_id}] ChatGPT error {response.status_code}: {error_json}")
                        if tracer:
                            tracer.log_error(f"ChatGPT error status={response.status_code} body={error_json}")

                        error_event = f'data: {{"error": {{"message": "ChatGPT API error: {response.status_code}"}}}}\n\n'
                        if tracer:
                            tracer.log_note("yielding synthetic error SSE event")
                        yield error_event
                        return

                    # Stream and translate Responses API → OpenAI format
                    chunk_index = 0
                    created = int(time.time())
                    model = request_data.get("model", "gpt-5")
                    response_id = f"chatcmpl-{request_id}"

                    async for line in response.aiter_lines():
                        chunk_index += 1

                        if not line or not line.startswith("data: "):
                            continue

                        data = line[6:].strip()  # Remove "data: " prefix

                        if not data or data == "[DONE]":
                            if data == "[DONE]":
                                if tracer:
                                    tracer.log_note("received [DONE] from ChatGPT")
                                yield "data: [DONE]\n\n"
                            continue

                        try:
                            evt = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        if tracer:
                            tracer.log_note(f"received ChatGPT chunk #{chunk_index}: {evt.get('type')}")
                            tracer.log_source_chunk(line)

                        # Translate Responses API events to OpenAI format
                        openai_chunk = self._translate_response_event(evt, response_id, created, model)

                        if openai_chunk:
                            chunk_str = f"data: {json.dumps(openai_chunk)}\n\n"
                            if tracer:
                                tracer.log_converted_chunk(chunk_str)
                            yield chunk_str

            except httpx.ReadTimeout:
                error_event = f'data: {{"error": {{"message": "Stream timeout after {STREAM_TIMEOUT}s"}}}}\n\n'
                if tracer:
                    tracer.log_error(f"ChatGPT stream timeout after {STREAM_TIMEOUT}s")
                yield error_event

            except httpx.RemoteProtocolError as e:
                error_event = f'data: {{"error": {{"message": "Connection closed: {str(e)}"}}}}\n\n'
                if tracer:
                    tracer.log_error(f"ChatGPT stream closed unexpectedly: {str(e)}")
                yield error_event

            finally:
                if tracer:
                    tracer.log_note("ChatGPT stream closed")

    def _translate_response_event(
        self,
        evt: Dict[str, Any],
        response_id: str,
        created: int,
        model: str
    ) -> Optional[Dict[str, Any]]:
        """Translate Responses API event to OpenAI format

        Args:
            evt: Responses API event
            response_id: Response ID for OpenAI format
            created: Creation timestamp
            model: Model name

        Returns:
            OpenAI format chunk, or None if event should be skipped
        """
        kind = evt.get("type")

        # Handle text deltas
        if kind == "response.output_text.delta":
            delta = evt.get("delta", "")
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": delta},
                    "finish_reason": None
                }]
            }

        # Handle reasoning/thinking deltas
        elif kind in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
            delta = evt.get("delta", "")
            # Use <think> tags for compatibility
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": delta},
                    "finish_reason": None
                }]
            }

        # Handle tool calls
        elif kind == "response.output_item.done":
            item = evt.get("item", {})
            if item.get("type") == "function_call":
                call_id = item.get("call_id", "")
                name = item.get("name", "")
                args = item.get("arguments", "")

                if isinstance(args, dict):
                    args = json.dumps(args)

                return {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_calls": [{
                                "index": 0,
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": args}
                            }]
                        },
                        "finish_reason": None
                    }]
                }

        # Handle completion
        elif kind == "response.completed":
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }

        # Handle errors
        elif kind == "response.failed":
            error_msg = evt.get("response", {}).get("error", {}).get("message", "Unknown error")
            return {
                "error": {"message": error_msg}
            }

        return None
