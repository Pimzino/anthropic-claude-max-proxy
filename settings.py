import os
from pathlib import Path
from config_loader import get_config_loader

# Get the config loader instance
config = get_config_loader()

# Server configuration
PORT = config.get("PORT", "server.port", 8081)
LOG_LEVEL = config.get("LOG_LEVEL", "server.log_level", "info")
BIND_ADDRESS = config.get("BIND_ADDRESS", "server.bind_address", "0.0.0.0")

# Model configuration
DEFAULT_MODEL = config.get("DEFAULT_MODEL", "models.default", "claude-sonnet-4-5-20250929")

# Anthropic API configuration (hardcoded - not user configurable)
ANTHROPIC_VERSION = "2023-06-01"
# Beta features matching OpenCode main provider (oauth-2025-04-20 excluded for compatibility)
ANTHROPIC_BETA = "claude-code-20250219,interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14"
API_BASE = "https://api.anthropic.com"
REQUEST_TIMEOUT = config.get("REQUEST_TIMEOUT", "api.request_timeout", 120.0)

# OAuth configuration (hardcoded - not user configurable)
# Max/Pro OAuth: claude.ai for authorization, console.anthropic.com for token exchange
# Uses Bearer tokens (not API keys) for authentication
AUTH_BASE_AUTHORIZE = "https://claude.ai"
AUTH_BASE_TOKEN = "https://console.anthropic.com"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
SCOPES = "org:create_api_key user:profile user:inference"

# Thinking configuration (legacy - clients handle directly now)
THINKING_FORCE_ENABLED = config.get("THINKING_FORCE_ENABLED", "thinking.force_enabled", False)
THINKING_DEFAULT_BUDGET = config.get("THINKING_DEFAULT_BUDGET", "thinking.default_budget_tokens", 16000)

# Thinking parameters handled directly by clients (no custom variants)

# Pure Anthropic proxy - native endpoint always enabled

# Token storage
TOKEN_FILE = config.get("TOKEN_FILE", "storage.token_file", str(Path.home() / ".anthropic-claude-max-proxy" / "tokens.json"))