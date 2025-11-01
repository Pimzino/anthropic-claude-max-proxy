"""Integration tests for streaming responses in proxy endpoints"""
import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest


@pytest.mark.integration
class TestAnthropicMessagesStreaming:
    """Test suite for /v1/messages endpoint streaming"""

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_streaming_response_basic(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client
    ):
        """Test basic streaming response from /v1/messages"""
        # Mock OAuth manager
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock SSE streaming response
        async def mock_stream_iter():
            events = [
                b'event: message_start\n',
                b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":0}\n\n',
                b'event: message_delta\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
                b'event: message_stop\n',
                b'data: {"type":"message_stop"}\n\n',
            ]
            for event in events:
                yield event

        # Create mock response with streaming
        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        # Make streaming request
        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )

        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

        # Read streaming response
        chunks = list(response.iter_bytes())
        assert len(chunks) > 0

        # Verify we got SSE formatted data
        content = b''.join(chunks)
        assert b'event: message_start' in content
        assert b'event: content_block_delta' in content
        assert b'event: message_stop' in content

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_streaming_with_thinking(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client
    ):
        """Test streaming response with thinking blocks"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock SSE streaming response with thinking
        async def mock_stream_iter():
            events = [
                b'event: message_start\n',
                b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"Let me think..."}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":0}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":1,"content_block":{"type":"text","text":""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"The answer is 42"}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":1}\n\n',
                b'event: message_delta\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":50}}\n\n',
                b'event: message_stop\n',
                b'data: {"type":"message_stop"}\n\n',
            ]
            for event in events:
                yield event

        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": "Think about this"}],
                "thinking": {"type": "enabled", "budget_tokens": 10000},
                "stream": True
            }
        )

        assert response.status_code == 200

        content = b''.join(response.iter_bytes())
        assert b'"type":"thinking"' in content
        assert b'"type":"text"' in content

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_streaming_unauthorized(self, mock_manager, fastapi_test_client):
        """Test streaming request without auth"""
        mock_manager.get_valid_token_async = AsyncMock(return_value=None)
        mock_manager.is_authenticated.return_value = False

        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )

        assert response.status_code == 401

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_streaming_with_tools(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client
    ):
        """Test streaming response with tool use"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        async def mock_stream_iter():
            events = [
                b'event: message_start\n',
                b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_1","name":"get_weather"}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"location\\""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":":\\"SF\\"}"}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":0}\n\n',
                b'event: message_delta\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":20}}\n\n',
                b'event: message_stop\n',
                b'data: {"type":"message_stop"}\n\n',
            ]
            for event in events:
                yield event

        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": "Get weather"}],
                "tools": [
                    {
                        "name": "get_weather",
                        "description": "Get weather",
                        "input_schema": {"type": "object", "properties": {}}
                    }
                ],
                "stream": True
            }
        )

        assert response.status_code == 200
        content = b''.join(response.iter_bytes())
        assert b'"type":"tool_use"' in content


@pytest.mark.integration
class TestOpenAIChatStreaming:
    """Test suite for /v1/chat/completions endpoint streaming"""

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_streaming_response_basic(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client
    ):
        """Test basic streaming response from /v1/chat/completions"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Mock Anthropic streaming response
        async def mock_stream_iter():
            events = [
                b'event: message_start\n',
                b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":0}\n\n',
                b'event: message_delta\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
                b'event: message_stop\n',
                b'data: {"type":"message_stop"}\n\n',
            ]
            for event in events:
                yield event

        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1000,
                "stream": True
            }
        )

        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

        # Read streaming response (should be in OpenAI format)
        chunks = list(response.iter_bytes())
        assert len(chunks) > 0

        # Verify we got OpenAI SSE formatted data
        content = b''.join(chunks)
        # OpenAI format uses "data: " prefix
        assert b'data: ' in content
        # Should contain choices and delta
        assert b'"choices"' in content or b'[DONE]' in content

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_streaming_with_reasoning(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client
    ):
        """Test streaming with reasoning_effort parameter"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        async def mock_stream_iter():
            events = [
                b'event: message_start\n',
                b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"Analyzing..."}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":0}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":1,"content_block":{"type":"text","text":""}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"Answer"}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":1}\n\n',
                b'event: message_delta\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":50}}\n\n',
                b'event: message_stop\n',
                b'data: {"type":"message_stop"}\n\n',
            ]
            for event in events:
                yield event

        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Think"}],
                "max_tokens": 4000,
                "reasoning_effort": "high",
                "stream": True
            }
        )

        assert response.status_code == 200
        content = b''.join(response.iter_bytes())
        # Should have reasoning_content in OpenAI format
        assert b'data: ' in content

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_streaming_with_tools(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client
    ):
        """Test streaming with tool calls"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        async def mock_stream_iter():
            events = [
                b'event: message_start\n',
                b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
                b'event: content_block_start\n',
                b'data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_1","name":"calc"}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"x\\":5"}}\n\n',
                b'event: content_block_delta\n',
                b'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"}"}}\n\n',
                b'event: content_block_stop\n',
                b'data: {"type":"content_block_stop","index":0}\n\n',
                b'event: message_delta\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":10}}\n\n',
                b'event: message_stop\n',
                b'data: {"type":"message_stop"}\n\n',
            ]
            for event in events:
                yield event

        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Calculate"}],
                "max_tokens": 1000,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "calc",
                            "description": "Calculate",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    }
                ],
                "stream": True
            }
        )

        assert response.status_code == 200
        content = b''.join(response.iter_bytes())
        assert b'data: ' in content

    @patch('httpx.AsyncClient')
    @patch('models.custom_models.is_custom_model')
    @patch('models.custom_models.get_custom_model_config')
    async def test_streaming_custom_provider(
        self,
        mock_get_config,
        mock_is_custom,
        mock_httpx,
        fastapi_test_client
    ):
        """Test streaming with custom provider"""
        # Mark as custom model
        mock_is_custom.return_value = True
        mock_get_config.return_value = {
            "id": "custom-model",
            "base_url": "https://api.custom.com/v1",
            "api_key": "custom-key",
            "context_length": 100000
        }

        # Mock custom provider streaming response
        async def mock_stream_iter():
            events = [
                b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234,"model":"custom-model","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234,"model":"custom-model","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234,"model":"custom-model","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}\n\n',
                b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234,"model":"custom-model","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
                b'data: [DONE]\n\n',
            ]
            for event in events:
                yield event

        mock_response = MagicMock()
        mock_response.aiter_bytes = mock_stream_iter
        mock_response.status_code = 200

        mock_client_instance = MagicMock()
        mock_client_instance.stream = MagicMock()
        mock_client_instance.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_client_instance.stream.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "custom-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1000,
                "stream": True
            }
        )

        assert response.status_code == 200
        content = b''.join(response.iter_bytes())
        assert b'data: ' in content
        assert b'[DONE]' in content

    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_streaming_unauthorized(self, mock_manager, fastapi_test_client):
        """Test streaming request without auth"""
        mock_manager.get_valid_token_async = AsyncMock(return_value=None)
        mock_manager.is_authenticated.return_value = False

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1000,
                "stream": True
            }
        )

        assert response.status_code == 401
