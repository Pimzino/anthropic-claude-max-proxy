# Timeout Configuration

## Overview

The proxy now uses industry-standard timeout configurations with separate settings for different types of requests.

## Timeout Types

### 1. Connection Timeout (`CONNECT_TIMEOUT`)
- **Default**: 10 seconds
- **Purpose**: Maximum time to establish a TCP connection with the API server
- **Industry Standard**: 5-10 seconds
- **Why**: Connection establishment should be fast. If it takes longer, the server is likely down or unreachable.

### 2. Read Timeout (`READ_TIMEOUT`)
- **Default**: 60 seconds
- **Purpose**: Maximum time between receiving data chunks (for streaming)
- **Why**: Detects stalled streams without terminating active ones. If no data arrives for 60 seconds, the stream is likely dead.

### 3. Request Timeout (`REQUEST_TIMEOUT`)
- **Default**: 120 seconds (2 minutes)
- **Purpose**: Total timeout for non-streaming requests
- **Why**: Sufficient for most API requests, including complex operations, without being excessive.

### 4. Stream Timeout (`STREAM_TIMEOUT`)
- **Default**: 600 seconds (10 minutes)
- **Purpose**: Total timeout for streaming requests
- **Why**: LLM streaming responses can take several minutes for complex reasoning tasks, long documents, or detailed code generation.

## Configuration

All timeout values can be configured in your `config.json` file:

```json
{
  "api": {
    "timeouts": {
      "connect": 10,
      "read": 60,
      "request": 120,
      "stream": 600
    }
  }
}
```

## Implementation Details

### Non-Streaming Requests
Uses `httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)`:
- Total request time: 120 seconds
- Connection establishment: 10 seconds

### Streaming Requests
Uses `httpx.Timeout(STREAM_TIMEOUT, connect=CONNECT_TIMEOUT, read=READ_TIMEOUT)`:
- Total stream time: 600 seconds
- Connection establishment: 10 seconds
- Time between chunks: 60 seconds

## Affected Files

- `settings.py` - Timeout constant definitions
- `config.example.json` - Default configuration values
- `proxy.py` - Imports timeout constants
- `anthropic.py` - Uses timeouts for Anthropic API requests
- `custom_provider.py` - Uses timeouts for custom provider requests

## Migration from Previous Configuration

**Old configuration** (single timeout):
```json
{
  "api": {
    "request_timeout": 600
  }
}
```

**New configuration** (granular timeouts):
```json
{
  "api": {
    "timeouts": {
      "connect": 10,
      "read": 60,
      "request": 120,
      "stream": 600
    }
  }
}
```

The old `request_timeout` setting is no longer used. Update your `config.json` to use the new structure.

## Benefits

1. **Faster failure detection**: 10-second connection timeout quickly identifies dead servers
2. **Better stream monitoring**: 60-second read timeout detects stalled streams
3. **Optimized for use case**: Different timeouts for streaming vs non-streaming
4. **Industry-aligned**: Follows best practices from major API providers
5. **Prevents premature termination**: Long streaming requests won't timeout during active generation

## Troubleshooting

### "Connection timeout" errors
- Check if the API server is reachable
- Verify network connectivity
- Consider increasing `connect` timeout if on a slow network

### "Stream timeout" errors
- The stream took longer than 10 minutes
- Consider increasing `stream` timeout for very long generations
- Check if the stream actually stalled (no data for 60+ seconds)

### "Read timeout" errors
- No data received for 60 seconds during streaming
- The stream may have stalled on the server side
- Consider increasing `read` timeout if legitimate pauses are expected
