# Anthropic Claude Max Proxy

Pure Anthropic proxy for Claude Pro/Max subscriptions using OAuth.

## SUPPORT MY WORK
<a href="https://buymeacoffee.com/Pimzino" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## DISCLAIMER

**FOR EDUCATIONAL PURPOSES ONLY**

This tool:
- Is NOT affiliated with or endorsed by Anthropic
- Uses undocumented OAuth flows from Claude Code (OpenCode)
- May violate Anthropic's Terms of Service
- Could stop working at any time without notice
- Comes with NO WARRANTY or support

**USE AT YOUR OWN RISK. The authors assume no liability for any consequences.**

For official access, use Claude Code or Anthropic's API with console API keys.

## Implementation Details

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

## Prerequisites

- Active Claude Pro or Claude Max subscription
- **Option 1: Traditional Setup**
  - Python 3.8+
  - pip
- **Option 2: Docker Setup**
  - Docker installed and running

## Quick Start

### Option 1: Docker Setup

**One-command setup and run:**
```bash
./run-docker.sh
# Or specify custom port:
./run-docker.sh 8082
```

This will automatically:
- Build the Docker image
- Create persistent volume for authentication tokens
- Guide you through the OAuth authentication
- Start the proxy server in background

**Features:**
- Automatic token refresh if container is already running
- Persistent authentication across container restarts
- Port conflict detection and automatic resolution
- Clean container lifecycle management

### Option 2: Traditional Python Setup

1. **Virtual Environment Setup**
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
cp config.example.json config.json
```

4. **Run:**
```bash
python cli.py
# Or with custom bind address:
python cli.py --bind 127.0.0.1
```

5. **Authenticate:**
- Select option 2 (Login)
- Browser opens automatically
- Complete login at claude.ai
- Copy the authorization code
- Paste in terminal

6. **Start proxy:**
- Select option 1 (Start Proxy Server)
- Server runs at `http://0.0.0.0:8081` (default, listens on all interfaces)

## Docker Management Commands

When using Docker setup:

**Check container status:**
```bash
docker ps -f name=claude-proxy-server
```

**View logs:**
```bash
docker logs claude-proxy-server -f
```

**Stop the server:**
```bash
docker stop claude-proxy-server
```

**Remove container:**
```bash
docker rm claude-proxy-server
```

**Re-run to refresh authentication:**
```bash
./run-docker.sh
```

## Client Configuration

The proxy supports **two API formats**:

### Native Anthropic API

Configure your Anthropic API client:

- **Base URL:** `http://<proxy-host>:8081`
- **API Key:** Any non-empty string (e.g., "dummy")
- **Model:** `claude-sonnet-4-20250514` (or any available Claude model)
- **Endpoint:** `/v1/messages`

### OpenAI-Compatible API

Configure your OpenAI API client:

- **Base URL:** `http://<proxy-host>:8081/v1`
- **API Key:** Any non-empty string (e.g., "dummy")
- **Model:** Use actual Claude model names (e.g., `claude-sonnet-4-20250514`)
- **Endpoint:** `/v1/chat/completions`

The OpenAI compatibility layer supports:
- ✅ Chat completions (streaming and non-streaming)
- ✅ Tool/Function calling (including parallel tool calls)
- ✅ Vision/Image inputs (URL and base64)
- ✅ System messages
- ✅ All standard parameters (temperature, top_p, max_tokens, stop sequences)
- ✅ Reasoning/Thinking support via `reasoning_effort` parameter or model variants

## Available Models

- Supports all Anthropic Models that you have access to with your Claude Pro / Max subscription.

## Custom Models Configuration

The proxy now supports routing requests to **custom OpenAI-compatible providers** (like Z.AI, OpenRouter, etc.) alongside Anthropic models. This allows you to use multiple providers through a single proxy endpoint without changing your client configuration.

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

Once configured, custom models appear in the `/v1/models` endpoint and can be used just like Anthropic models:

