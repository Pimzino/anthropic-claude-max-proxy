"""ChatGPT OAuth authentication module

Provides OAuth authentication for ChatGPT Plus/Pro subscriptions,
enabling access to GPT-5, GPT-5-Codex, and Codex-Mini models.
"""

from .models import TokenData, AuthBundle, PkceCodes
from .authorization import AuthorizationURLBuilder
from .pkce import PKCEManager
from .token_exchange import exchange_code_for_tokens, exchange_code_for_tokens_sync
from .token_manager import ChatGPTOAuthManager
from .token_refresh import refresh_chatgpt_tokens
from .storage import ChatGPTTokenStorage
from .utils import (
    parse_jwt_claims,
    get_effective_chatgpt_auth,
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
)

__all__ = [
    "TokenData",
    "AuthBundle",
    "PkceCodes",
    "AuthorizationURLBuilder",
    "PKCEManager",
    "exchange_code_for_tokens",
    "exchange_code_for_tokens_sync",
    "ChatGPTOAuthManager",
    "refresh_chatgpt_tokens",
    "ChatGPTTokenStorage",
    "parse_jwt_claims",
    "get_effective_chatgpt_auth",
    "convert_chat_messages_to_responses_input",
    "convert_tools_chat_to_responses",
]
