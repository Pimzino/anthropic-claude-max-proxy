# Debugging Guide for OpenAI to Anthropic Conversion

This guide explains the comprehensive debugging features added to help diagnose issues with OpenAI to Anthropic API conversion, particularly for tool/function calls.

## Overview

The proxy now includes extensive debug logging throughout the entire request/response pipeline:

1. **Raw Client Request Logging** - Captures the exact request from Cursor/client
2. **Message Conversion Logging** - Tracks how OpenAI messages are converted to Anthropic format
3. **Tool Schema Conversion Logging** - Shows how tool definitions are translated
4. **Tool Call Conversion Logging** - Tracks tool_calls in assistant messages
5. **Response Conversion Logging** - Shows how Anthropic responses are converted back to OpenAI format
6. **Streaming Tool Logging** - Tracks tool calls in streaming responses

## Enabling Debug Logging

To enable debug logging, start the proxy with the `--debug` flag:

```bash
python cli.py
# Then select "Start Proxy Server" and it will use debug mode if configured
```

Or set the log level in your environment:

```bash
export LOG_LEVEL=DEBUG
python cli.py
```

Debug logs are written to `proxy_debug.log` in the project directory.

## Debug Log Markers

All debug logs use specific markers to make them easy to search:

### Raw Client Request
- **Marker**: `[REQUEST_ID] ===== RAW CLIENT REQUEST (FULL DETAIL) =====`
- **What it shows**: The complete request from Cursor before any conversion
- **Includes**:
  - Model name
  - All messages with roles and content
  - Tool definitions (complete schemas)
  - Tool choice settings
  - Tool calls in assistant messages
  - Tool results in user messages

### Message Conversion
- **Marker**: `[MESSAGE_CONVERSION]`
- **What it shows**: How OpenAI messages are converted to Anthropic format
- **Includes**:
  - System message extraction
  - Role alternation handling
  - Tool result conversion (tool → tool_result)
  - Assistant tool_calls conversion (tool_calls → tool_use)

### Tool Schema Conversion
- **Marker**: `[TOOLS_SCHEMA]`
- **What it shows**: How OpenAI tool definitions are converted to Anthropic format
- **Includes**:
  - Each tool's name, description, and parameters
  - Detection of already-Anthropic-formatted tools
  - Conversion from OpenAI function format to Anthropic input_schema

### Tool Call Conversion
- **Marker**: `[TOOL_CONVERSION]`
- **What it shows**: How OpenAI tool_calls are converted to Anthropic tool_use blocks
- **Includes**:
  - Tool ID
  - Function name
  - Raw arguments string
  - Parsed arguments JSON
  - Final Anthropic tool_use block

### Request Conversion
- **Marker**: `[REQUEST_CONVERSION]`
- **What it shows**: The complete OpenAI to Anthropic request conversion
- **Includes**:
  - Full OpenAI request
  - Converted messages
  - System blocks
  - Model resolution
  - Tool choice handling
  - Final Anthropic request

### Response Conversion
- **Marker**: `[RESPONSE_CONVERSION]`
- **What it shows**: How Anthropic responses are converted back to OpenAI format
- **Includes**:
  - Anthropic content blocks
  - Text extraction
  - Tool_use to tool_calls conversion
  - Thinking/reasoning extraction

### Streaming Tool Calls
- **Marker**: `[STREAM_TOOL]`
- **What it shows**: Tool calls as they're streamed from Anthropic
- **Includes**:
  - Tool_use block start events
  - Incremental JSON arguments
  - Accumulated arguments
  - OpenAI delta chunks

## Common Issues and How to Debug

### Issue: Tool calls not working / Agent creates wrong filenames

**Symptoms**:
- Cursor's plan tool creates `f.plan.md` instead of `ProjectName.plan.md`
- Tool parameters are incorrect or missing
- Tools are not being called at all

**How to debug**:

1. Search for `[TOOLS_SCHEMA]` in the debug log to see:
   - Are the tool definitions being sent correctly from Cursor?
   - Are they being converted properly to Anthropic format?
   - Check the `input_schema` - does it match what you expect?

