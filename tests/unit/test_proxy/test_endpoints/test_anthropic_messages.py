"""Unit tests for proxy.endpoints.anthropic_messages"""
from unittest.mock import patch, AsyncMock, MagicMock, Mock
import pytest
from fastapi import HTTPException


@pytest.mark.unit
class TestAnthropicMessagesEndpoint:
    """Test suite for anthropic_messages endpoint logic"""

    @patch('proxy.endpoints.anthropic_messages.maybe_create_stream_tracer')
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_max_tokens_adjustment_for_thinking(
        self,
        mock_manager,
        mock_tracer_factory
    ):
        """Test that max_tokens is increased when thinking is enabled"""
        from proxy.endpoints.anthropic_messages import anthropic_messages
        from anthropic.models import AnthropicMessageRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        # Create a mock raw request
        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        # Create request with thinking
        request = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=100,  # Low max_tokens
            messages=[{"role": "user", "content": "Think"}],
            thinking={"type": "enabled", "budget_tokens": 16000}
        )

        # Mock the Anthropic API response
        with patch('proxy.endpoints.anthropic_messages.make_anthropic_request') as mock_api:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "msg_123",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "Answer"}],
                "usage": {"input_tokens": 10, "output_tokens": 50}
            }
            mock_api.return_value = mock_response

            result = await anthropic_messages(request, mock_raw_request)

            # Verify the request to Anthropic had adjusted max_tokens
            call_args = mock_api.call_args
            anthropic_request = call_args[0][0]
            # Should be 16000 (thinking budget) + 1024 (min response) = 17024
            assert anthropic_request["max_tokens"] == 17024

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_no_token_returns_401(
        self,
        mock_manager
    ):
        """Test that missing token returns 401"""
        from proxy.endpoints.anthropic_messages import anthropic_messages
        from anthropic.models import AnthropicMessageRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value=None)

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello"}]
        )

        with pytest.raises(HTTPException) as exc_info:
            await anthropic_messages(request, mock_raw_request)

        assert exc_info.value.status_code == 401

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_anthropic_api_error_raises_http_exception(
        self,
        mock_manager
    ):
        """Test that Anthropic API errors are converted to HTTPException"""
        from proxy.endpoints.anthropic_messages import anthropic_messages
        from anthropic.models import AnthropicMessageRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello"}]
        )

        with patch('proxy.endpoints.anthropic_messages.make_anthropic_request') as mock_api:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": {"message": "Invalid request"}
            }
            mock_api.return_value = mock_response

            with pytest.raises(HTTPException) as exc_info:
                await anthropic_messages(request, mock_raw_request)

            assert exc_info.value.status_code == 400

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_non_json_error_response(
        self,
        mock_manager
    ):
        """Test handling of non-JSON error response"""
        from proxy.endpoints.anthropic_messages import anthropic_messages
        from anthropic.models import AnthropicMessageRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello"}]
        )

        with patch('proxy.endpoints.anthropic_messages.make_anthropic_request') as mock_api:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.json.side_effect = Exception("Not JSON")
            mock_response.text = "Service unavailable"
            mock_api.return_value = mock_response

            with pytest.raises(HTTPException) as exc_info:
                await anthropic_messages(request, mock_raw_request)

            assert exc_info.value.status_code == 503
            assert "Service unavailable" in str(exc_info.value.detail)

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_exception_during_request(
        self,
        mock_manager
    ):
        """Test exception handling during request"""
        from proxy.endpoints.anthropic_messages import anthropic_messages
        from anthropic.models import AnthropicMessageRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello"}]
        )

        with patch('proxy.endpoints.anthropic_messages.make_anthropic_request') as mock_api:
            mock_api.side_effect = Exception("Connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await anthropic_messages(request, mock_raw_request)

            assert exc_info.value.status_code == 500
            assert "Connection failed" in str(exc_info.value.detail)

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_successful_response_passthrough(
        self,
        mock_manager
    ):
        """Test successful response is returned as-is"""
        from proxy.endpoints.anthropic_messages import anthropic_messages
        from anthropic.models import AnthropicMessageRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = AnthropicMessageRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello"}]
        )

        with patch('proxy.endpoints.anthropic_messages.make_anthropic_request') as mock_api:
            expected_response = {
                "id": "msg_123",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello there!"}],
                "usage": {"input_tokens": 5, "output_tokens": 10}
            }
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_response
            mock_api.return_value = mock_response

            result = await anthropic_messages(request, mock_raw_request)

            assert result == expected_response
            assert result["id"] == "msg_123"
            assert result["type"] == "message"
