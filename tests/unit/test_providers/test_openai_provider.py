"""Tests for OpenAI-compatible provider implementation"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import httpx

from providers.openai_provider import OpenAIProvider


async def async_iter(items):
    """Helper to create async iterator from list"""
    for item in items:
        yield item


@pytest.mark.unit
class TestOpenAIProviderEndpoint:
    """Test suite for endpoint building logic"""

    def test_get_endpoint_with_complete_url(self):
        """Test endpoint when base_url already includes /chat/completions"""
        provider = OpenAIProvider(
            base_url="https://api.example.com/v1/chat/completions",
            api_key="test-key"
        )

        endpoint = provider._get_endpoint()
        assert endpoint == "https://api.example.com/v1/chat/completions"

    def test_get_endpoint_with_trailing_slash(self):
        """Test endpoint when base_url ends with trailing slash"""
        provider = OpenAIProvider(
            base_url="https://api.example.com/v1/",
            api_key="test-key"
        )

        endpoint = provider._get_endpoint()
        assert endpoint == "https://api.example.com/v1/chat/completions"

    def test_get_endpoint_without_trailing_slash(self):
        """Test endpoint when base_url has no trailing slash"""
        provider = OpenAIProvider(
            base_url="https://api.example.com/v1",
            api_key="test-key"
        )

        endpoint = provider._get_endpoint()
        assert endpoint == "https://api.example.com/v1/chat/completions"

    def test_get_endpoint_with_custom_path(self):
        """Test endpoint with custom provider path"""
        provider = OpenAIProvider(
            base_url="https://api.z.ai/api/coding/paas/v4",
            api_key="test-key"
        )

        endpoint = provider._get_endpoint()
        assert endpoint == "https://api.z.ai/api/coding/paas/v4/chat/completions"


@pytest.mark.unit
class TestOpenAIProviderHeaders:
    """Test suite for header building logic"""

    def test_get_headers_default(self):
        """Test default headers for requests"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="sk-test-key-123"
        )

        headers = provider._get_headers()

        assert headers["Authorization"] == "Bearer sk-test-key-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_get_headers_streaming(self):
        """Test headers for streaming requests"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="sk-test-key-123"
        )

        headers = provider._get_headers(accept="text/event-stream")

        assert headers["Authorization"] == "Bearer sk-test-key-123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "text/event-stream"

    def test_get_headers_with_different_api_key(self):
        """Test headers with different API key format"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="custom-api-key-format"
        )

        headers = provider._get_headers()

        assert headers["Authorization"] == "Bearer custom-api-key-format"


@pytest.mark.unit
class TestOpenAIProviderMakeRequest:
    """Test suite for non-streaming requests"""

    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test successful non-streaming request"""
        provider = OpenAIProvider(
            base_url="https://api.example.com/v1",
            api_key="test-key"
        )

        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}]
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hi"}}]}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await provider.make_request(request_data, "req_123")

            assert response.status_code == 200
            mock_client.post.assert_called_once()

            # Verify endpoint
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.example.com/v1/chat/completions"

            # Verify request data
            assert call_args[1]["json"] == request_data

            # Verify headers
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer test-key"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_make_request_with_timeout(self):
        """Test request uses correct timeout settings"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await provider.make_request({"model": "test"}, "req_123")

            # Verify AsyncClient was created with timeout
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            assert "timeout" in call_args[1]
            timeout = call_args[1]["timeout"]
            assert isinstance(timeout, httpx.Timeout)

    @pytest.mark.asyncio
    async def test_make_request_error_response(self):
        """Test handling of error response"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Bad request"}}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await provider.make_request({"model": "test"}, "req_123")

            assert response.status_code == 400


@pytest.mark.unit
class TestOpenAIProviderStreamResponse:
    """Test suite for streaming requests"""

    @pytest.mark.asyncio
    async def test_stream_response_success(self):
        """Test successful streaming response"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        request_data = {"model": "gpt-4", "stream": True}

        # Mock streaming response
        chunks_to_yield = [
            "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n",
            "data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}\n\n",
            "data: [DONE]\n\n"
        ]
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_text = Mock(return_value=async_iter(chunks_to_yield))
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream_response(request_data, "req_123"):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert "Hello" in chunks[0]
            assert "world" in chunks[1]
            assert "[DONE]" in chunks[2]

    @pytest.mark.asyncio
    async def test_stream_response_with_tracer(self):
        """Test streaming with tracer enabled"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        mock_tracer = Mock()
        mock_tracer.log_note = Mock()
        mock_tracer.log_source_chunk = Mock()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_text = Mock(return_value=async_iter(["data: test\n\n"]))
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream_response(
                {"model": "test"}, "req_123", tracer=mock_tracer
            ):
                chunks.append(chunk)

            # Verify tracer was called
            assert mock_tracer.log_note.call_count > 0
            assert mock_tracer.log_source_chunk.call_count > 0

    @pytest.mark.asyncio
    async def test_stream_response_non_200_status(self):
        """Test streaming with error status code"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.aread = AsyncMock(return_value=b'{"error":"Unauthorized"}')
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream_response({"model": "test"}, "req_123"):
                chunks.append(chunk)

            # Should yield error event
            assert len(chunks) == 1
            assert "event: error" in chunks[0]
            assert "Unauthorized" in chunks[0]

    @pytest.mark.asyncio
    async def test_stream_response_timeout(self):
        """Test streaming with timeout error"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        async def mock_aiter_text():
            yield "data: start\n\n"
            raise httpx.ReadTimeout("Timeout")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_text = mock_aiter_text
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream_response({"model": "test"}, "req_123"):
                chunks.append(chunk)

            # Should yield data and timeout error
            assert len(chunks) == 2
            assert "start" in chunks[0]
            assert "event: error" in chunks[1]
            assert "timeout" in chunks[1].lower()

    @pytest.mark.asyncio
    async def test_stream_response_remote_protocol_error(self):
        """Test streaming with connection closed error"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        async def mock_aiter_text():
            yield "data: start\n\n"
            raise httpx.RemoteProtocolError("Connection closed")

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_text = mock_aiter_text
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in provider.stream_response({"model": "test"}, "req_123"):
                chunks.append(chunk)

            # Should yield data and connection error
            assert len(chunks) == 2
            assert "start" in chunks[0]
            assert "event: error" in chunks[1]
            assert "Connection closed" in chunks[1]

    @pytest.mark.asyncio
    async def test_stream_response_uses_streaming_timeout(self):
        """Test that streaming uses appropriate timeout settings"""
        provider = OpenAIProvider(
            base_url="https://api.example.com",
            api_key="test-key"
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_text = Mock(return_value=async_iter([]))
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            async for _ in provider.stream_response({"model": "test"}, "req_123"):
                pass

            # Verify AsyncClient was created with streaming timeout
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            assert "timeout" in call_args[1]
            timeout = call_args[1]["timeout"]
            assert isinstance(timeout, httpx.Timeout)