2. Search for `[TOOL_CONVERSION]` to see:
   - When the model responds with tool calls, are they being parsed correctly?
   - Check the `arguments` field - is it valid JSON?
   - Are the parameter names and values correct?

3. Search for `[MESSAGE_CONVERSION]` to see:
   - Are tool results being sent back correctly?
   - Check for `tool_call_id` matching

4. Compare with a working model (like GLM 4.6):
   - Run the same request through both models
   - Compare the `[TOOLS_SCHEMA]` sections
   - Look for differences in how parameters are structured

### Issue: Streaming responses have malformed tool calls

**Symptoms**:
- Tool calls work in non-streaming mode but fail in streaming
- Partial JSON in tool arguments

**How to debug**:

1. Search for `[STREAM_TOOL]` in the debug log
2. Check the `input_json_delta` events
3. Verify the accumulated arguments form valid JSON
4. Look for any truncation or encoding issues

### Issue: Tool choice not being respected

**Symptoms**:
- Setting `tool_choice` to force a specific tool doesn't work
- Model doesn't use tools when it should

**How to debug**:

1. Search for `tool_choice` in the raw client request
2. Check `[REQUEST_CONVERSION]` for how it's being translated
3. Verify the Anthropic request has the correct `tool_choice` format

## Example Debug Session

Here's an example of debugging a tool call issue:

```bash
# 1. Start proxy with debug logging
python cli.py --debug

# 2. Make a request from Cursor that uses tools

# 3. Search the debug log
grep "TOOLS_SCHEMA" proxy_debug.log
grep "TOOL_CONVERSION" proxy_debug.log

# 4. Look for the specific tool
grep -A 20 "todo_write" proxy_debug.log

# 5. Compare input vs output
grep -B 5 -A 10 "RAW CLIENT REQUEST" proxy_debug.log > client_request.txt
grep -B 5 -A 10 "FINAL ANTHROPIC REQUEST" proxy_debug.log > anthropic_request.txt
diff client_request.txt anthropic_request.txt
```

## Providing Debug Logs for Support

When reporting issues, please provide:

1. The relevant section from `proxy_debug.log` including:
   - `===== RAW CLIENT REQUEST (FULL DETAIL) =====`
   - `[TOOLS_SCHEMA]` sections
   - `[TOOL_CONVERSION]` sections
   - `===== FINAL ANTHROPIC REQUEST =====`
   - `===== CONVERTING ANTHROPIC RESPONSE TO OPENAI =====`

2. Redact any sensitive information (API keys, personal data)

3. Include the request ID (e.g., `[a45e1d59]`) to track the specific request

## Performance Considerations

Debug logging is verbose and will:
- Increase log file size significantly
- Add slight latency to requests (usually <10ms)
- Log potentially sensitive data (tool parameters, message content)

**Recommendation**: Only enable debug logging when actively troubleshooting issues.

## Log Rotation

The debug log appends to `proxy_debug.log`. To prevent it from growing too large:

```bash
# Clear the log
> proxy_debug.log

# Or rotate it
mv proxy_debug.log proxy_debug.log.old
```

## Advanced: Filtering Logs

Use these commands to extract specific information:

```bash
# Extract all tool-related logs for a specific request
grep "\[a45e1d59\].*TOOL" proxy_debug.log

# Extract the conversion pipeline for a request
grep "\[a45e1d59\].*CONVERSION" proxy_debug.log

# See all tool schemas sent by clients
grep -A 30 "TOOLS_SCHEMA.*Tool #" proxy_debug.log

# Compare tool definitions across requests
grep "Tool #0:" proxy_debug.log | head -20
```

## Troubleshooting the Debugger

If debug logs aren't appearing:

1. Check `LOG_LEVEL` environment variable
2. Verify `--debug` flag is being used
3. Check file permissions on `proxy_debug.log`
4. Ensure the proxy is actually processing requests (check for `NEW OPENAI CHAT COMPLETION REQUEST`)
