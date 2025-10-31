"""OAuth token exchange functionality"""

import logging
from typing import Dict, Any

import httpx

from settings import AUTH_BASE_TOKEN, CLIENT_ID, REDIRECT_URI
from utils.storage import TokenStorage
from .pkce import PKCEManager

logger = logging.getLogger(__name__)

# One year in seconds
ONE_YEAR_SECONDS = 31536000


async def exchange_code(
    code: str,
    storage: TokenStorage,
    pkce: PKCEManager
) -> Dict[str, Any]:
    """Exchange authorization code for tokens

    Args:
        code: Authorization code from OAuth flow
        storage: Token storage instance
        pkce: PKCE manager instance

    Returns:
        Dict with status and message

    Raises:
        ValueError: If PKCE verifier not found
        Exception: If token exchange fails
    """
    # Split the code and state (they come as "code#state")
    parts = code.split("#")
    actual_code = parts[0]
    state = parts[1] if len(parts) > 1 else None

    # Load saved PKCE verifier if not already loaded
    if not pkce.code_verifier:
        pkce.code_verifier, pkce.state = pkce.load_pkce()

    if not pkce.code_verifier:
        raise ValueError("No PKCE verifier found. Start login flow first.")

    # Use the state from the code if available, otherwise use saved state
    if not state:
        state = pkce.state

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AUTH_BASE_TOKEN}/v1/oauth/token",
            json={
                "code": actual_code,
                "state": state,
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": pkce.code_verifier
            },
            headers={"Content-Type": "application/json"}
        )

    if response.status_code != 200:
        error_detail = response.text
        raise Exception(f"Token exchange failed: {response.status_code} - {error_detail}")

    token_data = response.json()

    # Store OAuth tokens (Max/Pro uses Bearer tokens, not API keys)
    logger.info("OAuth tokens obtained, storing for Bearer authentication...")
    storage.save_tokens(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 3600)
    )

    # Clear PKCE values after successful exchange
    pkce.clear_pkce()

    logger.info("Authentication complete with OAuth Bearer tokens")
    return {"status": "success", "message": "OAuth tokens obtained successfully"}


async def exchange_code_for_long_term_token(
    code: str,
    storage: TokenStorage,
    pkce: PKCEManager
) -> Dict[str, Any]:
    """Exchange authorization code for a long-term token (1 year validity)

    This mimics the behavior of 'claude setup-token' by requesting a 1-year token.

    Args:
        code: Authorization code from OAuth flow
        storage: Token storage instance
        pkce: PKCE manager instance

    Returns:
        Dict with status, message, access_token, and expires_in

    Raises:
        ValueError: If PKCE verifier not found
        Exception: If token exchange fails
    """
    # Split the code and state (they come as "code#state")
    parts = code.split("#")
    actual_code = parts[0]
    state = parts[1] if len(parts) > 1 else None

    # Load saved PKCE verifier if not already loaded
    if not pkce.code_verifier:
        pkce.code_verifier, pkce.state = pkce.load_pkce()

    if not pkce.code_verifier:
        raise ValueError("No PKCE verifier found. Start login flow first.")

    # Use the state from the code if available, otherwise use saved state
    if not state:
        state = pkce.state

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AUTH_BASE_TOKEN}/v1/oauth/token",
            json={
                "code": actual_code,
                "state": state,
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": pkce.code_verifier,
                "expires_in": ONE_YEAR_SECONDS  # Request 1-year token
            },
            headers={"Content-Type": "application/json"}
        )

    if response.status_code != 200:
        error_detail = response.text
        raise Exception(f"Token exchange failed: {response.status_code} - {error_detail}")

    token_data = response.json()

    # Store as long-term token
    logger.info("Long-term OAuth token obtained (1 year validity)")
    storage.save_long_term_token(
        access_token=token_data["access_token"],
        expires_in=token_data.get("expires_in", ONE_YEAR_SECONDS)
    )

    # Clear PKCE values after successful exchange
    pkce.clear_pkce()

    logger.info("Long-term token setup complete")
    return {
        "status": "success",
        "message": "Long-term OAuth token obtained successfully",
        "access_token": token_data["access_token"],
        "expires_in": token_data.get("expires_in", ONE_YEAR_SECONDS)
    }
