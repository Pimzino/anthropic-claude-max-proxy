"""Smoke tests against real Anthropic API

⚠️  WARNING: These tests make real API calls and may incur costs.
Only run with ENABLE_SMOKE_TESTS=1 environment variable.

Example:
    ENABLE_SMOKE_TESTS=1 ANTHROPIC_OAUTH_TOKEN=sk-ant-... pytest tests/smoke/
"""
import pytest
from anthropic import make_anthropic_request


@pytest.mark.smoke
@pytest.mark.slow
class TestRealAnthropicAPI:
    """Smoke tests for real Anthropic API integration"""
    
    async def test_simple_message(self, real_oauth_token, smoke_test_enabled):
        """Test a simple message to Anthropic API"""
        request_data = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 100,
            "messages": [
                {"role": "user", "content": "Say 'test successful' and nothing else."}
            ]
        }
        
        response = await make_anthropic_request(request_data, real_oauth_token, None)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['type'] == 'message'
        assert 'content' in data
        assert len(data['content']) > 0
        assert 'test successful' in data['content'][0]['text'].lower()
    
    async def test_with_system_message(self, real_oauth_token, smoke_test_enabled):
        """Test request with system message"""
        request_data = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 50,
            "system": "You are a helpful assistant.",
            "messages": [
                {"role": "user", "content": "What is 2+2?"}
            ]
        }
        
        response = await make_anthropic_request(request_data, real_oauth_token, None)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['type'] == 'message'
        assert 'content' in data
        # Response should contain "4" somewhere
        response_text = data['content'][0]['text']
        assert '4' in response_text
    
    async def test_token_usage_reporting(self, real_oauth_token, smoke_test_enabled):
        """Test that token usage is properly reported"""
        request_data = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 50,
            "messages": [
                {"role": "user", "content": "Hi"}
            ]
        }
        
        response = await make_anthropic_request(request_data, real_oauth_token, None)
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'usage' in data
        assert 'input_tokens' in data['usage']
        assert 'output_tokens' in data['usage']
        assert data['usage']['input_tokens'] > 0
        assert data['usage']['output_tokens'] > 0
