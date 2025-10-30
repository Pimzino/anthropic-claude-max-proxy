# Bug Fix: Tool Call Streaming Issue

## Problem Description

When using Cursor's plan tool (or any tool with string parameters), the tool would receive truncated parameter values. For example:
- Expected: `{"name": "Add OpenRouter Example"}` → creates `AddOpenRouterExample.plan.md`
- Actual: `{"name": "A"}` → creates `a.plan.md` or `f.plan.md`

The agent would provide the correct full name (e.g., "Add OpenRouter Example"), but Cursor would only see the first character or first few characters.

## Root Cause

The issue was in how we streamed tool call arguments from Anthropic to OpenAI format.

### How Anthropic Streams Tool Arguments

Anthropic sends tool arguments incrementally via `input_json_delta` events:

```
Event 1: {"partial_json": "{\"name\": \"A"}
Event 2: {"partial_json": "dd OpenRo"}
Event 3: {"partial_json": "uter"}
Event 4: {"partial_json": " Exampl"}
Event 5: {"partial_json": "e\""}
```

These chunks assemble to: `{"name": "Add OpenRouter Example"}`

### The Bug

Our proxy was **immediately forwarding each partial JSON chunk** to Cursor:

```python
# BUGGY CODE (before fix)
partial_json = delta.get("partial_json", "")
call_state["arguments"] += partial_json

# Immediately emit the partial JSON
delta_chunk = {
    "delta": {
        "tool_calls": [{
            "function": {
                "arguments": partial_json  # <-- Sends "A", then "dd OpenRo", etc.
            }
        }]
    }
}
yield emit(delta_chunk)
```

### Why This Caused the Problem

When Cursor receives streaming tool calls, it parses the JSON incrementally. When it sees:

```json
{"name": "A"}
```

It interprets this as a **complete** JSON object with `name = "A"`, not as an incomplete fragment. By the time the next chunks arrive (`"dd OpenRo"`, `"uter"`, etc.), Cursor has already parsed and used the value `"A"`.

This is similar to how a streaming JSON parser works - it can't know that `"A"` is incomplete without seeing the rest of the string.

## The Fix

We now **buffer the complete arguments** and only send them when the tool block is complete:

```python
# FIXED CODE
if delta_type == "input_json_delta":
    partial_json = delta.get("partial_json", "")
    call_state["arguments"] += partial_json

    # Just accumulate, don't emit anything yet
    continue

# Later, when content_block_stop is received:
if data_type == "content_block_stop":
    call_state = tool_call_states.get(sse_index)
    if call_state and call_state.get("arguments"):
        # Send the COMPLETE arguments in one chunk
        final_args_chunk = {
            "delta": {
                "tool_calls": [{
                    "function": {
                        "arguments": call_state["arguments"]  # Complete JSON
                    }
                }]
            }
        }
        yield emit(final_args_chunk)
```

### Streaming Behavior After Fix

Now Cursor receives:

1. **Tool start**: `{"tool_calls": [{"id": "...", "name": "create_plan", "arguments": ""}]}`
2. **Tool complete**: `{"tool_calls": [{"arguments": "{\"name\": \"Add OpenRouter Example\", ...}"}]}`

The complete JSON is sent in one chunk, so Cursor parses the full, correct value.

## Impact

### Before Fix
- ❌ Tool parameters were truncated to first few characters
- ❌ Plan tool created files like `a.plan.md` instead of `ProjectName.plan.md`
- ❌ Any tool with string parameters would fail similarly

### After Fix
- ✅ Tool parameters are complete and correct
- ✅ Plan tool creates properly named files
- ✅ All tools work as expected with Anthropic models

## Technical Details

### Why OpenAI's Streaming Works Differently

OpenAI's actual API likely sends tool arguments in larger, more complete chunks, or uses a different streaming protocol that doesn't break JSON values mid-string. Our proxy now mimics this behavior by buffering.

### Alternative Approaches Considered

1. **Stream complete JSON tokens**: Parse the JSON and stream complete values (e.g., entire strings, numbers)
   - ❌ Too complex, requires a streaming JSON parser
   - ❌ Would add latency

2. **Send empty arguments initially, complete at end**: ✅ **This is what we implemented**
   - ✅ Simple and reliable
   - ✅ Minimal latency impact (arguments arrive when tool block completes)
   - ✅ Compatible with how clients expect streaming

3. **Don't stream tool calls at all**: Wait for complete response
   - ❌ Would break streaming for text responses
   - ❌ Poor user experience

## Testing

To verify the fix works:

1. Start the proxy with the updated code
2. In Cursor, use plan mode and ask it to create a plan
3. Verify the plan file is created with the correct name (not `a.plan.md`)
4. Check the debug logs to see complete arguments being sent:

```bash
grep "STREAM_TOOL.*Complete arguments" proxy_debug.log
```

You should see the full JSON arguments being logged when the tool block completes.

## Files Modified

- `openai_compat.py`: Modified `convert_anthropic_stream_to_openai()` function
  - Lines ~1145-1160: Removed immediate emission of partial JSON
  - Lines ~1200-1230: Added complete arguments emission at `content_block_stop`

## Related Issues

This fix resolves:
- Plan tool creating files with wrong names
- Any tool receiving truncated string parameters
- JSON parsing issues in streaming tool calls

## Credits

Bug identified through detailed analysis of stream traces showing character-by-character JSON transmission from Anthropic being forwarded directly to Cursor, causing premature JSON parsing.
