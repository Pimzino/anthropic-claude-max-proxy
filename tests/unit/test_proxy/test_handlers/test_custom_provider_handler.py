"""Unit tests for proxy.handlers.custom_provider_handler"""
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from proxy.handlers.custom_provider_handler import (
    handle_custom_provider_request,
    handle_custom_provider_stream
)


@pytest.mark.unit
class TestHandleCustomProviderRequest:
    """Test suite for handle_custom_provider_request function"""

    @patch('proxy.handlers.custom_provider_handler.make_custom_provider_request')
    async def test_calls_make_custom_provider_request(self, mock_make_request):
        """Test that handle_custom_provider_request delegates to provider module"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [{"message": {"content": "Hello"}}]
        }
        mock_make_request.return_value = mock_response

        openai_request = {
            "model": "custom-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        result = await handle_custom_provider_request(
            openai_request=openai_request,
            base_url="https://api.custom.com/v1",
            api_key="test-key",
            request_id="test-123"
        )

        # Verify provider function was called with correct args
        mock_make_request.assert_called_once_with(
            openai_request,
            "https://api.custom.com/v1",
            "test-key",
            "test-123"
        )

        # Verify response is returned
        assert result == mock_response
        assert result.status_code == 200

    @patch('proxy.handlers.custom_provider_handler.make_custom_provider_request')
    async def test_passes_all_parameters(self, mock_make_request):
        """Test that all parameters are correctly passed"""
        mock_response = MagicMock()
        mock_make_request.return_value = mock_response

        openai_request = {
            "model": "custom-model",
            "messages": [{"role": "user", "content": "Test"}],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 500
        }

        await handle_custom_provider_request(
            openai_request=openai_request,
            base_url="https://api.example.com/v1",
            api_key="sk-custom-key-123",
            request_id="req-456"
        )

        # Verify all args were passed correctly
        call_args = mock_make_request.call_args
        assert call_args[0][0] == openai_request
        assert call_args[0][1] == "https://api.example.com/v1"
        assert call_args[0][2] == "sk-custom-key-123"
        assert call_args[0][3] == "req-456"

    @patch('proxy.handlers.custom_provider_handler.make_custom_provider_request')
    async def test_handles_error_response(self, mock_make_request):
        """Test handling of error response from custom provider"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"message": "Invalid request"}
        }
        mock_make_request.return_value = mock_response

        result = await handle_custom_provider_request(
            openai_request={},
            base_url="https://api.custom.com/v1",
            api_key="test-key",
            request_id="test-123"
        )

        # Should still return the response (error handling is in endpoint)
        assert result.status_code == 400


@pytest.mark.unit
class TestHandleCustomProviderStream:
    """Test suite for handle_custom_provider_stream function"""

    @patch('proxy.handlers.custom_provider_handler.stream_custom_provider_response')
    async def test_calls_stream_custom_provider_response(self, mock_stream):
        """Test that handle_custom_provider_stream delegates to provider module"""
        # Setup mock async generator
        async def mock_gen():
            yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            yield b'data: [DONE]\n\n'

        mock_stream.return_value = mock_gen()

        openai_request = {
            "model": "custom-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "stream": True
        }

        # Call handle_custom_provider_stream
        chunks = []
        async for chunk in handle_custom_provider_stream(
            openai_request=openai_request,
            base_url="https://api.custom.com/v1",
            api_key="test-key",
            request_id="test-123",
            tracer=None
        ):
            chunks.append(chunk)

        # Verify stream function was called
        mock_stream.assert_called_once_with(
            openai_request,
            "https://api.custom.com/v1",
            "test-key",
            "test-123",
            tracer=None
        )

        # Verify chunks were yielded
        assert len(chunks) == 2
        assert b'Hello' in chunks[0]
        assert b'[DONE]' in chunks[1]

    @patch('proxy.handlers.custom_provider_handler.stream_custom_provider_response')
    async def test_passes_tracer(self, mock_stream):
        """Test that tracer is passed to stream function"""
        async def mock_gen():
            yield b'data: test\n\n'

        mock_stream.return_value = mock_gen()

        mock_tracer = MagicMock()

        async for _ in handle_custom_provider_stream(
            openai_request={},
            base_url="https://api.custom.com/v1",
            api_key="test-key",
            request_id="test-123",
            tracer=mock_tracer
        ):
            pass

        # Verify tracer was passed
        call_args = mock_stream.call_args
        assert call_args.kwargs['tracer'] == mock_tracer

    @patch('proxy.handlers.custom_provider_handler.stream_custom_provider_response')
    async def test_handles_streaming_with_tools(self, mock_stream):
        """Test streaming with tool calls"""
        async def mock_gen():
            yield b'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"","tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"calc","arguments":""}}]},"finish_reason":null}]}\n\n'
            yield b'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"x\\":5}"}}]},"finish_reason":null}]}\n\n'
            yield b'data: {"id":"chatcmpl-1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\n\n'
            yield b'data: [DONE]\n\n'

        mock_stream.return_value = mock_gen()

        openai_request = {
            "model": "custom-model",
            "messages": [{"role": "user", "content": "Calculate"}],
            "tools": [{"type": "function", "function": {"name": "calc"}}],
            "stream": True
        }

        chunks = []
        async for chunk in handle_custom_provider_stream(
            openai_request=openai_request,
            base_url="https://api.custom.com/v1",
            api_key="test-key",
            request_id="test-123",
            tracer=None
        ):
            chunks.append(chunk)

        assert len(chunks) == 4
        assert b'tool_calls' in chunks[0]

    @patch('proxy.handlers.custom_provider_handler.stream_custom_provider_response')
    async def test_empty_stream(self, mock_stream):
        """Test handling of empty stream"""
        async def mock_gen():
            # Empty generator
            return
            yield

        mock_stream.return_value = mock_gen()

        chunks = []
        async for chunk in handle_custom_provider_stream(
            openai_request={},
            base_url="https://api.custom.com/v1",
            api_key="test-key",
            request_id="test-123",
            tracer=None
        ):
            chunks.append(chunk)

        # Should handle empty stream gracefully
        assert len(chunks) == 0

    @patch('proxy.handlers.custom_provider_handler.stream_custom_provider_response')
    async def test_passes_all_parameters(self, mock_stream):
        """Test that all parameters are correctly passed"""
        async def mock_gen():
            yield b'data: test\n\n'

        mock_stream.return_value = mock_gen()

        openai_request = {
            "model": "custom-model",
            "messages": [{"role": "user", "content": "Test"}],
            "temperature": 0.5,
            "stream": True
        }

        async for _ in handle_custom_provider_stream(
            openai_request=openai_request,
            base_url="https://api.example.com/v1",
            api_key="sk-custom-123",
            request_id="req-789",
            tracer=None
        ):
            pass

        # Verify all parameters were passed
        call_args = mock_stream.call_args
        assert call_args[0][0] == openai_request
        assert call_args[0][1] == "https://api.example.com/v1"
        assert call_args[0][2] == "sk-custom-123"
        assert call_args[0][3] == "req-789"
