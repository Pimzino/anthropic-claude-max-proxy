# Reasoning Support

LLMux exposes Anthropic and OpenAI reasoning features through the OpenAI-compatible API. Use this document to understand how to enable and tune thinking modes.

## Reasoning Effort Mapping

| OpenAI `reasoning_effort` | Anthropic `thinking.budget_tokens` |
|---------------------------|-------------------------------------|
| `low`                     | 8,000 tokens                        |
| `medium`                  | 16,000 tokens                       |
| `high`                    | 32,000 tokens                       |

## Enabling Reasoning

### Via `reasoning_effort`

```python
response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Solve this complex problem..."}],
    reasoning_effort="high"
)
```

### Via Model Variants

Many providers expose dedicated reasoning variants (e.g. `gpt5-reasoning-high` or `claude-opus-4-20250514-reasoning-high`). Selecting these models automatically requests extended thinking budgets.

## Notes

- Thinking is only enabled when requested. Standard models run without extra reasoning overhead.
- Anthropic 1M context models require tier 4 access; use the `-1m` suffix variants when available.
- Custom models can signal reasoning support via the `supports_reasoning` flag in `models.json` (see `docs/custom-models.md`).
