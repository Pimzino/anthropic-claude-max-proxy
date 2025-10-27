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
- Uses header-based beta features instead of `?beta=true` query parameter

**Beta Features:**
- `claude-code-20250219` - Claude Code integration
- `oauth-2025-04-20` - OAuth support
- `interleaved-thinking-2025-05-14` - Extended thinking support
- `fine-grained-tool-streaming-2025-05-14` - Tool streaming support

**OAuth Endpoints:**
- Authorization: `https://claude.ai/oauth/authorize`
- Token exchange/refresh: `https://console.anthropic.com/v1/oauth/token`
- API key creation: `https://api.anthropic.com/api/oauth/claude_cli/create_api_key`

**Cache Control:**
- Automatic ephemeral cache control on system messages

## Prerequisites

- Active Claude Pro or Claude Max subscription
- Python 3.8+
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

## Configuration Priority

1. Environment variables (highest)
2. config.json file
3. Built-in defaults (lowest)

## License

MIT License - see [LICENSE](LICENSE) file

This software is provided for educational purposes only. Users assume all risks.
