"""Test fixture loader utilities

Helper functions to load and parse fixture JSON files.
"""
import json
from pathlib import Path
from typing import Any, Dict

FIXTURES_DIR = Path(__file__).parent


def load_fixture(filename: str) -> Dict[str, Any]:
    """Load a JSON fixture file
    
    Args:
        filename: Name of the fixture file (e.g., 'anthropic_responses.json')
        
    Returns:
        Parsed JSON data as dictionary
    """
    fixture_path = FIXTURES_DIR / filename
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_anthropic_response(response_type: str) -> Dict[str, Any]:
    """Get a specific Anthropic response fixture
    
    Args:
        response_type: Type of response (e.g., 'simple_text_response', 'tool_use_response')
        
    Returns:
        Anthropic response dictionary
    """
    data = load_fixture('anthropic_responses.json')
    return data[response_type]


def get_openai_request(request_type: str) -> Dict[str, Any]:
    """Get a specific OpenAI request fixture
    
    Args:
        request_type: Type of request (e.g., 'simple_chat', 'with_tools')
        
    Returns:
        OpenAI request dictionary
    """
    data = load_fixture('openai_requests.json')
    return data[request_type]


def get_token(token_type: str) -> Dict[str, Any]:
    """Get a specific token fixture
    
    Args:
        token_type: Type of token (e.g., 'valid_oauth_token', 'expired_oauth_token')
        
    Returns:
        Token data dictionary
    """
    data = load_fixture('tokens.json')
    return data[token_type]


def get_custom_models_config() -> Dict[str, Any]:
    """Get the custom models configuration fixture
    
    Returns:
        Custom models configuration dictionary
    """
    return load_fixture('models_config.json')
