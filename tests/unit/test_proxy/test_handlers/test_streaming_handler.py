"""Unit tests for proxy.handlers.streaming_handler"""
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from proxy.handlers.streaming_handler import create_anthropic_stream, create_openai_stream


@pytest.mark.unit
class TestCreateAnthropicStream:
    """Test suite for create_anthropic_stream function"""

    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_creates_anthropic_stream(self, mock_stream):
        """Test that create_anthropic_stream calls stream_anthropic_response"""
        # Setup mock async generator
        async def mock_gen():
            yield b'data: test1\n\n'
            yield b'data: test2\n\n'

        mock_stream.return_value = mock_gen()

        anthropic_request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        # Call create_anthropic_stream
        chunks = []
        async for chunk in create_anthropic_stream(
            request_id="test-123",
            anthropic_request=anthropic_request,
            access_token="test-token",
            client_beta_headers=None,
            tracer=None
        ):
            chunks.append(chunk)

        # Verify stream was called
        mock_stream.assert_called_once_with(
            "test-123",
            anthropic_request,
            "test-token",
            None,
            tracer=None
        )

        # Verify chunks were yielded
        assert len(chunks) == 2
        assert chunks[0] == b'data: test1\n\n'
        assert chunks[1] == b'data: test2\n\n'

    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_passes_tracer(self, mock_stream):
        """Test that tracer is passed through"""
        async def mock_gen():
            yield b'data: test\n\n'

        mock_stream.return_value = mock_gen()

        mock_tracer = MagicMock()

        async for _ in create_anthropic_stream(
            request_id="test-123",
            anthropic_request={},
            access_token="test-token",
            client_beta_headers=None,
            tracer=mock_tracer
        ):
            pass

        # Verify tracer was passed
        call_args = mock_stream.call_args
        assert call_args.kwargs['tracer'] == mock_tracer

    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_passes_beta_headers(self, mock_stream):
        """Test that beta headers are passed through"""
        async def mock_gen():
            yield b'data: test\n\n'

        mock_stream.return_value = mock_gen()

        async for _ in create_anthropic_stream(
            request_id="test-123",
            anthropic_request={},
            access_token="test-token",
            client_beta_headers="test-beta-header",
            tracer=None
        ):
            pass

        # Verify beta headers were passed
        call_args = mock_stream.call_args
        assert call_args[0][3] == "test-beta-header"


@pytest.mark.unit
class TestCreateOpenAIStream:
    """Test suite for create_openai_stream function"""

    @patch('proxy.handlers.streaming_handler.convert_anthropic_stream_to_openai')
    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_creates_openai_stream(
        self,
        mock_anthropic_stream,
        mock_convert
    ):
        """Test that create_openai_stream converts Anthropic to OpenAI format"""
        # Setup mock Anthropic stream
        async def mock_anthropic_gen():
            yield b'event: message_start\n'
            yield b'data: {"type":"message_start"}\n\n'

        mock_anthropic_stream.return_value = mock_anthropic_gen()

        # Setup mock OpenAI stream
        async def mock_openai_gen(stream, model, request_id, tracer):
            yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            yield b'data: [DONE]\n\n'

        mock_convert.side_effect = mock_openai_gen

        anthropic_request = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        # Call create_openai_stream
        chunks = []
        async for chunk in create_openai_stream(
            request_id="test-123",
            anthropic_request=anthropic_request,
            access_token="test-token",
            client_beta_headers=None,
            model="gpt-4",
            tracer=None
        ):
            chunks.append(chunk)

        # Verify Anthropic stream was called
        mock_anthropic_stream.assert_called_once()

        # Verify converter was called
        mock_convert.assert_called_once()
        call_args = mock_convert.call_args
        assert call_args[0][1] == "gpt-4"  # model
        assert call_args[0][2] == "test-123"  # request_id

        # Verify OpenAI chunks were yielded
        assert len(chunks) == 2
        assert b'"choices"' in chunks[0]
        assert b'[DONE]' in chunks[1]

    @patch('proxy.handlers.streaming_handler.convert_anthropic_stream_to_openai')
    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_passes_model_to_converter(
        self,
        mock_anthropic_stream,
        mock_convert
    ):
        """Test that model name is passed to converter"""
        async def mock_anthropic_gen():
            yield b'data: test\n\n'

        mock_anthropic_stream.return_value = mock_anthropic_gen()

        async def mock_openai_gen(stream, model, request_id, tracer):
            yield b'data: test\n\n'

        mock_convert.side_effect = mock_openai_gen

        async for _ in create_openai_stream(
            request_id="test-123",
            anthropic_request={},
            access_token="test-token",
            client_beta_headers=None,
            model="custom-model-name",
            tracer=None
        ):
            pass

        # Verify model was passed to converter
        call_args = mock_convert.call_args
        assert call_args[0][1] == "custom-model-name"

    @patch('proxy.handlers.streaming_handler.convert_anthropic_stream_to_openai')
    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_passes_tracer_to_both(
        self,
        mock_anthropic_stream,
        mock_convert
    ):
        """Test that tracer is passed to both stream and converter"""
        async def mock_anthropic_gen():
            yield b'data: test\n\n'

        mock_anthropic_stream.return_value = mock_anthropic_gen()

        async def mock_openai_gen(stream, model, request_id, tracer):
            yield b'data: test\n\n'

        mock_convert.side_effect = mock_openai_gen

        mock_tracer = MagicMock()

        async for _ in create_openai_stream(
            request_id="test-123",
            anthropic_request={},
            access_token="test-token",
            client_beta_headers=None,
            model="gpt-4",
            tracer=mock_tracer
        ):
            pass

        # Verify tracer was passed to Anthropic stream
        anthropic_call_args = mock_anthropic_stream.call_args
        assert anthropic_call_args.kwargs['tracer'] == mock_tracer

        # Verify tracer was passed to converter
        convert_call_args = mock_convert.call_args
        assert convert_call_args.kwargs['tracer'] == mock_tracer

    @patch('proxy.handlers.streaming_handler.convert_anthropic_stream_to_openai')
    @patch('proxy.handlers.streaming_handler.stream_anthropic_response')
    async def test_empty_stream(
        self,
        mock_anthropic_stream,
        mock_convert
    ):
        """Test handling of empty stream"""
        async def mock_anthropic_gen():
            # Empty generator
            return
            yield

        mock_anthropic_stream.return_value = mock_anthropic_gen()

        async def mock_openai_gen(stream, model, request_id, tracer):
            # Empty generator
            return
            yield

        mock_convert.side_effect = mock_openai_gen

        chunks = []
        async for chunk in create_openai_stream(
            request_id="test-123",
            anthropic_request={},
            access_token="test-token",
            client_beta_headers=None,
            model="gpt-4",
            tracer=None
        ):
            chunks.append(chunk)

        # Should handle empty stream gracefully
        assert len(chunks) == 0
