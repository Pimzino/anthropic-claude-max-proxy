"""Integration tests for API endpoints"""
import json
from unittest.mock import patch, AsyncMock

import pytest
import respx
from httpx import Response


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
        
        # Should include at least one Claude model
        assert any('claude' in model_id for model_id in model_ids)


@pytest.mark.integration
class TestOAuthStatusEndpoint:
    """Test suite for /oauth/status endpoint"""
    
    @patch('proxy.endpoints.auth.oauth_manager')
    def test_oauth_status_authenticated(self, mock_manager, fastapi_test_client):
        """Test OAuth status when authenticated"""
        mock_manager.is_authenticated.return_value = True
        mock_manager.storage.is_long_term_token.return_value = False
        mock_manager.storage.is_token_expired.return_value = False
        
        response = fastapi_test_client.get("/oauth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data['authenticated'] is True
    
    @patch('proxy.endpoints.auth.oauth_manager')
    def test_oauth_status_unauthenticated(self, mock_manager, fastapi_test_client):
        """Test OAuth status when not authenticated"""
        mock_manager.is_authenticated.return_value = False
        
        response = fastapi_test_client.get("/oauth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data['authenticated'] is False


@pytest.mark.integration
class TestOpenAIChatEndpoint:
    """Test suite for /v1/chat/completions endpoint"""
    
    @respx.mock
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_simple_chat_completion(
        self, 
        mock_manager, 
        fastapi_test_client,
        openai_simple_request,
        mock_anthropic_text_response
    ):
        """Test basic chat completion request"""
        # Mock OAuth manager
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        
        # Mock Anthropic API
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=Response(200, json=mock_anthropic_text_response)
        )
        
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
        
        response = fastapi_test_client.post(
            "/v1/chat/completions",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100
            }
        )
        
        assert response.status_code == 401


@pytest.mark.integration  
class TestAnthropicMessagesEndpoint:
    """Test suite for /v1/messages endpoint (native Anthropic)"""
    
    @respx.mock
    @patch('proxy.endpoints.anthropic_messages.oauth_manager')
    async def test_native_anthropic_request(
        self,
        mock_manager,
        fastapi_test_client,
        mock_anthropic_text_response
    ):
        """Test native Anthropic format request"""
        # Mock OAuth manager
        mock_manager.get_valid_token_async = AsyncMock(return_value="test-token")
        
        # Mock Anthropic API
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=Response(200, json=mock_anthropic_text_response)
        )
        
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
