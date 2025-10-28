# Prompt Caching Implementation

## Overview

The proxy now implements **automatic prompt caching** for all requests to optimize API usage and reduce costs. Prompt caching is a standard Anthropic API feature available to all users.

## How It Works

The proxy automatically adds `cache_control` markers to:

1. **System messages** - The entire system prompt is cached
2. **Last 2 user messages** - Recent conversation history is cached

This follows Anthropic's best practices for prompt caching as documented at: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

## Implementation Details

### Cache Breakpoints

The `add_prompt_caching()` function in `proxy.py` adds ephemeral cache breakpoints:

- **System Message**: Converts string system messages to array format and adds `cache_control: {type: 'ephemeral'}` to the last block
- **User Messages**: Adds `cache_control: {type: 'ephemeral'}` to the last content block of the last 2 user messages

### Example

**Before caching:**
```json
{
  "system": "You are a helpful assistant",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"},
    {"role": "user", "content": "How are you?"}
  ]
}
```

**After caching:**
```json
{
  "system": [
    {
      "type": "text",
      "text": "You are a helpful assistant",
      "cache_control": {"type": "ephemeral"}
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Hello",
          "cache_control": {"type": "ephemeral"}
        }
      ]
    },
    {"role": "assistant", "content": "Hi!"},
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "How are you?",
          "cache_control": {"type": "ephemeral"}
        }
      ]
    }
  ]
}
```

## Benefits

1. **Reduced Costs**: Cached tokens are significantly cheaper than regular input tokens
2. **Faster Responses**: Cached content is processed faster by the API
3. **Automatic**: No client-side configuration needed
4. **Universal**: Works with both OpenAI-compatible and native Anthropic endpoints

## Supported Endpoints

- ✅ `/v1/messages` (Native Anthropic API)
- ✅ `/v1/chat/completions` (OpenAI-compatible API)

Both endpoints automatically benefit from prompt caching.

## Cache Behavior

- **Type**: Ephemeral (5-minute TTL as per Anthropic's implementation)
- **Scope**: Per-conversation (system + recent messages)
- **Automatic**: Applied to all requests without client configuration

## Previous Implementation

The previous implementation **incorrectly stripped** `cache_control` from messages based on the mistaken belief that it required tier 4 access. This has been corrected - prompt caching is available to all Anthropic API users.
