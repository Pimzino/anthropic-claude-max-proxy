"""Data models for ChatGPT OAuth authentication"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenData:
    """OAuth token data from ChatGPT authentication

    Attributes:
        id_token: JWT ID token containing user identity
        access_token: Bearer token for API authentication
        refresh_token: Token for refreshing expired access tokens
        account_id: ChatGPT account identifier
    """
    id_token: str
    access_token: str
    refresh_token: str
    account_id: str


@dataclass
class AuthBundle:
    """Complete authentication bundle with tokens and metadata

    Attributes:
        api_key: Optional API key (may be None for ChatGPT OAuth)
        token_data: OAuth token data
        last_refresh: ISO 8601 timestamp of last token refresh
    """
    api_key: Optional[str]
    token_data: TokenData
    last_refresh: str


@dataclass
class PkceCodes:
    """PKCE (Proof Key for Code Exchange) codes for OAuth flow

    Attributes:
        code_verifier: Random string used to generate code_challenge
        code_challenge: SHA256 hash of code_verifier, sent in auth request
    """
    code_verifier: str
    code_challenge: str
