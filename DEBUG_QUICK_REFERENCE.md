# Debug Quick Reference Card

## Most Useful Grep Commands

### Find a specific request by ID
```bash
grep "\[a45e1d59\]" proxy_debug.log
```

### See all tool schemas from Cursor
```bash
grep -A 50 "TOOLS_SCHEMA.*Converting" proxy_debug.log
```

### See tool calls made by the model
```bash
grep -A 20 "TOOL_CONVERSION.*Converting" proxy_debug.log
```

### See the raw client request
```bash
grep -A 100 "RAW CLIENT REQUEST" proxy_debug.log
```

### See the final Anthropic request
```bash
grep -A 100 "FINAL ANTHROPIC REQUEST" proxy_debug.log
```

### See tool parameters being sent
```bash
grep "Parameters schema:" proxy_debug.log
```

### See tool arguments in responses
```bash
grep "Arguments (raw string):" proxy_debug.log
```

### Track a specific tool by name
```bash
grep -i "todo_write" proxy_debug.log
grep -i "plan" proxy_debug.log
```

### See all tool-related logs for one request
```bash
# Replace REQUEST_ID with actual ID like a45e1d59
grep "\[REQUEST_ID\].*\(TOOL\|tool\)" proxy_debug.log
```

### Compare requests side-by-side
```bash
# Extract two requests
grep -A 200 "\[REQUEST_ID_1\].*RAW CLIENT REQUEST" proxy_debug.log > req1.txt
grep -A 200 "\[REQUEST_ID_2\].*RAW CLIENT REQUEST" proxy_debug.log > req2.txt
diff req1.txt req2.txt
```

## Debug Markers Cheat Sheet

| Marker | What It Shows |
|--------|---------------|
| `[TOOLS_SCHEMA]` | Tool definitions conversion |
| `[TOOL_CONVERSION]` | Tool calls in responses |
| `[MESSAGE_CONVERSION]` | Message format conversion |
| `[REQUEST_CONVERSION]` | Full request conversion |
| `[RESPONSE_CONVERSION]` | Response back to OpenAI |
| `[STREAM_TOOL]` | Streaming tool calls |

## Common Patterns

### Pattern 1: Tool not being called
```bash
# Check if tool is in the schema
grep -A 30 "TOOLS_SCHEMA" proxy_debug.log | grep -i "TOOL_NAME"

# Check if model tried to call it
grep -A 20 "TOOL_CONVERSION" proxy_debug.log | grep -i "TOOL_NAME"
```

### Pattern 2: Wrong parameters in tool call
```bash
# See what Cursor sent
grep -B 5 -A 30 "TOOLS_SCHEMA.*Tool #0" proxy_debug.log

# See what model returned
grep -A 20 "TOOL_CONVERSION.*Tool #0" proxy_debug.log
```

### Pattern 3: Compare working vs broken model
```bash
# GLM request (working)
grep "\[GLM-4.6\]" proxy_debug.log > glm.log

# Anthropic request (broken)
grep "\[sonnet-4-5\]" proxy_debug.log > anthropic.log

# Compare tool schemas
grep "TOOLS_SCHEMA" glm.log > glm_tools.txt
grep "TOOLS_SCHEMA" anthropic.log > anthropic_tools.txt
diff glm_tools.txt anthropic_tools.txt
```

## Windows PowerShell Equivalents

```powershell
# Find request by ID
Select-String -Path proxy_debug.log -Pattern "\[a45e1d59\]"

# See tool schemas
Select-String -Path proxy_debug.log -Pattern "TOOLS_SCHEMA" -Context 0,50

# See tool conversions
Select-String -Path proxy_debug.log -Pattern "TOOL_CONVERSION" -Context 0,20

# Extract to file
Select-String -Path proxy_debug.log -Pattern "RAW CLIENT REQUEST" -Context 0,100 | Out-File client_req.txt
```

## Real-World Example

**Problem**: Cursor's plan tool creates `f.plan.md` instead of proper filename

**Debug Steps**:
```bash
# 1. Find the request where plan tool was called
grep -n "plan" proxy_debug.log | grep -i "tool"

# 2. Get the request ID from line number
# Let's say it's [abc123]

# 3. See what Cursor sent for the plan tool
grep "\[abc123\]" proxy_debug.log | grep -A 50 "TOOLS_SCHEMA"

# 4. See what parameters the model used
grep "\[abc123\]" proxy_debug.log | grep -A 30 "TOOL_CONVERSION"

# 5. Look at the specific parameter
grep "\[abc123\]" proxy_debug.log | grep -i "target_file\|filename"
```

## Tips

1. **Always get the request ID first** - Makes filtering much easier
2. **Use -A (after) and -B (before) context** - Shows surrounding lines
3. **Pipe to less for long output** - `grep ... | less`
4. **Save to files for comparison** - Easier to diff
5. **Use -i for case-insensitive** - Catches more matches
