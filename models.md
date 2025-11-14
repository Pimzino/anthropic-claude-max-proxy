# Available Models

This document lists all models available through the `/v1/models` endpoint.

## Claude Models (Anthropic)

### Base Models

| Model ID | Anthropic ID | Context Length | Max Completion Tokens | Vision Support |
|----------|--------------|----------------|----------------------|----------------|
| `sonnet-4-5` | `claude-sonnet-4-5-20250929` | 200,000 | 65,536 | ✓ |
| `haiku-4-5` | `claude-haiku-4-5-20251001` | 200,000 | 65,536 | ✓ |
| `opus-4-1` | `claude-opus-4-1-20250805` | 200,000 | 32,768 | ✓ |
| `sonnet-4` | `claude-sonnet-4-20250514` | 200,000 | 65,536 | ✓ |

### Reasoning Variants

Each base model has three reasoning variants with different thinking budgets:

| Model ID | Reasoning Level | Thinking Budget (tokens) |
|----------|----------------|-------------------------|
| `sonnet-4-5-reasoning-low` | Low | 8,000 |
| `sonnet-4-5-reasoning-medium` | Medium | 16,000 |
| `sonnet-4-5-reasoning-high` | High | 32,000 |
| `haiku-4-5-reasoning-low` | Low | 8,000 |
| `haiku-4-5-reasoning-medium` | Medium | 16,000 |
| `haiku-4-5-reasoning-high` | High | 32,000 |
| `opus-4-1-reasoning-low` | Low | 8,000 |
| `opus-4-1-reasoning-medium` | Medium | 16,000 |
| `opus-4-1-reasoning-high` | High | 32,000 |
| `sonnet-4-reasoning-low` | Low | 8,000 |
| `sonnet-4-reasoning-medium` | Medium | 16,000 |
| `sonnet-4-reasoning-high` | High | 32,000 |

## ChatGPT Models (OpenAI)

### Base Models

| Model ID | Context Length | Max Completion Tokens | Vision Support | Reasoning Support |
|----------|----------------|----------------------|----------------|-------------------|
| `gpt5` | 400,000 | 128,000 | ✓ | ✓ |
| `gpt5codex` | 400,000 | 128,000 | ✓ | ✓ |
| `gpt51` | 400,000 | 128,000 | ✓ | ✓ |
| `gpt51codex` | 400,000 | 128,000 | ✓ | ✓ |
| `codexmini` | 128,000 | 16,000 | ✗ | ✗ |

### Reasoning Variants (if enabled)

When `CHATGPT_EXPOSE_REASONING_VARIANTS` is enabled, the following variants are available:

| Model ID | Reasoning Effort |
|----------|-----------------|
| `gpt5-reasoning-minimal` | Minimal |
| `gpt5-reasoning-low` | Low |
| `gpt5-reasoning-medium` | Medium |
| `gpt5-reasoning-high` | High |
| `gpt5codex-reasoning-minimal` | Minimal |
| `gpt5codex-reasoning-low` | Low |
| `gpt5codex-reasoning-medium` | Medium |
| `gpt5codex-reasoning-high` | High |
| `gpt51-reasoning-minimal` | Minimal |
| `gpt51-reasoning-low` | Low |
| `gpt51-reasoning-medium` | Medium |
| `gpt51-reasoning-high` | High |
| `gpt51codex-reasoning-minimal` | Minimal |
| `gpt51codex-reasoning-low` | Low |
| `gpt51codex-reasoning-medium` | Medium |
| `gpt51codex-reasoning-high` | High |

## Custom Models

Custom models can be configured via `models.json`. These models appear in the `/v1/models` endpoint alongside Claude and ChatGPT models.

## Model Aliases

The following Anthropic native IDs are also accepted (but not listed in `/v1/models`):

- `claude-sonnet-4-5-20250929`
- `claude-haiku-4-5-20251001`
- `claude-opus-4-1-20250805`
- `claude-sonnet-4-20250514`

Each Anthropic native ID also supports reasoning variants:
- `{anthropic-id}-reasoning-low`
- `{anthropic-id}-reasoning-medium`
- `{anthropic-id}-reasoning-high`

The following OpenAI native IDs are also accepted (but not listed in `/v1/models`):

- `gpt-5`
- `gpt-5-codex`
- `gpt-5.1`
- `gpt-5.1-codex`
- `codex-mini-latest`

Each OpenAI native ID also supports reasoning variants (when enabled):
- `gpt-5-minimal`, `gpt-5-low`, `gpt-5-medium`, `gpt-5-high`
- `gpt-5-codex-minimal`, `gpt-5-codex-low`, `gpt-5-codex-medium`, `gpt-5-codex-high`
- `gpt-5.1-minimal`, `gpt-5.1-low`, `gpt-5.1-medium`, `gpt-5.1-high`
- `gpt-5.1-codex-minimal`, `gpt-5.1-codex-low`, `gpt-5.1-codex-medium`, `gpt-5.1-codex-high`

## Total Model Count

- **Claude Base Models**: 4
- **Claude Reasoning Variants**: 12 (3 per base model)
- **ChatGPT Base Models**: 5
- **ChatGPT Reasoning Variants**: 16 (when enabled)
- **Custom Models**: Varies based on configuration

**Total Listed Models**: 21-37 (depending on configuration)

## Notes

1. All Claude models support vision (image input)
2. Reasoning variants use extended thinking to improve response quality
3. ChatGPT reasoning variants use OpenAI's effort-based reasoning system
4. Custom models can override default specifications via `models.json`
5. Model aliases (Anthropic native IDs and OpenAI native IDs) are accepted but not shown in listings
