"""Tests for OAuth token manager"""
import pytest
from unittest.mock import patch, AsyncMock
import asyncio

from oauth.token_manager import get_valid_token_async, get_valid_token
from utils.storage import TokenStorage


@pytest.mark.unit
class TestGetValidTokenAsync:
    """Test suite for async token retrieval"""

    @pytest.mark.asyncio
    async def test_get_valid_long_term_token_not_expired(self):
        """Test getting valid long-term token that hasn't expired"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=True), \
             patch.object(storage, 'is_token_expired', return_value=False), \
             patch.object(storage, 'get_access_token', return_value="sk-ant-oat01-token"):

            token = await get_valid_token_async(storage)

            assert token == "sk-ant-oat01-token"

    @pytest.mark.asyncio
    async def test_get_valid_long_term_token_expired_returns_none(self):
        """Test that expired long-term token returns None"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=True), \
             patch.object(storage, 'is_token_expired', return_value=True):

            token = await get_valid_token_async(storage)

            assert token is None

    @pytest.mark.asyncio
    async def test_get_valid_oauth_token_not_expired(self):
        """Test getting valid OAuth flow token that hasn't expired"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=False), \
             patch.object(storage, 'get_access_token', return_value="oauth_token"):

            token = await get_valid_token_async(storage)

            assert token == "oauth_token"

    @pytest.mark.asyncio
    async def test_get_valid_oauth_token_expired_refreshes(self):
        """Test that expired OAuth token triggers refresh"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=True), \
             patch('oauth.token_manager.refresh_tokens', new_callable=AsyncMock, return_value=True), \
             patch.object(storage, 'get_access_token', return_value="refreshed_token"):

            token = await get_valid_token_async(storage)

            assert token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_get_valid_oauth_token_refresh_fails_returns_none(self):
        """Test that failed refresh returns None"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=True), \
             patch('oauth.token_manager.refresh_tokens', new_callable=AsyncMock, return_value=False):

            token = await get_valid_token_async(storage)

            assert token is None


@pytest.mark.unit
class TestGetValidToken:
    """Test suite for sync token retrieval"""

    def test_get_valid_long_term_token_not_expired(self):
        """Test getting valid long-term token (sync)"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=True), \
             patch.object(storage, 'is_token_expired', return_value=False), \
             patch.object(storage, 'get_access_token', return_value="sk-ant-oat01-token"):

            token = get_valid_token(storage)

            assert token == "sk-ant-oat01-token"

    def test_get_valid_long_term_token_expired_returns_none(self):
        """Test that expired long-term token returns None (sync)"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=True), \
             patch.object(storage, 'is_token_expired', return_value=True):

            token = get_valid_token(storage)

            assert token is None

    def test_get_valid_oauth_token_not_expired(self):
        """Test getting valid OAuth token (sync)"""
        storage = TokenStorage()

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=False), \
             patch.object(storage, 'get_access_token', return_value="oauth_token"):

            token = get_valid_token(storage)

            assert token == "oauth_token"

    def test_get_valid_oauth_token_expired_refreshes_no_loop(self):
        """Test that expired OAuth token refreshes when no event loop exists"""
        storage = TokenStorage()

        async def mock_refresh(s):
            return True

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=True), \
             patch('oauth.token_manager.refresh_tokens', side_effect=mock_refresh), \
             patch.object(storage, 'get_access_token', return_value="refreshed_token"):

            token = get_valid_token(storage)

            assert token == "refreshed_token"

    def test_get_valid_oauth_token_refresh_fails_returns_none(self):
        """Test that failed refresh returns None (sync)"""
        storage = TokenStorage()

        async def mock_refresh(s):
            return False

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=True), \
             patch('oauth.token_manager.refresh_tokens', side_effect=mock_refresh):

            token = get_valid_token(storage)

            assert token is None

    @pytest.mark.asyncio
    async def test_get_valid_oauth_token_with_existing_loop(self):
        """Test sync token retrieval when event loop already exists"""
        storage = TokenStorage()

        # This test runs in an async context, so there's already a loop
        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=True):

            # Mock refresh_tokens to return True
            async def mock_refresh(s):
                return True

            with patch('oauth.token_manager.refresh_tokens', side_effect=mock_refresh), \
                 patch.object(storage, 'get_access_token', return_value="refreshed_token"):

                # Call in a separate thread to simulate sync context with existing loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(get_valid_token, storage)
                    token = future.result(timeout=5)

                assert token == "refreshed_token"

    def test_get_valid_oauth_token_refresh_exception_returns_none(self):
        """Test that refresh exception returns None"""
        storage = TokenStorage()

        async def mock_refresh(s):
            raise Exception("Refresh failed")

        with patch.object(storage, 'is_long_term_token', return_value=False), \
             patch.object(storage, 'is_token_expired', return_value=True), \
             patch('oauth.token_manager.refresh_tokens', side_effect=mock_refresh):

            token = get_valid_token(storage)

            assert token is None