```python
# Using Z.AI GLM-4.6 through the proxy
response = client.chat.completions.create(
    model="glm-4.6",  # Your custom model ID
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### How It Works

- **Custom models bypass Anthropic-specific processing** (no OAuth, no Claude Code spoofing, no prompt caching)
- Requests are passed directly to the configured endpoint in OpenAI format
- Each custom model uses its own API key (no OAuth required)
- Supports both streaming and non-streaming requests
- Custom models appear alongside Anthropic models in `/v1/models` listing

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

```python
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514-reasoning-high",  # Auto-enables thinking
    messages=[{"role": "user", "content": "Solve this complex problem..."}]
)
```

Available reasoning model variants:
- `{model-name}-reasoning-low` (8k thinking budget)
- `{model-name}-reasoning-medium` (16k thinking budget)
- `{model-name}-reasoning-high` (32k thinking budget)

**Note:** If both `reasoning_effort` parameter and reasoning model variant are specified, the parameter takes precedence.

## 1M Context Window Support

The proxy supports 1-million token context window through model name variants. **Note:** 1M context requires **tier 4** subscription or custom rate limits.

### Using 1M Context Model Variants

Add `-1m` to any model name to enable 1M context:

```python
# Standard 200K context
model="claude-sonnet-4-20250514"

# 1M context (tier 4 required)
model="claude-sonnet-4-20250514-1m"

# 1M context + reasoning
model="claude-sonnet-4-20250514-1m-reasoning-high"
```

### How it Works

When you use a `-1m` model variant:
1. The proxy automatically adds the `context-1m-2025-08-07` beta header
2. The `-1m` suffix is stripped before sending to Anthropic
3. If you don't have tier 4 access, the request will fail with an error

**Important:** Only use `-1m` variants if you have confirmed tier 4 access. Standard Pro/Max subscriptions do NOT have 1M context access.

### Automatic max_tokens Adjustment

When reasoning is enabled, the proxy automatically ensures `max_tokens` is sufficient:
- Minimum required = thinking_budget + 1024 (for response)
- If your `max_tokens` is too low, it will be automatically increased with a warning logged

## Usage Examples

### Using with OpenAI Python SDK

```python
import openai

client = openai.OpenAI(
    api_key="dummy",
    base_url="http://localhost:8081/v1"
)

# Basic chat completion (no reasoning)
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=1000
)

print(response.choices[0].message.content)

# With reasoning enabled via parameter
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
    reasoning_effort="high",  # Enables extended thinking
    max_tokens=4000
)

# With reasoning enabled via model variant
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514-reasoning-medium",
    messages=[{"role": "user", "content": "Solve this logic puzzle"}],
    max_tokens=4000
)

# Streaming
for chunk in client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# Function calling
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

### Using with cURL (OpenAI format)

```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 1000
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
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
```

## Tested & Supported Features

### Native Anthropic API
- Browser use
- Images
- Extended thinking mode
- All Anthropic-specific features

### OpenAI API Compatibility
- Chat completions (streaming and non-streaming)
- Tool/Function calling
- Vision (image inputs via URL or base64)
- System messages
- Standard parameters (temperature, top_p, max_tokens, stop)
- Extended thinking/reasoning via `reasoning_effort` parameter
- Model variants with pre-configured thinking budgets
  - `claude-sonnet-4-20250514-reasoning-low` (8k tokens)
  - `claude-sonnet-4-20250514-reasoning-medium` (16k tokens)
  - `claude-sonnet-4-20250514-reasoning-high` (32k tokens)

These features provide compatibility with OpenAI's API format while leveraging Anthropic's extended thinking capabilities that are not available or not user friendly in Claude Code.

## Docker Architecture

The Docker setup uses:
- **Persistent Volume:** `claude-tokens` - Stores authentication tokens across container restarts
- **Container Name:** `claude-proxy-server` - Fixed name for easy management
- **Automatic Restart:** `unless-stopped` policy ensures service continuity
- **Smart Authentication:** Only re-authenticates when tokens expire
- **Port Management:** Automatic port conflict resolution for default port

## Configuration Priority

1. Environment variables (highest)
2. config.json file
3. Built-in defaults (lowest)

## License

MIT License - see [LICENSE](LICENSE) file

This software is provided for educational purposes only. Users assume all risks.
