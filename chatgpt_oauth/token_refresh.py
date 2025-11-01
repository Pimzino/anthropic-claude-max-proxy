"""OAuth token refresh for ChatGPT authentication"""

import datetime
import json
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from .authorization import CLIENT_ID, OAUTH_ISSUER
from .utils import parse_jwt_claims


logger = logging.getLogger(__name__)

TOKEN_ENDPOINT = f"{OAUTH_ISSUER}/oauth/token"


async def refresh_chatgpt_tokens(
    refresh_token: str
) -> Optional[dict]:
    """Refresh expired ChatGPT OAuth tokens

    Args:
        refresh_token: Refresh token from previous authentication

    Returns:
        Dictionary with new tokens, or None if refresh fails
    """
    if not refresh_token:
        logger.error("No refresh token provided")
        return None

    # Build refresh request
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "scope": "openid profile email",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TOKEN_ENDPOINT,
                data=urlencode(data),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed with status {response.status_code}: {response.text}")
                return None

            payload = response.json()

    except httpx.RequestError as e:
        logger.error(f"Token refresh request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse token refresh response: {e}")
        return None

    # Extract tokens
    id_token = payload.get("id_token")
    access_token = payload.get("access_token")
    new_refresh_token = payload.get("refresh_token") or refresh_token

    if not id_token or not access_token:
        logger.error("Token refresh response missing required tokens")
        return None

    # Extract account ID from ID token
    id_claims = parse_jwt_claims(id_token) or {}
    auth_claims = id_claims.get("https://api.openai.com/auth", {})
    account_id = auth_claims.get("chatgpt_account_id")

    logger.info("Successfully refreshed ChatGPT OAuth tokens")

    return {
        "id_token": id_token,
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "account_id": account_id,
    }


def should_refresh_access_token(
    access_token: Optional[str],
    last_refresh: Optional[str]
) -> bool:
    """Check if access token should be refreshed

    Args:
        access_token: Current access token
        last_refresh: ISO 8601 timestamp of last refresh

    Returns:
        True if token should be refreshed
    """
    if not access_token:
        return True

    # Check token expiry from JWT claims
    claims = parse_jwt_claims(access_token) or {}
    exp = claims.get("exp")
    now = datetime.datetime.now(datetime.timezone.utc)

    if isinstance(exp, (int, float)):
        try:
            expiry = datetime.datetime.fromtimestamp(float(exp), datetime.timezone.utc)
            # Refresh if expiring within 5 minutes
            if expiry <= now + datetime.timedelta(minutes=5):
                return True
        except (OverflowError, OSError, ValueError):
            pass

    # Check last refresh time
    if isinstance(last_refresh, str):
        try:
            if last_refresh.endswith("Z"):
                last_refresh = last_refresh[:-1] + "+00:00"
            refreshed_at = datetime.datetime.fromisoformat(last_refresh)
            if refreshed_at.tzinfo is None:
                refreshed_at = refreshed_at.replace(tzinfo=datetime.timezone.utc)
            refreshed_at = refreshed_at.astimezone(datetime.timezone.utc)

            # Refresh if last refresh was over 55 minutes ago
            if refreshed_at <= now - datetime.timedelta(minutes=55):
                return True
        except (ValueError, AttributeError):
            pass

    return False
