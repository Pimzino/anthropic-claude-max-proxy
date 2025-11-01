# ChatGPT "Instructions are not valid" Error - Fix

## Problem

When trying to use GPT-5 models through the ChatGPT Responses API, we were getting a 400 error:

```json
{"detail":"Instructions are not valid"}
```

## Root Cause

The issue was that we were sending **short one-liner instructions** to the ChatGPT API:

```
"You are a helpful coding assistant. You are precise, safe, and helpful. Your default personality and tone is concise, direct, and friendly."
```

However, ChatMock (the reference implementation) sends the **entire prompt markdown files** as instructions:
- For `gpt-5`: The full `prompt.md` file (~23KB, 327 lines)
- For `gpt-5-codex`: The full `prompt_gpt5_codex.md` file (~9.6KB, 101 lines)

The ChatGPT Responses API expects these detailed, comprehensive instructions that match what the official Codex CLI uses.

## Solution

1. **Created prompt files** in `prompts/` directory:
   - `prompts/gpt5_base.md` - Full base GPT-5 instructions (copied from ChatMock's `prompt.md`)
   - `prompts/gpt5_codex.md` - Full GPT-5 Codex instructions (copied from ChatMock's `prompt_gpt5_codex.md`)

2. **Updated `models/custom_models.py`** to load instructions from markdown files:
   - Added `_read_prompt_file()` function to read prompt files from multiple candidate locations
   - Added `_load_base_instructions()` to load base GPT-5 instructions
   - Added `_load_gpt5_codex_instructions()` to load Codex instructions
   - Changed `CHATGPT_BASE_INSTRUCTIONS` and `CHATGPT_GPT5_CODEX_INSTRUCTIONS` to load from files

## Files Changed

- `prompts/gpt5_base.md` (new) - Base GPT-5 instructions
- `prompts/gpt5_codex.md` (new) - GPT-5 Codex instructions
- `models/custom_models.py` - Updated to load instructions from markdown files

## Testing

After this fix, the ChatGPT provider will send the full, detailed instructions that the API expects, matching exactly what ChatMock does.

To verify the fix is working:

```bash
# Check that instructions are loaded
python -c "from models.custom_models import CHATGPT_BASE_INSTRUCTIONS; print(f'Length: {len(CHATGPT_BASE_INSTRUCTIONS)}')"

# Should output: Length: 23430 (approximately)
```

## Why This Matters

The ChatGPT Responses API is designed to work with the Codex CLI, which sends comprehensive system instructions that define:
- How the agent should behave
- Tool usage patterns
- Response formatting guidelines
- Planning and execution strategies
- Sandbox and approval workflows

These detailed instructions are critical for the model to function correctly as a coding agent, not just a simple chatbot.

---

## Second Issue: Reasoning Parameter Format

### Problem

After fixing the instructions, we encountered another 400 error:

```json
{
  "error": {
    "message": "Unknown parameter: 'reasoning.type'.",
    "type": "invalid_request_error",
    "param": "reasoning.type",
    "code": "unknown_parameter"
  }
}
```

### Root Cause

We were sending the reasoning parameter in the wrong format:

**Our format (WRONG):**
```json
{
  "type": "enabled",
  "effort": "medium",
  "summary": "auto"
}
```

**ChatMock format (CORRECT):**
```json
{
  "effort": "medium",
  "summary": "auto"
}
```

The ChatGPT API doesn't recognize the `"type": "enabled"` field.

### Solution

Updated `providers/chatgpt_provider.py` to match ChatMock's reasoning parameter format:
- Removed the `"type": "enabled"` field
- Only include `"effort"` (required) and `"summary"` (optional, omit if "none")
- Added validation for effort values: `["minimal", "low", "medium", "high"]`
- Added validation for summary values: `["auto", "concise", "detailed", "none"]`

### Files Changed

- `providers/chatgpt_provider.py` - Fixed reasoning parameter format in `_build_responses_payload()`

### Testing

The reasoning parameter should now be sent in the correct format that the ChatGPT API expects.
