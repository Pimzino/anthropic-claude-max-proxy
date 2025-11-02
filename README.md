# LLM Subscription Proxy

OpenAI-compatible proxy for Claude Pro/Max and ChatGPT Plus/Pro subscriptions using OAuth.

## Overview

Access your Claude and ChatGPT subscriptions through a unified OpenAI-compatible API. Route requests to multiple providers through a single endpoint without changing your client configuration.

**Supported Providers:**
- 🤖 **Anthropic Claude** (Pro/Max via OAuth)
- 💬 **ChatGPT** (Plus/Pro via OAuth)
- 🔌 **Custom Providers** (any OpenAI-compatible API)

## SUPPORT MY WORK
<a href="https://buymeacoffee.com/Pimzino" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## DISCLAIMER

**FOR EDUCATIONAL PURPOSES ONLY**

This tool:
- Is NOT affiliated with or endorsed by Anthropic or OpenAI
- Uses undocumented OAuth flows from Claude Code and ChatGPT Codex
- May violate Terms of Service
- Could stop working at any time without notice
- Comes with NO WARRANTY or support

**USE AT YOUR OWN RISK. The authors assume no liability for any consequences.**

For official access, use official APIs with console API keys.

## Implementation Details

### Anthropic Claude

This proxy is aligned with the [OpenCode](https://github.com/anthropics/opencode) implementation:

**API Endpoint:**
- Base URL: `https://api.anthropic.com/v1/messages` (no query parameters)
- Uses header-based beta features

**Beta Features (Messages API):**
- `oauth-2025-04-20` - OAuth authentication support (always included, required for Bearer tokens)
- `context-1m-2025-08-07` - 1M context window (conditionally added when using `-1m` model variants, requires tier 4)
- `interleaved-thinking-2025-05-14` - Extended thinking support (conditionally added when thinking is enabled)

**OAuth Flow (Max/Pro authentication):**
1. User authorizes via `https://claude.ai/oauth/authorize` (with `code=true` parameter)
2. Redirects to `https://console.anthropic.com/oauth/code/callback`
3. Authorization code exchanged at `https://console.anthropic.com/v1/oauth/token`
4. OAuth access token used with Bearer authorization for all requests

**Authentication:**
- Uses OAuth Bearer tokens with `authorization: Bearer <token>` header
- All requests authenticated via OAuth access tokens from the flow above

**Cache Control:**
- Automatic ephemeral cache control on system messages
- Automatic caching on the last 2 user messages for optimal performance

### ChatGPT

This proxy uses the ChatGPT Codex OAuth flow:

**API Endpoint:**
- Base URL: `https://chatgpt.com/backend-api/codex/responses`
- Uses Responses API format (converted from OpenAI format)

**OAuth Flow (Plus/Pro authentication):**
1. User authorizes via `https://auth.openai.com/oauth/authorize`
2. Redirects to `http://localhost:1455/auth/callback`
3. Authorization code exchanged at `https://auth.openai.com/oauth/token`
4. OAuth access token used with Bearer authorization for all requests

**Authentication:**
- Uses OAuth Bearer tokens with `authorization: Bearer <token>` header
- Includes `chatgpt-account-id` header for account identification
- Tokens stored separately in `~/.chatgpt-local/tokens.json`

**Features:**
- Session-based prompt caching for efficiency
- Reasoning support with configurable effort levels (minimal/low/medium/high)
- Reasoning summaries (auto/concise/detailed/none)
- Vision support (text and image inputs)
- Tool/function calling support

**Model Specifications:**
- **GPT-5**: 400K context, 128K max output, reasoning + vision
- **GPT-5-Codex**: 400K context, 128K max output, coding-optimized
- **Codex-Mini**: 128K context, 16K max output, faster variant

## Prerequisites

- **For Claude models:** Active Claude Pro or Claude Max subscription
- **For ChatGPT models:** Active ChatGPT Plus or ChatGPT Pro subscription
- **For custom models:** API keys from your chosen providers
- Python 3.9+
- pip

## Quick Start

1. **Virtual Environment Setup (Recommended)**
```bash
python -m venv venv
```

2. **Install:**
```bash
venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

3. **Configure (optional):**
```bash
cp .env.example .env
# Edit .env to customize settings (port, timeouts, etc.)
```

4. **Run:**
```bash
python cli.py
# Or with custom bind address:
python cli.py --bind 127.0.0.1
```

5. **Authenticate:**
- Select option 2 (Authentication)
- Choose provider (Anthropic Claude or ChatGPT)
- Browser opens automatically
- Complete login at claude.ai or auth.openai.com
- Copy/paste the authorization code or callback URL
- Paste in terminal

6. **Start proxy:**
- Select option 1 (Start Proxy Server)
- Server runs at `http://0.0.0.0:8081` (default, listens on all interfaces)

## Headless Mode

The proxy supports headless (non-interactive) operation for CI/CD, Docker containers, and production deployments.

### Authentication Methods

#### Method 1: Long-Term OAuth Token (Recommended for Headless)

Generate a **true long-term token** valid for **1 year** (365 days):

```bash
# Interactive setup
python cli.py --setup-token

# Or via menu option 6 in interactive mode
python cli.py
# Select option 6 (Setup Long-Term Token)
```

This will:
1. Open your browser for OAuth authentication
2. Generate a 1-year token
3. **Automatically save it** to your token file
4. Display the token for use on other machines

**The token is immediately ready to use!** After running `--setup-token`, you can run:

```bash
python cli.py --headless
```

No additional configuration needed on the same machine.

**How it works:** The `--setup-token` command requests a 1-year token by including `"expires_in": 31536000` (365 days in seconds) in the OAuth token exchange request, exactly like `claude setup-token` does. This is a **real long-term token**, not just a regular short-lived token.

#### Method 2: Use Existing OAuth Flow Tokens

Authenticate once interactively, then run headless:

```bash
# First time: authenticate interactively
python cli.py
# Select option 2 to login

# Then run headless with saved tokens
python cli.py --headless
```

**Note:** Regular OAuth flow tokens are short-lived (~1 hour) but include a refresh token for automatic renewal.

### Running in Headless Mode

#### Using Environment Variable

```bash
# Set the token
export ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."

# Run headless
python cli.py --headless
```

#### Using CLI Argument

```bash
python cli.py --headless --token "sk-ant-oat01-..."
```

#### Using Saved Tokens

```bash
# If you've already authenticated via interactive mode
python cli.py --headless
```

### Headless Mode Options

```bash
# Basic headless mode (auto-starts server)
python cli.py --headless

# Headless with custom bind address
python cli.py --headless --bind 127.0.0.1

# Headless without auto-starting server
python cli.py --headless --no-auto-start

# Headless with debug logging
python cli.py --headless --debug

# Provide token directly
python cli.py --headless --token "sk-ant-oat01-..."
```

### Docker/Container Usage

Example Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Set token via environment variable
ENV ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."

CMD ["python", "cli.py", "--headless"]
```

Or use docker-compose:

```yaml
version: '3.8'
services:
  claude-proxy:
    build: .
    ports:
      - "8081:8081"
    environment:
      - ANTHROPIC_OAUTH_TOKEN=${ANTHROPIC_OAUTH_TOKEN}
    command: python cli.py --headless
```

### Token Types Comparison

| Feature | OAuth Flow Tokens | Long-Term Tokens |
|---------|------------------|------------------|
| **Validity** | ~1 hour | ~1 year |
| **Auto-Refresh** | ✅ Yes (with refresh token) | ❌ No |
| **Best For** | Interactive use | Headless/Production |
| **Setup** | Browser OAuth flow | Same OAuth flow |
| **Storage** | Automatic | Manual or env var |

### Headless Mode Behavior

When running in headless mode:
1. Checks for authentication (env var, CLI arg, or stored tokens)
2. Validates and saves token if provided
3. Auto-refreshes expired OAuth flow tokens (if refresh token available)
4. Starts server automatically (unless `--no-auto-start`)
5. Runs in foreground with graceful shutdown on SIGINT/SIGTERM
6. Exits with error if authentication fails

## Client Configuration

The proxy supports **OpenAI-compatible API format** for all providers:

### OpenAI-Compatible API (Recommended)

Configure your OpenAI API client:

- **Base URL:** `http://<proxy-host>:8081/v1`
- **API Key:** Any non-empty string (e.g., "dummy")
- **Models:**
  - Claude: `claude-sonnet-4-20250514`, `claude-opus-4-20250514`, etc.
  - ChatGPT: `gpt5`, `gpt5codex`, `codexmini`
    - Aliases (also accepted): `gpt-5`, `gpt-5-codex`, `codex-mini-latest`
  - Custom: Your configured model IDs
- **Endpoint:** `/v1/chat/completions`

**Example:**
```python
from openai import OpenAI

client = OpenAI(
    api_key="dummy",
    base_url="http://localhost:8081/v1"
)

# Use Claude
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Use ChatGPT
response = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Use custom model
response = client.chat.completions.create(
    model="glm-4.6",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Native Anthropic API

For Claude-specific features, use the native Anthropic format:

- **Base URL:** `http://<proxy-host>:8081`
- **API Key:** Any non-empty string (e.g., "dummy")
- **Model:** `claude-sonnet-4-20250514` (or any available Claude model)
- **Endpoint:** `/v1/messages`

The OpenAI compatibility layer supports:
- ✅ Chat completions (streaming and non-streaming)
- ✅ Tool/Function calling (including parallel tool calls)
- ✅ Vision/Image inputs (URL and base64)
- ✅ System messages
- ✅ All standard parameters (temperature, top_p, max_tokens, stop sequences)
- ✅ Reasoning/Thinking support via `reasoning_effort` parameter or model variants

## Available Models

### Anthropic Claude Models
All Claude models available with your Pro/Max subscription:
- `claude-sonnet-4-20250514`
- `claude-opus-4-20250514`
- `claude-haiku-4-20250514`
- Plus reasoning and 1M context variants

### ChatGPT Models
All GPT models available with your Plus/Pro subscription:
- `gpt5` (400K context, 128K output)
- `gpt5codex` (optimized for coding)
- `codexmini` (faster, smaller variant)
- Plus reasoning variants: `-reasoning-minimal`, `-reasoning-low`, `-reasoning-medium`, `-reasoning-high`
- Aliases: `gpt-5`, `gpt-5-codex`, `codex-mini-latest` (also accepted)

### Custom Models
Any OpenAI-compatible models configured in `models.json`

## Custom Models Configuration

Beyond Claude and ChatGPT, the proxy supports routing requests to **additional OpenAI-compatible providers** (like Z.AI, OpenRouter, etc.). This allows you to use multiple providers through a single proxy endpoint.

### Setup

1. **Create models.json:**
```bash
cp models.example.json models.json
```

2. **Configure your custom models:**

Edit `models.json` and add your custom model configurations:

```json
{
  "custom_models": [
    {
      "id": "glm-4.6",
      "base_url": "https://api.z.ai/api/coding/paas/v4",
      "api_key": "YOUR_Z_AI_API_KEY_HERE",
      "context_length": 200000,
      "max_completion_tokens": 8192,
      "supports_reasoning": true,
      "owned_by": "zhipu-ai"
    }
  ]
}
```

### Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ Yes | Model identifier used in API requests |
| `base_url` | ✅ Yes | OpenAI-compatible API endpoint (e.g., `https://api.provider.com/v1`) |
| `api_key` | ✅ Yes | API key for authentication |
| `context_length` | ❌ No | Maximum context window in tokens (default: 200000) |
| `max_completion_tokens` | ❌ No | Maximum completion tokens (default: 4096) |
| `supports_reasoning` | ❌ No | Whether model supports reasoning/thinking (default: false) |
| `owned_by` | ❌ No | Model provider name (default: "custom") |

### Usage

Once configured, custom models appear in the `/v1/models` endpoint alongside Claude and ChatGPT models:

```python
# Using Z.AI GLM-4.6 through the proxy
response = client.chat.completions.create(
    model="glm-4.6",  # Your custom model ID
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### How It Works

- **Claude models** → Anthropic API with OAuth
- **ChatGPT models** → ChatGPT Responses API with OAuth
- **Custom models** → Direct passthrough to configured endpoint with API key
- All models accessible through the same OpenAI-compatible interface
- Requests are automatically routed based on model name

### Example: Z.AI Coding Plan

The Z.AI Coding Plan provides access to GLM-4.6 with an OpenAI-compatible API. See [Z.AI Documentation](https://docs.z.ai/devpack/tool/others) for details.

```json
{
  "custom_models": [
    {
      "id": "glm-4.6",
      "base_url": "https://api.z.ai/api/coding/paas/v4",
      "api_key": "your-z-ai-api-key",
      "context_length": 200000,
      "max_completion_tokens": 8192,
      "supports_reasoning": true,
      "owned_by": "zhipu-ai"
    }
  ]
}
```

**Note:** The `models.json` file is automatically gitignored to prevent accidentally committing API keys.

## Reasoning/Thinking Support

The proxy supports Anthropic's extended thinking mode through OpenAI-compatible APIs. Thinking is **only enabled when explicitly requested**.

### Reasoning Budget Mapping

| OpenAI `reasoning_effort` | Anthropic `thinking.budget_tokens` |
|---------------------------|-------------------------------------|
| `low`                     | 8,000 tokens                        |
| `medium`                  | 16,000 tokens                       |
| `high`                    | 32,000 tokens                       |

### Two Ways to Enable Reasoning

#### 1. Using `reasoning_effort` Parameter

```python
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Solve this complex problem..."}],
    reasoning_effort="high"  # Enables thinking with 32k token budget
)
```

#### 2. Using Reasoning Model Variants

```
```

## Usage Examples

### Using with OpenAI Python SDK

```python
import openai

