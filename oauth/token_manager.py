"""OAuth token manager for retrieving valid tokens"""

import asyncio
import concurrent.futures
import logging
from typing import Optional

from utils.storage import TokenStorage
from .token_refresh import refresh_tokens

logger = logging.getLogger(__name__)


async def get_valid_token_async(storage: TokenStorage) -> Optional[str]:
    """Get a valid OAuth token for API requests (async version)

    Uses Bearer authentication for API requests.

    Args:
        storage: Token storage instance

    Returns:
        Valid access token or None if not available/expired
    """
    logger.debug("Using OAuth Bearer token for authentication")

    # For long-term tokens, just return if not expired
    if storage.is_long_term_token():
        if not storage.is_token_expired():
            return storage.get_access_token()
        else:
            logger.error("Long-term token has expired - please generate a new token")
            return None

    # For regular OAuth flow tokens, try to refresh if expired
    if not storage.is_token_expired():
        return storage.get_access_token()

    logger.info("Token expired, attempting automatic refresh...")
    # Try to refresh
    if await refresh_tokens(storage):
        return storage.get_access_token()

    logger.error("Failed to refresh token automatically")
    return None


def get_valid_token(storage: TokenStorage) -> Optional[str]:
    """Get a valid OAuth token for API requests (sync version)

    Uses Bearer authentication for API requests.
    Handles both sync and async contexts.

    Args:
        storage: Token storage instance

    Returns:
        Valid access token or None if not available/expired
    """
    logger.debug("Using OAuth Bearer token for authentication")

    # For long-term tokens, just return if not expired
    if storage.is_long_term_token():
        if not storage.is_token_expired():
            return storage.get_access_token()
        else:
            logger.error("Long-term token has expired - please generate a new token")
            return None

    # For regular OAuth flow tokens, try to refresh if expired
    if not storage.is_token_expired():
        return storage.get_access_token()

    # Try to refresh - handle both sync and async contexts
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context - use run_coroutine_threadsafe
        logger.info("Detected existing event loop, using threadsafe refresh")
        future = asyncio.run_coroutine_threadsafe(refresh_tokens(storage), loop)
        # Wait for the refresh to complete
        if future.result(timeout=30):  # 30 second timeout
            return storage.get_access_token()
        else:
            logger.error("Token refresh failed in threadsafe execution")
            return None
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        logger.info("No existing event loop, using asyncio.run for refresh")
        try:
            if asyncio.run(refresh_tokens(storage)):
                return storage.get_access_token()
            else:
                logger.error("Token refresh failed in new event loop")
                return None
        except Exception as e:
            logger.error(f"Token refresh failed with exception: {e}")
            return None
    except concurrent.futures.TimeoutError:
        logger.error("Token refresh timed out")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        return None
