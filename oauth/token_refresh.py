"""OAuth token refresh functionality"""

import logging
from typing import Optional

import httpx

from settings import AUTH_BASE_TOKEN, CLIENT_ID
from utils.storage import TokenStorage

logger = logging.getLogger(__name__)


async def refresh_tokens(storage: TokenStorage) -> bool:
    """Refresh expired tokens

    Note: Long-term tokens cannot be refreshed and will return False

    Args:
        storage: Token storage instance

    Returns:
        True if refresh succeeded, False otherwise
    """
    # Check if this is a long-term token
    if storage.is_long_term_token():
        logger.warning("Cannot refresh long-term tokens - please generate a new token")
        return False

    refresh_token = storage.get_refresh_token()
    if not refresh_token:
        logger.warning("No refresh token available for refresh")
        return False

    logger.info("Attempting to refresh OAuth tokens...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{AUTH_BASE_TOKEN}/v1/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": CLIENT_ID
                },
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed with status {response.status_code}: {response.text}")
                return False

            token_data = response.json()

            # Update stored tokens
            storage.save_tokens(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data.get("expires_in", 3600)
            )

            logger.info("Successfully refreshed OAuth tokens")
            return True
        except Exception as e:
            logger.error(f"Token refresh failed with exception: {e}")
            return False
