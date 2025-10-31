"""Shared pytest fixtures for all tests

This module provides common fixtures used across unit, integration, and smoke tests.
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from unittest.mock import Mock, MagicMock

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response

# Import fixtures loader
from tests.fixtures.loader import (
    get_anthropic_response,
    get_openai_request,
    get_token,
    get_custom_models_config,
)


@pytest.fixture
def temp_token_file():
    """Create a temporary token file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_models_config_file():
    """Create a temporary models.json file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(get_custom_models_config(), f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_token_storage(temp_token_file):
    """Create a mock TokenStorage instance"""
    from utils.storage import TokenStorage
    
    storage = TokenStorage(token_file=temp_token_file)
    return storage


@pytest.fixture
def valid_oauth_token():
    """Get a valid OAuth token for testing"""
    return get_token('valid_oauth_token')


@pytest.fixture
def expired_oauth_token():
    """Get an expired OAuth token for testing"""
    return get_token('expired_oauth_token')


@pytest.fixture
def long_term_token():
    """Get a long-term OAuth token for testing"""
    return get_token('long_term_token')


@pytest.fixture
def mock_anthropic_text_response():
    """Get a simple text response from Anthropic"""
    return get_anthropic_response('simple_text_response')


@pytest.fixture
def mock_anthropic_tool_response():
    """Get a tool use response from Anthropic"""
    return get_anthropic_response('tool_use_response')


@pytest.fixture
def mock_anthropic_thinking_response():
    """Get a thinking response from Anthropic"""
    return get_anthropic_response('thinking_response')


@pytest.fixture
def openai_simple_request():
    """Get a simple OpenAI chat request"""
    return get_openai_request('simple_chat')


@pytest.fixture
def openai_tools_request():
    """Get an OpenAI request with tools"""
    return get_openai_request('with_tools')


@pytest.fixture
def openai_reasoning_request():
    """Get an OpenAI request with reasoning enabled"""
    return get_openai_request('with_reasoning')


@pytest.fixture
def custom_models_config():
    """Get custom models configuration"""
    return get_custom_models_config()


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient for testing"""
    with respx.mock:
        yield respx


@pytest.fixture
async def async_client():
    """Create an async httpx client for testing"""
    async with AsyncClient() as client:
        yield client


@pytest.fixture
def fastapi_test_client():
    """Create a FastAPI TestClient for integration tests"""
    from proxy.app import app
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_oauth_manager(valid_oauth_token):
    """Create a mock OAuthManager with valid token"""
    from oauth import OAuthManager
    
    manager = Mock(spec=OAuthManager)
    manager.get_valid_token_async = Mock(return_value=valid_oauth_token['access_token'])
    manager.get_valid_token = Mock(return_value=valid_oauth_token['access_token'])
    manager.is_authenticated = Mock(return_value=True)
    
    return manager


@pytest.fixture
def mock_config_with_custom_models(temp_models_config_file, monkeypatch):
    """Mock settings to use temporary models.json file"""
    import settings
    
    # Patch the models.json path
    monkeypatch.setattr('models.custom_models.MODELS_JSON_PATH', temp_models_config_file)
    
    # Force reload of custom models
    from models import custom_models
    custom_models._custom_models_cache = None  # Clear cache if it exists
    
    yield
    
    # Cleanup
    custom_models._custom_models_cache = None


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing"""
    env_vars = {
        'PORT': '8081',
        'LOG_LEVEL': 'debug',
        'DEFAULT_MODEL': 'claude-sonnet-4-20250514',
        'STREAM_TRACE_ENABLED': 'false',
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def sample_sse_chunks():
    """Generate sample SSE chunks for streaming tests"""
    return [
        b'event: message_start\n',
        b'data: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
        b'event: content_block_start\n',
        b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
        b'event: content_block_delta\n',
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n',
        b'event: content_block_delta\n',
        b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}\n\n',
        b'event: content_block_stop\n',
        b'data: {"type":"content_block_stop","index":0}\n\n',
        b'event: message_delta\n',
        b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
        b'event: message_stop\n',
        b'data: {"type":"message_stop"}\n\n',
    ]


@pytest.fixture
def mock_anthropic_api(mock_httpx_client, mock_anthropic_text_response):
    """Mock Anthropic API responses using respx"""
    # Mock the messages endpoint
    route = mock_httpx_client.post(
        "https://api.anthropic.com/v1/messages"
    ).mock(
        return_value=Response(
            200,
            json=mock_anthropic_text_response
        )
    )
    
    return route


@pytest.fixture
def mock_custom_provider_api(mock_httpx_client):
    """Mock custom provider API responses using respx"""
    # Mock a generic OpenAI-compatible endpoint
    route = mock_httpx_client.post(
        url__regex=r"https://api\..*/v1/chat/completions"
    ).mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-test123",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "test-model-1",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Test response from custom provider"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
        )
    )
    
    return route


# Markers for convenience
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (may use TestClient)"
    )
    config.addinivalue_line(
        "markers", "smoke: Smoke tests (require real API tokens, opt-in only)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (may take several seconds)"
    )