client = openai.OpenAI(
    api_key="dummy",
    base_url="http://localhost:8081/v1"
)

# ===== Claude Models =====
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=1000
)

# Claude with reasoning
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
    reasoning_effort="high",
    max_tokens=4000
)

# ===== ChatGPT Models =====
# Note: Examples use aliases (gpt-5) for brevity, but gpt5 is the advertised model ID
response = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "Write a Python function"}],
    max_tokens=2000
)

# ChatGPT with reasoning variant
response = client.chat.completions.create(
    model="gpt-5-high",  # High reasoning effort
    messages=[{"role": "user", "content": "Solve this logic puzzle"}],
    max_tokens=4000
)

# ChatGPT Codex for coding
response = client.chat.completions.create(
    model="gpt-5-codex",
    messages=[{"role": "user", "content": "Refactor this code"}],
    max_tokens=3000
)

# ===== Custom Models =====
response = client.chat.completions.create(
    model="glm-4.6",  # Z.AI model
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=1000
)

# ===== Streaming (works with all providers) =====
for chunk in client.chat.completions.create(
    model="gpt-5",  # or claude-sonnet-4-20250514, or glm-4.6
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# ===== Function calling (works with all providers) =====
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "What's the weather?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }]
)
```

### Using with cURL

```bash
# Claude model
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 1000
  }'

# ChatGPT model
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 2000
  }'
```

### Using with Anthropic SDK (native format)

```python
from anthropic import Anthropic

client = Anthropic(
    api_key="dummy",
    base_url="http://localhost:8081"
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Supported Features

### All Providers
- ✅ Chat completions (streaming and non-streaming)
- ✅ Tool/Function calling (including parallel tool calls)
- ✅ Vision/Image inputs (URL and base64)
- ✅ System messages
- ✅ Standard parameters (temperature, top_p, max_tokens, stop sequences)

### Claude-Specific
- ✅ Extended thinking mode via `reasoning_effort` parameter
- ✅ 1M context window (tier 4 required, use `-1m` suffix)
- ✅ Browser use
- ✅ All Anthropic-specific features via native API

### ChatGPT-Specific
- ✅ Reasoning with effort levels (minimal/low/medium/high)
- ✅ Reasoning summaries (auto/concise/detailed/none)
- ✅ 400K context window, 128K max output
- ✅ Model variants with pre-configured reasoning

## Configuration Priority

1. Environment variables (highest)
2. .env file
3. Built-in defaults (lowest)

## License

MIT License - see [LICENSE](LICENSE) file

This software is provided for educational purposes only. Users assume all risks.
