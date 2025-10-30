import base64
import hashlib
import json
import secrets
import tempfile
import webbrowser
from pathlib import Path
from urllib.parse import urlencode
from typing import Optional, Dict, Any
import httpx
import re

from settings import AUTH_BASE_AUTHORIZE, AUTH_BASE_TOKEN, CLIENT_ID, REDIRECT_URI, SCOPES
from storage import TokenStorage

class OAuthManager:
    """OAuth PKCE flow implementation (plan.md section 3)"""

    def __init__(self):
        self.storage = TokenStorage()
        self.code_verifier: Optional[str] = None
        self.state: Optional[str] = None
        self.pkce_file = Path(tempfile.gettempdir()) / "anthropic_oauth_pkce.json"

    @staticmethod
    def is_long_term_token_format(token: str) -> bool:
        """Check if a token matches the long-term OAuth token format (sk-ant-oat01-...)

        Args:
            token: The token string to validate

        Returns:
            True if token matches long-term format, False otherwise
        """
        if not token:
            return False
        # Long-term OAuth tokens start with sk-ant-oat01-
        return token.startswith("sk-ant-oat01-")

    @staticmethod
    def validate_token_format(token: str) -> bool:
        """Validate that a token has the correct format

        Args:
            token: The token string to validate

        Returns:
            True if token format is valid, False otherwise
        """
        if not token:
            return False
        # Check for OAuth token format (sk-ant-oat01-...)
        # Token should be at least 20 characters and contain only valid characters
        if OAuthManager.is_long_term_token_format(token):
            return len(token) > 20 and re.match(r'^sk-ant-oat01-[A-Za-z0-9_-]+$', token) is not None
        return False

    def _save_pkce(self):
        """Save PKCE values temporarily"""
        self.pkce_file.write_text(json.dumps({
            "code_verifier": self.code_verifier,
            "state": self.state
        }))

    def _load_pkce(self):
        """Load saved PKCE values"""
        if self.pkce_file.exists():
            try:
                data = json.loads(self.pkce_file.read_text())
                return data.get("code_verifier"), data.get("state")
            except (json.JSONDecodeError, IOError):
                pass
        return None, None

    def _clear_pkce(self):
        """Clear PKCE values after use"""
        if self.pkce_file.exists():
            self.pkce_file.unlink()

    def generate_pkce(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge (plan.md section 3.1)"""
        # Generate high-entropy code_verifier (43-128 chars)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        # Create code_challenge using SHA-256
        challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')

        return code_verifier, code_challenge

    def get_authorize_url(self) -> str:
        """Construct OAuth authorize URL with PKCE (plan.md section 3.2)"""
        self.code_verifier, code_challenge = self.generate_pkce()
        # OpenCode uses the verifier as the state
        self.state = self.code_verifier

        # Save PKCE values for later use
        self._save_pkce()

        params = {
            "code": "true",  # Critical parameter from OpenCode
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self.state
        }

        # Use claude.ai for authorization (Claude Pro/Max)
        return f"{AUTH_BASE_AUTHORIZE}/oauth/authorize?{urlencode(params)}"

    def get_authorize_url_for_long_term_token(self) -> str:
        """Construct OAuth authorize URL for long-term token with minimal scope

        Uses only 'user:inference' scope to allow custom expires_in parameter.
        The 'user:profile' and 'org:create_api_key' scopes don't allow custom expiry.
        """
        self.code_verifier, code_challenge = self.generate_pkce()
        # OpenCode uses the verifier as the state
        self.state = self.code_verifier

        # Save PKCE values for later use
        self._save_pkce()

        params = {
            "code": "true",  # Critical parameter from OpenCode
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": "user:inference",  # Minimal scope for long-term tokens
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self.state
        }

        # Use claude.ai for authorization (Claude Pro/Max)
        return f"{AUTH_BASE_AUTHORIZE}/oauth/authorize?{urlencode(params)}"

    def start_login_flow(self) -> str:
        """Start the OAuth login flow by opening browser (plan.md section 3.3)"""
        auth_url = self.get_authorize_url()

        # Open the authorization URL in the default browser
        webbrowser.open(auth_url)

        return auth_url

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens (plan.md section 3.4)"""
        import logging
        logger = logging.getLogger(__name__)

        # Split the code and state (they come as "code#state")
        parts = code.split("#")
        actual_code = parts[0]
        state = parts[1] if len(parts) > 1 else None

        # Load saved PKCE verifier if not already loaded
        if not self.code_verifier:
            self.code_verifier, self.state = self._load_pkce()

        if not self.code_verifier:
            raise ValueError("No PKCE verifier found. Start login flow first.")

        # Use the state from the code if available, otherwise use saved state
        if not state:
            state = self.state

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_BASE_TOKEN}/v1/oauth/token",
                json={
                    "code": actual_code,
                    "state": state,
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": self.code_verifier
                },
                headers={"Content-Type": "application/json"}
            )

        if response.status_code != 200:
            error_detail = response.text
            raise Exception(f"Token exchange failed: {response.status_code} - {error_detail}")

        token_data = response.json()

        # Store OAuth tokens (Max/Pro uses Bearer tokens, not API keys)
        logger.info("OAuth tokens obtained, storing for Bearer authentication...")
        self.storage.save_tokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data.get("expires_in", 3600)
        )

        # Clear PKCE values after successful exchange
        self._clear_pkce()
        self.code_verifier = None
        self.state = None

        logger.info("Authentication complete with OAuth Bearer tokens")
        return {"status": "success", "message": "OAuth tokens obtained successfully"}

    async def exchange_code_for_long_term_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for a long-term token (1 year validity)

        This mimics the behavior of 'claude setup-token' by requesting a 1-year token.

        Args:
            code: The authorization code from OAuth flow

        Returns:
            Dict with status, message, and the access_token for display
        """
        import logging
        logger = logging.getLogger(__name__)

        # Split the code and state (they come as "code#state")
        parts = code.split("#")
        actual_code = parts[0]
        state = parts[1] if len(parts) > 1 else None

        # Load saved PKCE verifier if not already loaded
        if not self.code_verifier:
            self.code_verifier, self.state = self._load_pkce()

        if not self.code_verifier:
            raise ValueError("No PKCE verifier found. Start login flow first.")

        # Use the state from the code if available, otherwise use saved state
        if not state:
            state = self.state

        # Request 1-year token (31536000 seconds = 365 days)
        ONE_YEAR_SECONDS = 31536000

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_BASE_TOKEN}/v1/oauth/token",
                json={
                    "code": actual_code,
                    "state": state,
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": self.code_verifier,
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
        self.storage.save_long_term_token(
            access_token=token_data["access_token"],
            expires_in=token_data.get("expires_in", ONE_YEAR_SECONDS)
        )

        # Clear PKCE values after successful exchange
        self._clear_pkce()
        self.code_verifier = None
        self.state = None

        logger.info("Long-term token setup complete")
        return {
            "status": "success",
            "message": "Long-term OAuth token obtained successfully",
            "access_token": token_data["access_token"],
            "expires_in": token_data.get("expires_in", ONE_YEAR_SECONDS)
        }

    async def refresh_tokens(self) -> bool:
        """Refresh expired tokens (plan.md section 3.5)

        Note: Long-term tokens cannot be refreshed and will return False
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check if this is a long-term token
        if self.storage.is_long_term_token():
            logger.warning("Cannot refresh long-term tokens - please generate a new token")
            return False

        refresh_token = self.storage.get_refresh_token()
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
                self.storage.save_tokens(
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    expires_in=token_data.get("expires_in", 3600)
                )

                logger.info("Successfully refreshed OAuth tokens")
                return True
            except Exception as e:
                logger.error(f"Token refresh failed with exception: {e}")
                return False

    async def get_valid_token_async(self) -> Optional[str]:
        """Get a valid OAuth token for API requests (uses Bearer authentication)"""
        import logging
        logger = logging.getLogger(__name__)

        logger.debug("Using OAuth Bearer token for authentication")

        # For long-term tokens, just return if not expired
        if self.storage.is_long_term_token():
            if not self.storage.is_token_expired():
                return self.storage.get_access_token()
            else:
                logger.error("Long-term token has expired - please generate a new token")
                return None

        # For regular OAuth flow tokens, try to refresh if expired
        if not self.storage.is_token_expired():
            return self.storage.get_access_token()

        logger.info("Token expired, attempting automatic refresh...")
        # Try to refresh
        if await self.refresh_tokens():
            return self.storage.get_access_token()

        logger.error("Failed to refresh token automatically")
        return None

    def get_valid_token(self) -> Optional[str]:
        """Get a valid OAuth token for API requests (uses Bearer authentication)"""
        import logging
        logger = logging.getLogger(__name__)

        logger.debug("Using OAuth Bearer token for authentication")

        # For long-term tokens, just return if not expired
        if self.storage.is_long_term_token():
            if not self.storage.is_token_expired():
                return self.storage.get_access_token()
            else:
                logger.error("Long-term token has expired - please generate a new token")
                return None

        # For regular OAuth flow tokens, try to refresh if expired
        if not self.storage.is_token_expired():
            return self.storage.get_access_token()

        # Try to refresh - handle both sync and async contexts
        import asyncio
        import concurrent.futures
        import logging
        logger = logging.getLogger(__name__)

        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - use run_coroutine_threadsafe
            logger.info("Detected existing event loop, using threadsafe refresh")
            future = asyncio.run_coroutine_threadsafe(self.refresh_tokens(), loop)
            # Wait for the refresh to complete
            if future.result(timeout=30):  # 30 second timeout
                return self.storage.get_access_token()
            else:
                logger.error("Token refresh failed in threadsafe execution")
                return None
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            logger.info("No existing event loop, using asyncio.run for refresh")
            try:
                if asyncio.run(self.refresh_tokens()):
                    return self.storage.get_access_token()
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