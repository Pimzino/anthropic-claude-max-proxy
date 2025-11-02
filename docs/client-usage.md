# Client Usage Examples

LLMux speaks the OpenAI-compatible API across all providers, making it easy to swap in for existing clients. This guide collects example snippets in multiple environments.

## OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="dummy",  # Any non-empty string
    base_url="http://localhost:8081/v1"
)

# Claude Sonnet
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello!"}]
)

# ChatGPT
response = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Custom model example
response = client.chat.completions.create(
    model="glm-4.6",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Streaming output
for chunk in client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# Tool/function calling
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

## Anthropic Python SDK (Native Format)

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

## cURL Examples

```bash
# Claude via OpenAI-compatible endpoint
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
