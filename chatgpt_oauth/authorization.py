"""OAuth authorization URL construction for ChatGPT"""

import webbrowser
from urllib.parse import urlencode
from typing import Optional

from .pkce import PKCEManager


# ChatGPT OAuth configuration
OAUTH_ISSUER = "https://auth.openai.com"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPES = "openid profile email offline_access"


class AuthorizationURLBuilder:
    """Builds OAuth authorization URLs with PKCE for ChatGPT authentication"""

    def __init__(self, pkce_manager: Optional[PKCEManager] = None):
        """Initialize authorization URL builder

        Args:
            pkce_manager: PKCE manager instance (creates new if None)
        """
        self.pkce = pkce_manager or PKCEManager()

    def get_authorize_url(self) -> str:
        """Construct OAuth authorize URL with PKCE

        Returns:
            Full authorization URL for ChatGPT OAuth flow
        """
        # Generate PKCE codes
        self.pkce.code_verifier, code_challenge = self.pkce.generate_pkce()

        # Use code verifier as state (following ChatMock pattern)
        self.pkce.state = self.pkce.code_verifier

        # Save PKCE values for later use
        self.pkce.save_pkce()

        # Build authorization parameters
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self.pkce.state,
            # ChatGPT-specific parameters
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
        }

        return f"{OAUTH_ISSUER}/oauth/authorize?{urlencode(params)}"

    def start_login_flow(self) -> str:
        """Start the OAuth login flow by opening browser

        Returns:
            Authorization URL that was opened
        """
        auth_url = self.get_authorize_url()

        # Open the authorization URL in the default browser
        webbrowser.open(auth_url)

        return auth_url
