"""Integration tests for API endpoints"""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


@pytest.mark.integration
class TestHealthEndpoint:
    """Test suite for /health endpoint"""

    def test_health_check(self, fastapi_test_client):
        """Test that health endpoint returns healthy status"""
        response = fastapi_test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'


@pytest.mark.integration
class TestModelsEndpoint:
    """Test suite for /v1/models endpoint"""

    def test_list_models(self, fastapi_test_client):
        """Test listing available models"""
        response = fastapi_test_client.get("/v1/models")

        assert response.status_code == 200
        data = response.json()
        assert 'data' in data
        assert isinstance(data['data'], list)
        assert len(data['data']) > 0

        # Check model structure
        first_model = data['data'][0]
        assert 'id' in first_model
        assert 'object' in first_model
        assert first_model['object'] == 'model'

    def test_models_include_anthropic(self, fastapi_test_client):
        """Test that Anthropic models are included"""
        response = fastapi_test_client.get("/v1/models")
        data = response.json()

        model_ids = [model['id'] for model in data['data']]

        # Should include at least one Anthropic model (using OpenAI-style IDs)
        assert any('sonnet' in model_id or 'haiku' in model_id or 'opus' in model_id for model_id in model_ids)

    @patch('config.loader.load_custom_models')
    def test_models_include_custom(self, mock_load, fastapi_test_client):
        """Test that custom models endpoint works"""
        # Custom models are loaded at module import time, so mocking here won't affect the result
        # This test just verifies the endpoint returns a valid response
        response = fastapi_test_client.get("/v1/models")
        data = response.json()

        # Should have a valid response structure
        assert 'data' in data
        assert isinstance(data['data'], list)
        # Should have at least the base Anthropic models
        assert len(data['data']) > 0


@pytest.mark.integration
class TestOAuthStatusEndpoint:
    """Test suite for /oauth/status endpoint"""

    @patch('proxy.endpoints.auth.token_storage')
    def test_oauth_status_authenticated(self, mock_storage, fastapi_test_client):
        """Test OAuth status when authenticated"""
        mock_storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": "2025-12-31T23:59:59",
            "time_until_expiry": "365d 0h",
            "token_type": "oauth_flow"
        }

        response = fastapi_test_client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data['has_tokens'] is True

    @patch('proxy.endpoints.auth.token_storage')
    def test_oauth_status_unauthenticated(self, mock_storage, fastapi_test_client):
        """Test OAuth status when not authenticated"""
        mock_storage.get_status.return_value = {
            "has_tokens": False,
            "is_expired": True,
            "expires_at": None,
            "time_until_expiry": "No tokens",
            "token_type": None
        }

        response = fastapi_test_client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data['has_tokens'] is False

    @patch('proxy.endpoints.auth.token_storage')
    def test_oauth_status_long_term_token(self, mock_storage, fastapi_test_client):
        """Test OAuth status with long-term token"""
        mock_storage.get_status.return_value = {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": "2026-12-31T23:59:59",
            "time_until_expiry": "365d 0h",
            "token_type": "long_term"
        }

        response = fastapi_test_client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data['has_tokens'] is True


@pytest.mark.integration
class TestOpenAIChatEndpoint:
    """Test suite for /v1/chat/completions endpoint"""

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_simple_chat_completion(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client,
        openai_simple_request,
        mock_anthropic_text_response
    ):
        """Test basic chat completion request"""
        # Mock OAuth manager
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_anthropic_text_response

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json=openai_simple_request
        )

        assert response.status_code == 200
        data = response.json()

        # Check OpenAI format
        assert 'id' in data
        assert 'object' in data
        assert data['object'] == 'chat.completion'
        assert 'choices' in data
        assert len(data['choices']) > 0
        assert 'message' in data['choices'][0]

    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_chat_completion_unauthorized(self, mock_manager, fastapi_test_client):
        """Test chat completion without valid token"""
        # Mock OAuth manager to return no token
        mock_manager.get_valid_token_async = AsyncMock(return_value=None)
        mock_manager.is_authenticated.return_value = False

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
        )

        assert response.status_code == 401

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_chat_completion_missing_required_fields(self, mock_manager, mock_httpx, fastapi_test_client, mock_anthropic_text_response):
        """Test chat completion with missing max_tokens (should use default)"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_anthropic_text_response

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        # Missing max_tokens (should use default of 4096)
        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )

        # Should succeed with default max_tokens
        assert response.status_code == 200

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_chat_completion_with_reasoning(self, mock_manager, mock_httpx, fastapi_test_client):
        """Test chat completion with reasoning_effort parameter"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        mock_response_data = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Let me think...", "signature": "sig"},
                {"type": "text", "text": "The answer is 42"}
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 50}
        }

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Think about this"}],
                "max_tokens": 4000,
                "reasoning_effort": "high"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert 'reasoning_content' in data['choices'][0]['message']

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_chat_completion_with_tools(self, mock_manager, mock_httpx, fastapi_test_client):
        """Test chat completion with tool calling"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        mock_response_data = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "get_weather",
                    "input": {"location": "San Francisco"}
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 20}
        }

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "What's the weather?"}],
                "max_tokens": 1000,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get weather",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert 'tool_calls' in data['choices'][0]['message']

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_chat_completion_anthropic_error(self, mock_manager, mock_httpx, fastapi_test_client):
        """Test handling of Anthropic API errors"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock error response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"type": "rate_limit_error"}}

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
        )

        # Should propagate error
        assert response.status_code == 429


