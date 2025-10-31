import os
from pathlib import Path
from config.loader import get_config_loader

# Get the config loader instance
config = get_config_loader()

# Server configuration
PORT = config.get("PORT", 8081)
LOG_LEVEL = config.get("LOG_LEVEL", "info")
BIND_ADDRESS = config.get("BIND_ADDRESS", "0.0.0.0")

# Model configuration
DEFAULT_MODEL = config.get("DEFAULT_MODEL", "claude-sonnet-4-5-20250929")

# Anthropic API configuration (hardcoded - not user configurable)
ANTHROPIC_VERSION = "2023-06-01"
# Beta features are now conditionally added based on request features:
# - oauth-2025-04-20: Always included (required for Bearer token auth)
# - context-1m-2025-08-07: Added when using -1m model variants (requires tier 4)
# - interleaved-thinking-2025-05-14: Added when thinking is enabled
ANTHROPIC_BETA = "oauth-2025-04-20"  # Base beta header (others added conditionally)
API_BASE = "https://api.anthropic.com"

# Timeout configuration (industry-standard values)
# Connection timeout: Time to establish TCP connection (industry standard: 5-10s)
CONNECT_TIMEOUT = config.get("CONNECT_TIMEOUT", 10.0)
# Read timeout: Time between receiving data chunks, important for detecting stalled streams
READ_TIMEOUT = config.get("READ_TIMEOUT", 60.0)
# Request timeout: Total timeout for non-streaming requests
REQUEST_TIMEOUT = config.get("REQUEST_TIMEOUT", 120.0)
# Stream timeout: Total timeout for streaming requests (LLMs can take longer)
STREAM_TIMEOUT = config.get("STREAM_TIMEOUT", 600.0)

# Stream tracing / debugging
STREAM_TRACE_ENABLED = config.get("STREAM_TRACE_ENABLED", False)
STREAM_TRACE_DIR = config.get("STREAM_TRACE_DIR", "stream_traces")
STREAM_TRACE_MAX_BYTES = config.get("STREAM_TRACE_MAX_BYTES", 262144)

# OAuth configuration (hardcoded - not user configurable)
# Max/Pro OAuth: claude.ai for authorization, console.anthropic.com for token exchange
# Uses Bearer tokens (not API keys) for authentication
AUTH_BASE_AUTHORIZE = "https://claude.ai"
AUTH_BASE_TOKEN = "https://console.anthropic.com"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
SCOPES = "org:create_api_key user:profile user:inference"

# Thinking configuration (legacy - clients handle directly now)
THINKING_FORCE_ENABLED = config.get("THINKING_FORCE_ENABLED", False)
THINKING_DEFAULT_BUDGET = config.get("THINKING_DEFAULT_BUDGET", 16000)

# Thinking parameters handled directly by clients (no custom variants)

# Pure Anthropic proxy - native endpoint always enabled

# Token storage
TOKEN_FILE = config.get("TOKEN_FILE", str(Path.home() / ".anthropic-claude-max-proxy" / "tokens.json"))

# Headless mode configuration
# Long-term OAuth token from environment (e.g., from claude setup-token)
ANTHROPIC_OAUTH_TOKEN = os.getenv("ANTHROPIC_OAUTH_TOKEN", None)