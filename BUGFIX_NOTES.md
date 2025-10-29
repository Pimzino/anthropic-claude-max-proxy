# Bug Fix Notes

## Bug: NoneType has no len() Error (Fixed)

**Date**: October 29-30, 2025
**Status**: ✅ FIXED

### Issue
After adding comprehensive debug logging, requests to Anthropic models (like sonnet-4-5) were failing with:
```
object of type 'NoneType' has no len()
```

### Root Causes

#### Occurrence 1: openai_compat.py (Line 263)
In `openai_compat.py`, line 263, the debug logging code was trying to get the length of `system_message_blocks` without checking if it was `None`:

```python
# BROKEN CODE:
logger.debug(f"[MESSAGE_CONVERSION] Final result: {len(anthropic_messages)} Anthropic messages, {len(system_message_blocks)} system blocks")
```

The `system_message_blocks` variable can be `None` when there are no system messages in the request, causing the `len()` call to fail.

**Fix**: Added a conditional check before calling `len()`:

```python
# FIXED CODE:
logger.debug(f"[MESSAGE_CONVERSION] Final result: {len(anthropic_messages)} Anthropic messages, {len(system_message_blocks) if system_message_blocks else 0} system blocks")
```

#### Occurrence 2: proxy.py (Line 234)
In `proxy.py`, line 234, similar issue with the `system` field in the Anthropic request:

```python
# BROKEN CODE:
logger.debug(f"[{request_id}] - system: {type(anthropic_request.get('system'))} with {len(anthropic_request.get('system', []))} elements")
```

The problem was that `anthropic_request.get('system')` returns `None` when there's no system message, and we were trying to get both the type and length of `None`. The default `[]` only applied to the second `.get()` call, not the first.

**Fix**: Properly handle the None case:

```python
# FIXED CODE:
system = anthropic_request.get('system')
if system:
    logger.debug(f"[{request_id}] - system: {type(system)} with {len(system)} elements")
else:
    logger.debug(f"[{request_id}] - system: None")
```

#### Occurrence 3: openai_compat.py (Lines 607, 617)
In `openai_compat.py`, lines 607 and 617, checking if `'tools'` or `'functions'` exists in the request but not checking if they're `None`:

```python
# BROKEN CODE:
if "tools" in openai_request:
    logger.debug(f"[REQUEST_CONVERSION] Found 'tools' field in OpenAI request with {len(openai_request['tools'])} tools")

if "functions" in openai_request:
    logger.debug(f"[REQUEST_CONVERSION] Found 'functions' field (legacy) in OpenAI request with {len(openai_request['functions'])} functions")
```

The problem: In Python, `"key" in dict` returns `True` even if `dict["key"]` is `None`. So we were trying to call `len(None)`.

**Fix**: Check both existence AND that the value is not None/empty:

```python
# FIXED CODE:
if "tools" in openai_request and openai_request["tools"]:
    logger.debug(f"[REQUEST_CONVERSION] Found 'tools' field in OpenAI request with {len(openai_request['tools'])} tools")

if "functions" in openai_request and openai_request["functions"]:
    logger.debug(f"[REQUEST_CONVERSION] Found 'functions' field (legacy) in OpenAI request with {len(openai_request['functions'])} functions")
```

### Files Changed
- `openai_compat.py` - Line 263 (system_message_blocks)
- `openai_compat.py` - Lines 607, 617 (tools and functions)
- `proxy.py` - Lines 232-237 (system field)
- `proxy.py` - Added traceback logging to exception handlers (lines 604, 427)

### Testing
After the fixes:
- ✅ Requests to Anthropic models work correctly
- ✅ Debug logging still captures all necessary information
- ✅ No linting errors
- ✅ Full tracebacks now logged for easier debugging
- ✅ Handles None values in tools, functions, and system fields

### Prevention
Similar checks were already in place for other potentially-None values in the debug logging:
- Line 855: `len(tool_calls_result) if tool_calls_result else 0`
- Line 856: `len(reasoning_content) if reasoning_content else 0`

**Lesson Learned**:
1. When calling `len()` or other methods on values that could be `None`, always check for None first or use a conditional expression
2. In Python, `"key" in dict` returns `True` even if `dict["key"]` is `None`, so always check the value: `if "key" in dict and dict["key"]:`
3. This is especially important in debug logging code where we're inspecting potentially optional fields

### Additional Improvements
Added `logger.exception()` calls to exception handlers to capture full tracebacks, making future debugging much easier. This helped us quickly identify the exact line causing the error.

---

## Bug: Stream Error Handling - 'str' object has no attribute 'get' (Fixed)

**Date**: October 30, 2025
**Status**: ✅ FIXED

### Issue
When a stream timeout occurred, the error conversion code was failing with:
```
'str' object has no attribute 'get'
```

This happened during streaming responses when the Anthropic API timed out after 60 seconds.

### Root Cause
In `openai_compat.py`, line 1267, the error handling code assumed that `data["error"]` was always a dictionary:

```python
# BROKEN CODE:
if data_type == "error":
    error_chunk = {
        "error": {
            "message": data.get("error", {}).get("message", "Unknown error"),
            "type": data.get("error", {}).get("type", "api_error")
        }
    }
```

However, when a timeout occurs in `anthropic.py`, it yields:
```python
error_event = f"event: error\ndata: {{\"error\": \"Stream timeout after {STREAM_TIMEOUT}s\"}}\n\n"
```

After JSON parsing, this becomes `{"error": "Stream timeout after 60s"}`, where `error` is a **string**, not a dict. Calling `.get("message")` on a string causes the error.

### Fix
Added proper type checking to handle both string and dict error formats:

```python
# FIXED CODE:
if data_type == "error":
    # Handle error events - error can be a string or a dict
    error_value = data.get("error", {})
    if isinstance(error_value, str):
        # Simple string error (e.g., from timeout)
        error_chunk = {
            "error": {
                "message": error_value,
                "type": "api_error"
            }
        }
    elif isinstance(error_value, dict):
        # Structured error from Anthropic
        error_chunk = {
            "error": {
                "message": error_value.get("message", "Unknown error"),
                "type": error_value.get("type", "api_error")
            }
        }
    else:
        # Fallback for unexpected format
        error_chunk = {
            "error": {
                "message": str(error_value),
                "type": "api_error"
            }
        }
```

### Files Changed
- `openai_compat.py` - Lines 1264-1275 (error handling in stream conversion)

### Testing
After the fix:
- ✅ Stream timeouts are handled gracefully
- ✅ Error messages are properly converted to OpenAI format
- ✅ Both string and dict error formats are supported
- ✅ No linting errors

### Lesson Learned
When handling data from external sources or different code paths, always validate the data type before assuming its structure. Use `isinstance()` checks to handle multiple formats gracefully.

### Stream Trace Evidence
From `stream_traces/20251029T232450Z_openai-chat_29fed74c.log`:
```
[2025-10-29T23:25:52.273] [ERROR] len=37
anthropic stream timeout after 600.0s
[2025-10-29T23:25:52.273] [NOTE] len=26
yielding timeout SSE event
[2025-10-29T23:25:52.274] [ERROR] len=57
conversion exception: 'str' object has no attribute 'get'
```

The stream tracer helped identify the exact sequence of events leading to the error.
