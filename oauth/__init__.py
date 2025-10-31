"""OAuth authentication package for Anthropic API"""

from typing import Optional, Dict, Any

from utils.storage import TokenStorage
from .validators import is_long_term_token_format, validate_token_format
from .pkce import PKCEManager
from .authorization import AuthorizationURLBuilder
from .token_exchange import exchange_code, exchange_code_for_long_term_token
from .token_refresh import refresh_tokens
from .token_manager import get_valid_token, get_valid_token_async


class OAuthManager:
    """OAuth PKCE flow implementation

    This class orchestrates the OAuth authentication flow including:
    - PKCE generation and management
    - Authorization URL construction
    - Token exchange
    - Token refresh
    - Token validation and retrieval
    """

    def __init__(self):
        self.storage = TokenStorage()
        self.pkce = PKCEManager()
        self.auth_builder = AuthorizationURLBuilder(self.pkce)

    # Static methods for token validation
    @staticmethod
    def is_long_term_token_format(token: str) -> bool:
        """Check if a token matches the long-term OAuth token format

        Args:
            token: The token string to validate

        Returns:
            True if token matches long-term format, False otherwise
        """
        return is_long_term_token_format(token)

    @staticmethod
    def validate_token_format(token: str) -> bool:
        """Validate that a token has the correct format

        Args:
            token: The token string to validate

        Returns:
            True if token format is valid, False otherwise
        """
        return validate_token_format(token)

    # PKCE management (delegate to PKCEManager)
    def generate_pkce(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        return self.pkce.generate_pkce()

    # Authorization URLs
    def get_authorize_url(self) -> str:
        """Construct OAuth authorize URL with PKCE

        Returns:
            Full authorization URL
        """
        return self.auth_builder.get_authorize_url()

    def get_authorize_url_for_long_term_token(self) -> str:
        """Construct OAuth authorize URL for long-term token

        Returns:
            Full authorization URL for long-term token
        """
        return self.auth_builder.get_authorize_url_for_long_term_token()

    def start_login_flow(self) -> str:
        """Start the OAuth login flow by opening browser

        Returns:
            Authorization URL that was opened
        """
        return self.auth_builder.start_login_flow()

    # Token exchange
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens

        Args:
            code: Authorization code from OAuth flow

        Returns:
            Dict with status and message
        """
        return await exchange_code(code, self.storage, self.pkce)

    async def exchange_code_for_long_term_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for a long-term token

        Args:
            code: Authorization code from OAuth flow

        Returns:
            Dict with status, message, access_token, and expires_in
        """
        return await exchange_code_for_long_term_token(code, self.storage, self.pkce)

    # Token refresh
    async def refresh_tokens(self) -> bool:
        """Refresh expired tokens

        Returns:
            True if refresh succeeded, False otherwise
        """
        return await refresh_tokens(self.storage)

    # Token retrieval
    async def get_valid_token_async(self) -> Optional[str]:
        """Get a valid OAuth token for API requests (async version)

        Returns:
            Valid access token or None if not available/expired
        """
        return await get_valid_token_async(self.storage)

    def get_valid_token(self) -> Optional[str]:
        """Get a valid OAuth token for API requests (sync version)

        Returns:
            Valid access token or None if not available/expired
        """
        return get_valid_token(self.storage)


__all__ = [
    "OAuthManager",
    "is_long_term_token_format",
    "validate_token_format",
]