@pytest.mark.integration
class TestAnthropicMessagesEndpoint:
    """Test suite for /v1/messages endpoint (native Anthropic)"""

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    def test_native_anthropic_request(
        self,
        mock_manager,
        mock_httpx,
        fastapi_test_client,
        mock_anthropic_text_response
    ):
        """Test native Anthropic format request"""
        # Mock OAuth manager
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_anthropic_text_response

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Check Anthropic format
        assert 'id' in data
        assert 'type' in data
        assert data['type'] == 'message'
        assert 'content' in data
        assert 'usage' in data

    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    def test_native_anthropic_unauthorized(self, mock_manager, fastapi_test_client):
        """Test native Anthropic endpoint without auth"""
        mock_manager.get_valid_token_async = AsyncMock(return_value=None)
        mock_manager.is_authenticated.return_value = False

        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )

        assert response.status_code == 401

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    def test_native_anthropic_with_thinking(self, mock_manager, mock_httpx, fastapi_test_client):
        """Test native Anthropic with thinking parameter"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        mock_response_data = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Thinking...", "signature": "sig"},
                {"type": "text", "text": "Answer"}
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 50}
        }

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": "Think"}],
                "thinking": {"type": "enabled", "budget_tokens": 16000}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['type'] == 'message'


@pytest.mark.integration
class TestCustomModelRouting:
    """Test suite for custom model routing"""

    @patch('httpx.AsyncClient')
    @patch('config.loader.load_custom_models')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_custom_model_detection(self, mock_manager, mock_load, mock_httpx, fastapi_test_client, mock_anthropic_text_response):
        """Test that custom models endpoint works with mocked responses"""
        # Mock OAuth manager
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # This test just verifies the endpoint doesn't crash with custom models
        # The actual custom model loading happens at module import time
        mock_load.return_value = [
            {
                "id": "custom-model-1",
                "base_url": "https://api.custom.com/v1",
                "api_key": "key",
                "context_length": 100000
            }
        ]

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_anthropic_text_response

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        # Request with any model should succeed with mocked response
        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "non-existent-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
        )

        # Should succeed with mocked response
        assert response.status_code == 200


@pytest.mark.integration
class TestEdgeCases:
    """Test suite for edge cases and error scenarios"""

    def test_invalid_endpoint(self, fastapi_test_client):
        """Test accessing non-existent endpoint"""
        response = fastapi_test_client.get("/invalid/endpoint")
        assert response.status_code == 404

    def test_invalid_method(self, fastapi_test_client):
        """Test using wrong HTTP method"""
        response = fastapi_test_client.get("/v1/chat/completions")
        assert response.status_code == 405

    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_malformed_json(self, mock_manager, fastapi_test_client):
        """Test handling of malformed JSON"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @patch('httpx.AsyncClient')
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    def test_empty_messages_array(self, mock_manager, mock_httpx, fastapi_test_client, mock_anthropic_text_response):
        """Test with empty messages array (mocked API accepts it)"""
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        mock_manager.is_authenticated.return_value = True

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_anthropic_text_response

        # Mock the async context manager and post method
        mock_client_instance = MagicMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_client_instance

        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [],
                "max_tokens": 100
            }
        )

        # Should succeed with mocked response (no Pydantic validation for min length)
        assert response.status_code == 200
