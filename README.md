# Anthropic Claude Max Proxy

Pure Anthropic proxy for Claude Pro/Max subscriptions using OAuth.

## SUPPORT MY WORK
<a href="https://buymeacoffee.com/Pimzino" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## DISCLAIMER

**FOR EDUCATIONAL PURPOSES ONLY**

This tool:
- Is NOT affiliated with or endorsed by Anthropic
- Uses undocumented OAuth flows from Claude Code
- May violate Anthropic's Terms of Service
- Could stop working at any time without notice
- Comes with NO WARRANTY or support

**USE AT YOUR OWN RISK. The authors assume no liability for any consequences.**

For official access, use Claude Code or Anthropic's API with console API keys.

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

## Available Models

- Supports all Anthropic Models that you have access to with your Claude Pro / Max subscription.

## Usage Examples

### Using with OpenAI Python SDK

```python
import openai

client = openai.OpenAI(
    api_key="dummy",
    base_url="http://localhost:8081/v1"
)

# Basic chat completion
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=1000
)

print(response.choices[0].message.content)

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

These are features that are not available or not user friendly in CC.

## Configuration Priority

1. Environment variables (highest)
2. config.json file
3. Built-in defaults (lowest)

## License

MIT License - see [LICENSE](LICENSE) file

This software is provided for educational purposes only. Users assume all risks.
