"""HTTP Request Headers and Spoofing Constants

These values are used to spoof requests as coming from the official Claude CLI
"""

from typing import Dict

# Message for system prompts when spoofing Claude Code
CLAUDE_CODE_SPOOF_MESSAGE = "You are Claude Code, Anthropic's official CLI for Claude."

# User-Agent string for API requests
USER_AGENT = "claude-cli/1.0.113 (external, cli)"

# x-app header value
X_APP_HEADER = "cli"

# Stainless SDK headers (mimics official Claude CLI behavior)
STAINLESS_HEADERS: Dict[str, str] = {
    "X-Stainless-Retry-Count": "0",
    "X-Stainless-Timeout": "600",
    "X-Stainless-Lang": "js",
    "X-Stainless-Package-Version": "0.60.0",
    "X-Stainless-OS": "Windows",
    "X-Stainless-Arch": "x64",
    "X-Stainless-Runtime": "node",
    "X-Stainless-Runtime-Version": "v22.19.0",
    "x-stainless-helper-method": "stream",
}
