"""OAuth authorization URL construction"""

import webbrowser
from urllib.parse import urlencode

from settings import AUTH_BASE_AUTHORIZE, CLIENT_ID, REDIRECT_URI, SCOPES
from .pkce import PKCEManager


class AuthorizationURLBuilder:
    """Builds OAuth authorization URLs with PKCE"""

    def __init__(self, pkce_manager: PKCEManager):
        self.pkce = pkce_manager

    def get_authorize_url(self) -> str:
        """Construct OAuth authorize URL with PKCE for standard scope

        Returns:
            Full authorization URL
        """
        self.pkce.code_verifier, code_challenge = self.pkce.generate_pkce()
        # OpenCode uses the verifier as the state
        self.pkce.state = self.pkce.code_verifier

        # Save PKCE values for later use
        self.pkce.save_pkce()

        params = {
            "code": "true",  # Critical parameter from OpenCode
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self.pkce.state
        }

        # Use claude.ai for authorization (Claude Pro/Max)
        return f"{AUTH_BASE_AUTHORIZE}/oauth/authorize?{urlencode(params)}"

    def get_authorize_url_for_long_term_token(self) -> str:
        """Construct OAuth authorize URL for long-term token with minimal scope

        Uses only 'user:inference' scope to allow custom expires_in parameter.
        The 'user:profile' and 'org:create_api_key' scopes don't allow custom expiry.

        Returns:
            Full authorization URL for long-term token
        """
        self.pkce.code_verifier, code_challenge = self.pkce.generate_pkce()
        # OpenCode uses the verifier as the state
        self.pkce.state = self.pkce.code_verifier

        # Save PKCE values for later use
        self.pkce.save_pkce()

        params = {
            "code": "true",  # Critical parameter from OpenCode
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": "user:inference",  # Minimal scope for long-term tokens
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self.pkce.state
        }

        # Use claude.ai for authorization (Claude Pro/Max)
        return f"{AUTH_BASE_AUTHORIZE}/oauth/authorize?{urlencode(params)}"

    def start_login_flow(self) -> str:
        """Start the OAuth login flow by opening browser

        Returns:
            Authorization URL that was opened
        """
        auth_url = self.get_authorize_url()

        # Open the authorization URL in the default browser
        webbrowser.open(auth_url)

        return auth_url
