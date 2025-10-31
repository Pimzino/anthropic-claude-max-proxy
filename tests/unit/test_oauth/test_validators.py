"""Tests for OAuth token validators"""
import pytest
from oauth.validators import (
    validate_token_format,
    is_long_term_token_format,
)


@pytest.mark.unit
class TestTokenValidators:
    """Test suite for token format validators"""
    
    def test_valid_long_term_token_format(self):
        """Test validation of valid long-term token format"""
        token = "sk-ant-oat01-abcdefghijklmnopqrstuvwxyz"
        assert validate_token_format(token) is True
        assert is_long_term_token_format(token) is True
    
    def test_invalid_token_format(self):
        """Test validation of invalid token formats"""
        invalid_tokens = [
            "",
            "invalid-token",
            "sk-ant-invalid",
            "not-a-token-at-all",
        ]
        
        for token in invalid_tokens:
            assert validate_token_format(token) is False
            assert is_long_term_token_format(token) is False
    
    def test_token_prefix_variations(self):
        """Test different token prefix variations"""
        # Test oat01 prefix (long-term)
        assert is_long_term_token_format("sk-ant-oat01-test123") is True
        assert validate_token_format("sk-ant-oat01-test123") is True
