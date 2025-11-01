"""OAuth token manager for ChatGPT authentication"""

import datetime
import logging
from typing import Optional

from .storage import ChatGPTTokenStorage
from .token_refresh import refresh_chatgpt_tokens, should_refresh_access_token


logger = logging.getLogger(__name__)


class ChatGPTOAuthManager:
    """Manages ChatGPT OAuth tokens with automatic refresh"""

    def __init__(self, storage: Optional[ChatGPTTokenStorage] = None):
        """Initialize OAuth manager

        Args:
            storage: Token storage instance (creates new if None)
        """
        self.storage = storage or ChatGPTTokenStorage()

    async def get_valid_token_async(self) -> Optional[str]:
        """Get a valid OAuth access token (async version)

        Automatically refreshes expired tokens if refresh token is available.

        Returns:
            Valid access token, or None if not available
        """
        data = self.storage.load_tokens()
        if not data:
            logger.debug("No ChatGPT tokens available")
            return None

        tokens = data.get("tokens", {})
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        last_refresh = data.get("last_refresh")

        # Check if token needs refresh
        if not should_refresh_access_token(access_token, last_refresh):
            return access_token

        # Try to refresh
        if not refresh_token:
            logger.error("Access token expired and no refresh token available")
            return None

        logger.info("ChatGPT access token expired, attempting refresh...")

        refreshed = await refresh_chatgpt_tokens(refresh_token)
        if not refreshed:
            logger.error("Failed to refresh ChatGPT access token")
            return None

        # Update stored tokens
        updated_tokens = {
            "id_token": refreshed.get("id_token"),
            "access_token": refreshed.get("access_token"),
            "refresh_token": refreshed.get("refresh_token"),
            "account_id": refreshed.get("account_id"),
        }

        updated_data = {
            "tokens": updated_tokens,
            "last_refresh": (
                datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        }

        if self.storage.save_tokens(updated_data):
            logger.info("Successfully refreshed and saved ChatGPT tokens")
            return updated_tokens["access_token"]
        else:
            logger.error("Failed to save refreshed tokens")
            return None

    def get_valid_token(self) -> Optional[str]:
        """Get a valid OAuth access token (sync version)

        Automatically refreshes expired tokens if refresh token is available.

        Returns:
            Valid access token, or None if not available
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(self.get_valid_token_async())
        else:
            # Event loop already running, use run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self.get_valid_token_async(),
                loop
            )
            try:
                return future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                logger.error("Token refresh timed out")
                return None

    async def refresh_tokens(self) -> bool:
        """Manually refresh tokens

        Returns:
            True if refresh was successful
        """
        data = self.storage.load_tokens()
        if not data:
            logger.error("No tokens to refresh")
            return False

        tokens = data.get("tokens", {})
        refresh_token = tokens.get("refresh_token")

        if not refresh_token:
            logger.error("No refresh token available")
            return False

        refreshed = await refresh_chatgpt_tokens(refresh_token)
        if not refreshed:
            return False

        # Update stored tokens
        updated_tokens = {
            "id_token": refreshed.get("id_token"),
            "access_token": refreshed.get("access_token"),
            "refresh_token": refreshed.get("refresh_token"),
            "account_id": refreshed.get("account_id"),
        }

        updated_data = {
            "tokens": updated_tokens,
            "last_refresh": (
                datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        }

        return self.storage.save_tokens(updated_data)

    def get_account_id(self) -> Optional[str]:
        """Get ChatGPT account ID

        Returns:
            Account ID string, or None if not available
        """
        return self.storage.get_account_id()

    def get_auth_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Get authentication credentials for API requests

        Returns:
            Tuple of (access_token, account_id)
        """
        token = self.get_valid_token()
        account_id = self.storage.get_account_id()
        return token, account_id

    async def get_auth_credentials_async(self) -> tuple[Optional[str], Optional[str]]:
        """Get authentication credentials for API requests (async version)

        Returns:
            Tuple of (access_token, account_id)
        """
        token = await self.get_valid_token_async()
        account_id = self.storage.get_account_id()
        return token, account_id