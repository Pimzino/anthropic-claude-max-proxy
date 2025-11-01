"""Tests for providers public API functions"""
import pytest
from unittest.mock import AsyncMock, Mock, patch

from providers import make_custom_provider_request, stream_custom_provider_response


@pytest.mark.unit
class TestMakeCustomProviderRequest:
    """Test suite for make_custom_provider_request function"""

    @pytest.mark.asyncio
    async def test_make_custom_provider_request_creates_provider(self):
        """Test that function creates OpenAIProvider instance"""
        request_data = {"model": "custom-model", "messages": []}
        base_url = "https://custom.api.com"
        api_key = "custom-key"
        request_id = "req_123"

        mock_response = Mock()
        mock_response.status_code = 200

        with patch('providers.OpenAIProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.make_request = AsyncMock(return_value=mock_response)
            mock_provider_class.return_value = mock_provider

            response = await make_custom_provider_request(
                request_data=request_data,
                base_url=base_url,
                api_key=api_key,
                request_id=request_id
            )

            # Verify provider was created with correct parameters
            mock_provider_class.assert_called_once_with(
                base_url=base_url,
                api_key=api_key
            )

            # Verify make_request was called
            mock_provider.make_request.assert_called_once_with(
                request_data,
                request_id
            )

            # Verify response is returned
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_make_custom_provider_request_with_different_params(self):
        """Test function with different parameter values"""
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.7
        }
        base_url = "https://api.z.ai/api/coding/paas/v4"
        api_key = "sk-abc123"
        request_id = "custom_req_456"

        mock_response = Mock(status_code=200)

        with patch('providers.OpenAIProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.make_request = AsyncMock(return_value=mock_response)
            mock_provider_class.return_value = mock_provider

            response = await make_custom_provider_request(
                request_data=request_data,
                base_url=base_url,
                api_key=api_key,
                request_id=request_id
            )

            assert response.status_code == 200
            mock_provider.make_request.assert_called_once_with(
                request_data,
                request_id
            )


@pytest.mark.unit
class TestStreamCustomProviderResponse:
    """Test suite for stream_custom_provider_response function"""

    @pytest.mark.asyncio
    async def test_stream_custom_provider_response_creates_provider(self):
        """Test that function creates OpenAIProvider instance"""
        request_data = {"model": "custom-model", "stream": True}
        base_url = "https://custom.api.com"
        api_key = "custom-key"
        request_id = "req_123"

        async def mock_stream():
            yield "data: chunk1\n\n"
            yield "data: chunk2\n\n"

        with patch('providers.OpenAIProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.stream_response = Mock(return_value=mock_stream())
            mock_provider_class.return_value = mock_provider

            chunks = []
            async for chunk in stream_custom_provider_response(
                request_data=request_data,
                base_url=base_url,
                api_key=api_key,
                request_id=request_id
            ):
                chunks.append(chunk)

            # Verify provider was created
            mock_provider_class.assert_called_once_with(
                base_url=base_url,
                api_key=api_key
            )

            # Verify stream_response was called
            mock_provider.stream_response.assert_called_once_with(
                request_data,
                request_id,
                None
            )

            # Verify chunks were yielded
            assert len(chunks) == 2
            assert chunks[0] == "data: chunk1\n\n"
            assert chunks[1] == "data: chunk2\n\n"

    @pytest.mark.asyncio
    async def test_stream_custom_provider_response_with_tracer(self):
        """Test streaming function with tracer parameter"""
        request_data = {"model": "test"}
        base_url = "https://api.test.com"
        api_key = "key"
        request_id = "req_789"
        mock_tracer = Mock()

        async def mock_stream():
            yield "data: test\n\n"

        with patch('providers.OpenAIProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.stream_response = Mock(return_value=mock_stream())
            mock_provider_class.return_value = mock_provider

            chunks = []
            async for chunk in stream_custom_provider_response(
                request_data=request_data,
                base_url=base_url,
                api_key=api_key,
                request_id=request_id,
                tracer=mock_tracer
            ):
                chunks.append(chunk)

            # Verify tracer was passed to stream_response
            mock_provider.stream_response.assert_called_once_with(
                request_data,
                request_id,
                mock_tracer
            )

    @pytest.mark.asyncio
    async def test_stream_custom_provider_response_yields_all_chunks(self):
        """Test that all chunks are yielded correctly"""
        request_data = {"model": "test"}

        async def mock_stream():
            for i in range(5):
                yield f"data: chunk{i}\n\n"

        with patch('providers.OpenAIProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider.stream_response = Mock(return_value=mock_stream())
            mock_provider_class.return_value = mock_provider

            chunks = []
            async for chunk in stream_custom_provider_response(
                request_data=request_data,
                base_url="https://test.com",
                api_key="key",
                request_id="req"
            ):
                chunks.append(chunk)

            assert len(chunks) == 5
            for i in range(5):
                assert f"chunk{i}" in chunks[i]

    @pytest.mark.asyncio
    async def test_stream_provider_backward_compatibility(self):
        """Test that the function maintains backward compatibility"""
        # This tests the public API interface
        request_data = {"model": "gpt-4"}

        async def mock_stream():
            yield "data: test\n\n"

        with patch('providers.OpenAIProvider') as mock_provider_class:
            # Test without tracer (optional parameter)
            mock_provider = Mock()
            mock_provider.stream_response = Mock(return_value=mock_stream())
            mock_provider_class.return_value = mock_provider

            chunks = []
            async for chunk in stream_custom_provider_response(
                request_data=request_data,
                base_url="https://api.com",
                api_key="key",
                request_id="req"
            ):
                chunks.append(chunk)

            assert len(chunks) == 1

        with patch('providers.OpenAIProvider') as mock_provider_class:
            # Test with tracer
            mock_tracer = Mock()
            mock_provider = Mock()
            mock_provider.stream_response = Mock(return_value=mock_stream())
            mock_provider_class.return_value = mock_provider

            chunks = []
            async for chunk in stream_custom_provider_response(
                request_data=request_data,
                base_url="https://api.com",
                api_key="key",
                request_id="req",
                tracer=mock_tracer
            ):
                chunks.append(chunk)

            assert len(chunks) == 1
