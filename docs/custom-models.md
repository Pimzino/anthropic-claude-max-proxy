# Custom Models

Configure additional OpenAI-compatible providers by editing `models.json`. This allows LLMux to forward requests to other services through the same proxy endpoint.

## Getting Started

1. Copy the example file: `cp models.example.json models.json`.
2. Add entries under the `custom_models` array.

Example configuration:

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

## Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Model identifier used by clients when making requests. |
| `base_url` | Yes | Base URL for the OpenAI-compatible API (e.g. `https://api.provider.com/v1`). |
| `api_key` | Yes | Provider API key used in outbound requests. |
| `context_length` | No | Specifies maximum context window tokens (defaults to 200000 if omitted). |
| `max_completion_tokens` | No | Overrides completion token cap (defaults to 4096). |
| `supports_reasoning` | No | Signals that the model accepts reasoning parameters. |
| `owned_by` | No | Friendly name for the provider (defaults to `custom`). |

## Usage

Once configured, invoke the model through any OpenAI-compatible client pointed at LLMux:

```python
response = client.chat.completions.create(
    model="glm-4.6",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

The proxy routes requests to the specified `base_url` using the stored API key while preserving the OpenAI API semantics.

> `models.json` is gitignored by default to prevent accidental commits of secrets.
