"""Unit tests for proxy.endpoints.openai_chat"""
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from fastapi import HTTPException


@pytest.mark.unit
class TestOpenAIChatEndpoint:
    """Test suite for openai_chat endpoint logic"""

    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_no_token_returns_401(
        self,
        mock_manager
    ):
        """Test that missing token returns 401 (for non-custom models)"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value=None)

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        # Mock is_custom_model to return False
        with patch('proxy.endpoints.openai_chat.is_custom_model', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await openai_chat_completions(request, mock_raw_request)

            assert exc_info.value.status_code == 401

    @patch('proxy.endpoints.openai_chat.get_custom_model_config')
    @patch('proxy.endpoints.openai_chat.is_custom_model')
    async def test_custom_model_not_configured_error(
        self,
        mock_is_custom,
        mock_get_config
    ):
        """Test error when custom model config not found"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_is_custom.return_value = True
        mock_get_config.return_value = None

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="unconfigured-model",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        with pytest.raises(HTTPException) as exc_info:
            await openai_chat_completions(request, mock_raw_request)

        assert exc_info.value.status_code == 400
        assert "not properly configured" in str(exc_info.value.detail)

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.get_custom_model_config')
    @patch('proxy.endpoints.openai_chat.is_custom_model')
    async def test_custom_provider_error_handling(
        self,
        mock_is_custom,
        mock_get_config,
        mock_httpx
    ):
        """Test error handling for custom provider"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_is_custom.return_value = True
        mock_get_config.return_value = {
            "id": "custom-model",
            "base_url": "https://api.custom.com/v1",
            "api_key": "test-key",
            "context_length": 100000
        }

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="custom-model",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        # Mock error response from custom provider
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {
                "message": "Invalid API key",
                "type": "authentication_error",
                "code": 401
            }
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        with pytest.raises(HTTPException) as exc_info:
            await openai_chat_completions(request, mock_raw_request)

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value.detail)

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.get_custom_model_config')
    @patch('proxy.endpoints.openai_chat.is_custom_model')
    async def test_custom_provider_exception(
        self,
        mock_is_custom,
        mock_get_config,
        mock_httpx
    ):
        """Test exception handling for custom provider"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_is_custom.return_value = True
        mock_get_config.return_value = {
            "id": "custom-model",
            "base_url": "https://api.custom.com/v1",
            "api_key": "test-key",
            "context_length": 100000
        }

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="custom-model",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        # Mock exception from custom provider
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        with pytest.raises(HTTPException) as exc_info:
            await openai_chat_completions(request, mock_raw_request)

        assert exc_info.value.status_code == 500
        assert "Connection timeout" in str(exc_info.value.detail)

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_anthropic_error_converted_to_openai_format(
        self,
        mock_manager,
        mock_httpx
    ):
        """Test that Anthropic errors are converted to OpenAI format"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        # Mock Anthropic error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {
                "type": "invalid_request_error",
                "message": "Invalid parameters"
            }
        }

        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        with patch('proxy.endpoints.openai_chat.is_custom_model', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await openai_chat_completions(request, mock_raw_request)

            assert exc_info.value.status_code == 400
            # Check OpenAI format
            detail = exc_info.value.detail
            assert "error" in detail
            assert "message" in detail["error"]
            assert "type" in detail["error"]
            assert "code" in detail["error"]
            assert detail["error"]["message"] == "Invalid parameters"

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_non_json_error_converted_to_openai_format(
        self,
        mock_manager,
        mock_httpx
    ):
        """Test that non-JSON errors are converted to OpenAI format"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        # Mock non-JSON error
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "Bad Gateway"

        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        with patch('proxy.endpoints.openai_chat.is_custom_model', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await openai_chat_completions(request, mock_raw_request)

            assert exc_info.value.status_code == 502
            detail = exc_info.value.detail
            assert detail["error"]["type"] == "api_error"
            assert detail["error"]["message"] == "Bad Gateway"
            assert detail["error"]["code"] == 502

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_exception_returned_in_openai_format(
        self,
        mock_manager,
        mock_httpx
    ):
        """Test that exceptions are returned in OpenAI format"""
        from proxy.endpoints.openai_chat import openai_chat_completions
        from proxy.models import OpenAIChatCompletionRequest

        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")

        mock_raw_request = MagicMock()
        mock_raw_request.headers = {}

        request = OpenAIChatCompletionRequest(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1000
        )

        # Mock exception
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        with patch('proxy.endpoints.openai_chat.is_custom_model', return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await openai_chat_completions(request, mock_raw_request)

            assert exc_info.value.status_code == 500
            detail = exc_info.value.detail
            assert detail["error"]["type"] == "internal_error"
            assert "Network error" in detail["error"]["message"]
            assert detail["error"]["code"] == 500
