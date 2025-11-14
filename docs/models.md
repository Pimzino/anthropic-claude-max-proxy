# Available Models

LLMux routes requests to models provided by Anthropic, OpenAI (ChatGPT), and any custom OpenAI-compatible provider you configure. This guide lists the key model identifiers and capabilities surfaced through the proxy.

## Anthropic Claude Models

All Claude models available under your Claude Pro or Claude Max subscription become accessible:

- `claude-sonnet-4-20250514`
- `claude-opus-4-20250514`
- `claude-haiku-4-20250514`
- Reasoning variants (suffixed with `-reasoning-low`, `-reasoning-medium`, `-reasoning-high`)
- 1M context variants (suffixed with `-1m`, tier 4 required)

Requests sent through the OpenAI-compatible API are transparently rewritten to the Anthropic Messages API, adding required beta headers based on the chosen model.

## ChatGPT (OpenAI) Models

Your ChatGPT Plus or Pro subscription exposes these model identifiers through LLMux:

- `gpt5` (400K context, 128K output, reasoning + vision)
- `gpt5codex` (coding-tuned variant)
- `gpt51` (400K context, 128K output, reasoning + vision)
- `gpt51codex` (coding-tuned variant)
- `codexmini` (faster, smaller variant)
- Reasoning suffixes: `-reasoning-minimal`, `-reasoning-low`, `-reasoning-medium`, `-reasoning-high`

Friendly aliases like `gpt-5`, `gpt-5-codex`, `gpt-5.1`, `gpt-5.1-codex`, and `codex-mini-latest` continue to work for clients configured with those names.

## Custom Models

Any OpenAI-compatible API can be surfaced by adding entries to `models.json`. See `docs/custom-models.md` for configuration guidance.

Once configured, custom models appear alongside Claude and ChatGPT in the `/v1/models` endpoint and are callable via the same OpenAI-compatible interface.
