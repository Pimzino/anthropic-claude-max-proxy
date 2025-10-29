# Bug Fix Notes

## Bug: NoneType has no len() Error (Fixed)

**Date**: October 29, 2025
**Status**: ✅ FIXED

### Issue
After adding comprehensive debug logging, requests to Anthropic models (like sonnet-4-5) were failing with:
```
object of type 'NoneType' has no len()
```

### Root Cause
In `openai_compat.py`, line 263, the debug logging code was trying to get the length of `system_message_blocks` without checking if it was `None`:

```python
# BROKEN CODE:
logger.debug(f"[MESSAGE_CONVERSION] Final result: {len(anthropic_messages)} Anthropic messages, {len(system_message_blocks)} system blocks")
```

The `system_message_blocks` variable can be `None` when there are no system messages in the request, causing the `len()` call to fail.

### Fix
Added a conditional check before calling `len()`:

```python
# FIXED CODE:
logger.debug(f"[MESSAGE_CONVERSION] Final result: {len(anthropic_messages)} Anthropic messages, {len(system_message_blocks) if system_message_blocks else 0} system blocks")
```

### Files Changed
- `openai_compat.py` - Line 263

### Testing
After the fix:
- ✅ Requests to Anthropic models work correctly
- ✅ Debug logging still captures all necessary information
- ✅ No linting errors

### Prevention
Similar checks were already in place for other potentially-None values in the debug logging:
- Line 855: `len(tool_calls_result) if tool_calls_result else 0`
- Line 856: `len(reasoning_content) if reasoning_content else 0`

This pattern should be used consistently whenever calling `len()` on values that could be `None`.
