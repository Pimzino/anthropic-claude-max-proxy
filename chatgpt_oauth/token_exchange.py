"""OAuth token exchange for ChatGPT authentication"""

import datetime
import json
import logging
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx

from .authorization import CLIENT_ID, OAUTH_ISSUER, REDIRECT_URI
from .models import AuthBundle, TokenData
from .pkce import PKCEManager
from .utils import parse_jwt_claims


logger = logging.getLogger(__name__)

TOKEN_ENDPOINT = f"{OAUTH_ISSUER}/oauth/token"


async def exchange_code_for_tokens(
    code: str,
    pkce_manager: PKCEManager
) -> Optional[AuthBundle]:
    """Exchange authorization code for OAuth tokens

    Args:
        code: Authorization code from OAuth callback
        pkce_manager: PKCE manager with code verifier

    Returns:
        AuthBundle with tokens, or None if exchange fails
    """
    # Load PKCE state
    if not pkce_manager.load_pkce():
        logger.error("Failed to load PKCE state for token exchange")
        return None

    if not pkce_manager.code_verifier:
        logger.error("No code verifier available for token exchange")
        return None

    # Build token exchange request
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": pkce_manager.code_verifier,
    }

    logger.info(f"Exchanging authorization code for tokens at {TOKEN_ENDPOINT}")

    try:
        async with httpx.AsyncClient() as client:
            logger.debug("Sending token exchange request...")
            response = await client.post(
                TOKEN_ENDPOINT,
                data=urlencode(data),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=60.0  # Increased from 30 to 60 seconds
            )

            logger.debug(f"Token exchange response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Token exchange failed with status {response.status_code}: {response.text}")
                return None

            payload = response.json()

    except httpx.TimeoutException as e:
        logger.error(f"Token exchange timed out after 60 seconds: {e}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Token exchange request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse token exchange response: {e}")
        return None

    # Extract tokens
    id_token = payload.get("id_token", "")
    access_token = payload.get("access_token", "")
    refresh_token = payload.get("refresh_token", "")

    if not id_token or not access_token:
        logger.error("Token exchange response missing required tokens")
        return None

    # Extract account ID from ID token
    id_token_claims = parse_jwt_claims(id_token) or {}
    auth_claims = id_token_claims.get("https://api.openai.com/auth", {})
    chatgpt_account_id = auth_claims.get("chatgpt_account_id", "")

    # Create token data
    token_data = TokenData(
        id_token=id_token,
        access_token=access_token,
        refresh_token=refresh_token,
        account_id=chatgpt_account_id,
    )

    # Create auth bundle
    last_refresh_str = (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    bundle = AuthBundle(
        api_key=None,  # ChatGPT OAuth doesn't use API keys
        token_data=token_data,
        last_refresh=last_refresh_str,
    )

    # Clear PKCE state after successful exchange
    pkce_manager.clear_pkce()

    logger.info("Successfully exchanged authorization code for tokens")
    return bundle


def exchange_code_for_tokens_sync(
    code: str,
    pkce_manager: PKCEManager
) -> Optional[AuthBundle]:
    """Synchronous version of exchange_code_for_tokens

    Args:
        code: Authorization code from OAuth callback
        pkce_manager: PKCE manager with code verifier

    Returns:
        AuthBundle with tokens, or None if exchange fails
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running, create one
        return asyncio.run(exchange_code_for_tokens(code, pkce_manager))
    else:
        # Event loop already running, use run_coroutine_threadsafe
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(
            exchange_code_for_tokens(code, pkce_manager),
            loop
        )
        try:
            return future.result(timeout=60)  # Increased from 30 to 60 seconds
        except concurrent.futures.TimeoutError:
            logger.error("Token exchange timed out")
            return None
