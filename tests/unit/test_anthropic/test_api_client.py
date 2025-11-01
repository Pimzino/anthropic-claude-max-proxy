"""Tests for Anthropic API client"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import httpx

from anthropic.api_client import make_anthropic_request, stream_anthropic_response


async def async_iter(items):
    """Helper to create async iterator from list"""
    for item in items:
        yield item


@pytest.mark.unit
class TestMakeAnthropicRequest:
    """Test suite for non-streaming Anthropic requests"""

    @pytest.mark.asyncio
    async def test_make_request_basic(self):
        """Test basic non-streaming request"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }
        access_token = "test-access-token"

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "msg_123",
            "content": [{"type": "text", "text": "Hi"}]
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await make_anthropic_request(
                anthropic_request=anthropic_request,
                access_token=access_token
            )

            assert response.status_code == 200

            # Verify POST was made to correct endpoint
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.anthropic.com/v1/messages"

            # Verify headers
            headers = call_args[1]["headers"]
            assert headers["authorization"] == f"Bearer {access_token}"
            assert headers["anthropic-version"] == "2023-06-01"
            assert headers["content-type"] == "application/json"

    @pytest.mark.asyncio
    async def test_make_request_injects_system_message(self):
        """Test that system message is injected when not present"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with patch('anthropic.api_client.inject_claude_code_system_message') as mock_inject:
                mock_inject.return_value = {**anthropic_request, "system": "injected"}

                await make_anthropic_request(
                    anthropic_request=anthropic_request,
                    access_token="token"
                )

                # Verify injection was called
                mock_inject.assert_called_once_with(anthropic_request)

    @pytest.mark.asyncio
    async def test_make_request_preserves_existing_system(self):
        """Test that existing system message is preserved"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "system": "Existing system message",
            "max_tokens": 1024
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with patch('anthropic.api_client.inject_claude_code_system_message') as mock_inject:
                await make_anthropic_request(
                    anthropic_request=anthropic_request,
                    access_token="token"
                )

                # Verify injection was NOT called when system exists
                mock_inject.assert_not_called()

    @pytest.mark.asyncio
    async def test_make_request_with_beta_headers(self):
        """Test request with client-provided beta headers"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with patch('anthropic.api_client.build_beta_headers') as mock_build_beta:
                mock_build_beta.return_value = "custom-beta-header"

                await make_anthropic_request(
                    anthropic_request=anthropic_request,
                    access_token="token",
                    client_beta_headers="client-beta"
                )

                # Verify build_beta_headers was called with client headers
                mock_build_beta.assert_called_once()
                call_args = mock_build_beta.call_args
                assert call_args[1]["client_beta_headers"] == "client-beta"
                assert call_args[1]["for_streaming"] is False

    @pytest.mark.asyncio
    async def test_make_request_timeout_settings(self):
        """Test that correct timeout settings are used"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await make_anthropic_request(
                anthropic_request=anthropic_request,
                access_token="token"
            )

            # Verify AsyncClient was created with timeout
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            assert "timeout" in call_args[1]
            timeout = call_args[1]["timeout"]
            assert isinstance(timeout, httpx.Timeout)

    @pytest.mark.asyncio
    async def test_make_request_error_response(self):
        """Test handling of error response"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"type": "invalid_request_error", "message": "Invalid request"}
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = await make_anthropic_request(
                anthropic_request=anthropic_request,
                access_token="token"
            )

            assert response.status_code == 400


@pytest.mark.unit
class TestStreamAnthropicResponse:
    """Test suite for streaming Anthropic requests"""

    @pytest.mark.asyncio
    async def test_stream_response_basic(self):
        """Test basic streaming response"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024,
            "stream": True
        }

        mock_response = AsyncMock()
        mock_response.status_code = 200
        chunks_to_yield = [
            'event: message_start\ndata: {"type":"message_start"}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]
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
            async for chunk in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token"
            ):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert "message_start" in chunks[0]
            assert "Hi" in chunks[1]
            assert "message_stop" in chunks[2]

    @pytest.mark.asyncio
    async def test_stream_response_injects_system_message(self):
        """Test that system message is injected in streaming"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

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

            with patch('anthropic.api_client.inject_claude_code_system_message') as mock_inject:
                mock_inject.return_value = {**anthropic_request, "system": "injected"}

                async for _ in stream_anthropic_response(
                    request_id="req_123",
                    anthropic_request=anthropic_request,
                    access_token="token"
                ):
                    pass

                # Verify injection was called
                mock_inject.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_response_removes_internal_metadata(self):
        """Test that internal metadata is removed before API call"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024,
            "_use_1m_context": True  # Internal metadata
        }

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

            async for _ in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token"
            ):
                pass

            # Verify request sent to API doesn't include internal metadata
            call_args = mock_client.stream.call_args
            sent_request = call_args[1]["json"]
            assert "_use_1m_context" not in sent_request

    @pytest.mark.asyncio
    async def test_stream_response_with_tracer(self):
        """Test streaming with tracer enabled"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        mock_tracer = Mock()
        mock_tracer.log_note = Mock()
        mock_tracer.log_source_chunk = Mock()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_text = Mock(return_value=async_iter([
            'event: message_start\ndata: {"type":"message_start"}\n\n',
        ]))
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            async for _ in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token",
                tracer=mock_tracer
            ):
                pass

            # Verify tracer was called
            assert mock_tracer.log_note.call_count > 0
            assert mock_tracer.log_source_chunk.call_count > 0

    @pytest.mark.asyncio
    async def test_stream_response_non_200_status(self):
        """Test streaming with error status code"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.aread = AsyncMock(return_value=b'{"error":{"type":"authentication_error","message":"Invalid token"}}')
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.stream = MagicMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token"
            ):
                chunks.append(chunk)

            # Should yield error event
            assert len(chunks) == 1
            assert "event: error" in chunks[0]
            assert "Invalid token" in chunks[0]

    @pytest.mark.asyncio
    async def test_stream_response_timeout(self):
        """Test streaming with timeout error"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        async def mock_aiter_text():
            yield 'event: message_start\ndata: {"type":"message_start"}\n\n'
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
            async for chunk in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token"
            ):
                chunks.append(chunk)

            # Should yield data and timeout error
            assert len(chunks) == 2
            assert "message_start" in chunks[0]
            assert "event: error" in chunks[1]
            assert "timeout" in chunks[1].lower()

    @pytest.mark.asyncio
    async def test_stream_response_remote_protocol_error(self):
        """Test streaming with connection closed error"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

        async def mock_aiter_text():
            yield 'event: message_start\ndata: {"type":"message_start"}\n\n'
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
            async for chunk in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token"
            ):
                chunks.append(chunk)

            # Should yield data and connection error
            assert len(chunks) == 2
            assert "message_start" in chunks[0]
            assert "event: error" in chunks[1]
            assert "Connection closed" in chunks[1]

    @pytest.mark.asyncio
    async def test_stream_response_with_client_beta_headers(self):
        """Test streaming with client-provided beta headers"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

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

            with patch('anthropic.api_client.build_beta_headers') as mock_build_beta:
                mock_build_beta.return_value = "custom-beta-header"

                async for _ in stream_anthropic_response(
                    request_id="req_123",
                    anthropic_request=anthropic_request,
                    access_token="token",
                    client_beta_headers="client-beta"
                ):
                    pass

                # Verify build_beta_headers was called with correct params
                mock_build_beta.assert_called_once()
                call_args = mock_build_beta.call_args
                assert call_args[1]["client_beta_headers"] == "client-beta"
                assert call_args[1]["for_streaming"] is True
                assert call_args[1]["request_id"] == "req_123"

    @pytest.mark.asyncio
    async def test_stream_response_timeout_settings(self):
        """Test that streaming uses correct timeout settings"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

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

            async for _ in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="token"
            ):
                pass

            # Verify AsyncClient was created with streaming timeout
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            assert "timeout" in call_args[1]
            timeout = call_args[1]["timeout"]
            assert isinstance(timeout, httpx.Timeout)

    @pytest.mark.asyncio
    async def test_stream_response_headers_complete(self):
        """Test that all required headers are present"""
        anthropic_request = {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1024
        }

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

            async for _ in stream_anthropic_response(
                request_id="req_123",
                anthropic_request=anthropic_request,
                access_token="test-token"
            ):
                pass

            # Verify headers
            call_args = mock_client.stream.call_args
            headers = call_args[1]["headers"]

            assert headers["host"] == "api.anthropic.com"
            assert headers["authorization"] == "Bearer test-token"
            assert headers["anthropic-version"] == "2023-06-01"
            assert headers["content-type"] == "application/json"
            assert "anthropic-beta" in headers
            assert "User-Agent" in headers
