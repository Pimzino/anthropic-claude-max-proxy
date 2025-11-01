"""Tests for TokenStorage"""
import json
import os
import time
from unittest.mock import patch

import pytest
from utils.storage import TokenStorage


@pytest.mark.unit
class TestTokenStorage:
    """Test suite for TokenStorage functionality"""

    def test_save_and_load_tokens(self, temp_token_file, valid_oauth_token):
        """Test saving and loading OAuth tokens"""
        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()

            # Save tokens
            storage.save_tokens(
                access_token=valid_oauth_token['access_token'],
                refresh_token=valid_oauth_token['refresh_token'],
                expires_in=3600
            )

            # Load tokens
            assert storage.get_access_token() == valid_oauth_token['access_token']
            assert storage.get_refresh_token() == valid_oauth_token['refresh_token']
            assert storage.is_authenticated() is True

    def test_save_long_term_token(self, temp_token_file, long_term_token):
        """Test saving and loading long-term tokens"""
        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()

            # Save long-term token
            storage.save_long_term_token(
                access_token=long_term_token['access_token'],
                expires_in=31536000  # 1 year
            )

            # Verify it's recognized as long-term
            assert storage.is_long_term_token() is True
            assert storage.get_access_token() == long_term_token['access_token']

    def test_token_expiry_check(self, temp_token_file):
        """Test token expiration detection"""
        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()

            # Save token that expires in 1 second
            storage.save_tokens(
                access_token="test-token",
                refresh_token="test-refresh",
                expires_in=1
            )

            # Should not be expired immediately
            assert storage.is_token_expired() is False

            # Wait for expiration
            time.sleep(2)

            # Should now be expired
            assert storage.is_token_expired() is True

    def test_clear_tokens(self, temp_token_file, valid_oauth_token):
        """Test clearing stored tokens"""
        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()

            # Save tokens
            storage.save_tokens(
                access_token=valid_oauth_token['access_token'],
                refresh_token=valid_oauth_token['refresh_token'],
                expires_in=3600
            )

            assert storage.is_authenticated() is True

            # Clear tokens
            storage.clear_tokens()

            # Should no longer be authenticated
            assert storage.is_authenticated() is False
            assert storage.get_access_token() is None
            assert storage.get_refresh_token() is None

    def test_token_file_creation(self, temp_token_file):
        """Test that token file is created if it doesn't exist"""
        # Remove the temp file
        if os.path.exists(temp_token_file):
            os.unlink(temp_token_file)
        assert not os.path.exists(temp_token_file)

        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()
            storage.save_tokens(
                access_token="test-token",
                refresh_token="test-refresh",
                expires_in=3600
            )

            # File should be created
            assert os.path.exists(temp_token_file)

    def test_invalid_token_file(self, temp_token_file):
        """Test handling of corrupted token file"""
        # Write invalid JSON to file
        with open(temp_token_file, 'w') as f:
            f.write("invalid json content {{{")

        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()

            # Should handle gracefully
            assert storage.is_authenticated() is False
            assert storage.get_access_token() is None

    def test_token_format_validation(self, temp_token_file):
        """Test that token format is validated"""
        with patch('utils.storage.TOKEN_FILE', temp_token_file):
            storage = TokenStorage()

            # Valid OAuth token format
            storage.save_tokens(
                access_token="sk-ant-sid01-validtokenhere1234567890",
                refresh_token="sk-ant-sid01-validrefreshhere1234567890",
                expires_in=3600
            )

            assert storage.is_authenticated() is True

            # Valid long-term token format
            storage.save_long_term_token(
                access_token="sk-ant-oat01-longtermtokenhere1234567890",
                expires_in=31536000
            )

            assert storage.is_long_term_token() is True
