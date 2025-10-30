# Headless Mode Implementation

## Overview

This document explains how headless mode works in the Anthropic Claude Max Proxy, including the discovery of the long-term token mechanism.

## The Discovery

Through packet capture analysis of the official `claude setup-token` command, we discovered that Claude Code requests **1-year tokens** by including an `expires_in` parameter in the OAuth token exchange request:

```json
{
  "grant_type": "authorization_code",
  "code": "...",
  "redirect_uri": "http://localhost:63081/callback",
  "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
  "code_verifier": "...",
  "state": "...",
  "expires_in": 31536000  // <-- This is the key! (365 days in seconds)
}
```

The response confirms the 1-year validity:

```json
{
  "token_type": "Bearer",
  "access_token": "sk-ant-oat01-...",
  "expires_in": 31536000,  // 1 year
  "refresh_token": "sk-ant-ort01-...",
  "scope": "user:inference"
}
```

### Critical Discovery: Scope Limitation

**Important:** Custom `expires_in` values are **only allowed with the `user:inference` scope**.

If you request other scopes like `user:profile` or `org:create_api_key`, Anthropic will reject the custom `expires_in` with:

```json
{
  "error": "invalid_request",
  "error_description": "Custom expires_in not allowed for scope 'user:profile'"
}
```

This is why our implementation uses **two different OAuth flows**:

1. **Regular OAuth** (short-lived): Uses `org:create_api_key user:profile user:inference` scopes
2. **Long-term token**: Uses **only** `user:inference` scope to allow custom expiry

## Implementation

### Token Types

The proxy now supports two types of OAuth tokens:

| Type | Validity | Auto-Refresh | Use Case |
|------|----------|--------------|----------|
| **OAuth Flow** | ~1 hour | ✅ Yes (via refresh token) | Interactive use |
| **Long-Term** | 1 year | ❌ No | Headless/Production |

### Storage Schema

Tokens are stored with a `token_type` field:

```json
{
  "token_type": "long_term",  // or "oauth_flow"
  "access_token": "sk-ant-oat01-...",
  "refresh_token": "sk-ant-ort01-...",  // only for oauth_flow
  "expires_at": 1234567890
}
```

### Key Files Modified

1. **storage.py**
   - Added `save_long_term_token()` method
   - Added `token_type` field to token storage
   - Added `is_long_term_token()` helper
   - Updated status display to show days for long-term tokens

2. **oauth.py**
   - Added `exchange_code_for_long_term_token()` method
   - Includes `"expires_in": 31536000` in token request
   - Added `is_long_term_token_format()` validator
   - Updated refresh logic to skip long-term tokens

3. **auth_cli.py**
   - Added `setup_long_term_token()` method
   - Handles the OAuth flow specifically for 1-year tokens

4. **cli.py**
   - Added `--headless` mode
   - Added `--setup-token` command
   - Added `--token` argument for direct token input
   - Added `--no-auto-start` flag
   - Added `run_headless()` method with graceful shutdown

5. **settings.py**
   - Added `ANTHROPIC_OAUTH_TOKEN` environment variable support

## Usage Examples

### Generate Long-Term Token

```bash
# Method 1: CLI command
python cli.py --setup-token

# Method 2: Interactive menu
python cli.py
# Select option 6
```

Output:
```
✓ Long-term token generated successfully!

Your OAuth Token:
sk-ant-oat01-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

IMPORTANT:
• This token is valid for 1 year (365 days)
• Store this token securely
• You can use it with: export ANTHROPIC_OAUTH_TOKEN="<token>"
• Or pass it via: python cli.py --headless --token "<token>"
```

### Run Headless

```bash
# Using environment variable
export ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."
python cli.py --headless

# Using CLI argument
python cli.py --headless --token "sk-ant-oat01-..."

# Using saved tokens (from previous interactive login)
python cli.py --headless
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

ENV ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."

CMD ["python", "cli.py", "--headless"]
```

## Technical Details

### OAuth Endpoint

```
POST https://console.anthropic.com/v1/oauth/token
```

### Request Differences

**Regular OAuth (short-lived):**
```json
{
  "grant_type": "authorization_code",
  "code": "...",
  "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
  "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
  "code_verifier": "...",
  "scope": "org:create_api_key user:profile user:inference"
  // No expires_in parameter
}
```

**Long-Term Token (1 year):**
```json
{
  "grant_type": "authorization_code",
  "code": "...",
  "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
  "redirect_uri": "https://console.anthropic.com/oauth/code/callback",
  "code_verifier": "...",
  "scope": "user:inference",  // Minimal scope required for custom expires_in
  "expires_in": 31536000  // Request 1-year validity
}
```

**Key Differences:**
1. Long-term tokens use **only** `user:inference` scope (not `user:profile` or `org:create_api_key`)
2. Long-term tokens include `expires_in: 31536000` parameter
3. Both use the same OAuth endpoint and flow

### Token Format

All OAuth tokens follow the format:
```
sk-ant-oat01-[base64-encoded-data]
```

Where:
- `sk` = Secret Key
- `ant` = Anthropic
- `oat` = OAuth Token
- `01` = Version

## Security Considerations

1. **Long-term tokens cannot be refreshed** - When they expire after 1 year, you must generate a new one
2. **Store tokens securely** - Use environment variables or secret management systems
3. **File permissions** - Token files are automatically set to 600 (owner read/write only) on Unix systems
4. **No token in logs** - Tokens are never logged in debug output

## Headless Mode Behavior

When running `python cli.py --headless`:

1. Checks for authentication in this order:
   - CLI `--token` argument
   - `ANTHROPIC_OAUTH_TOKEN` environment variable
   - Saved tokens from previous login

2. Validates token format (must start with `sk-ant-oat01-`)

3. Saves token if provided via CLI/env

4. For OAuth flow tokens: Attempts auto-refresh if expired

5. For long-term tokens: Fails if expired (no refresh available)

6. Starts server automatically (unless `--no-auto-start`)

7. Runs in foreground with graceful shutdown on SIGINT/SIGTERM

## Comparison with Claude Code

Our implementation now **exactly matches** Claude Code's `setup-token` behavior:

| Feature | Claude Code | Our Implementation |
|---------|-------------|-------------------|
| Token validity | 1 year | ✅ 1 year |
| OAuth endpoint | console.anthropic.com | ✅ Same |
| Request parameter | `expires_in: 31536000` | ✅ Same |
| Token format | `sk-ant-oat01-...` | ✅ Same |
| Headless support | ✅ Yes | ✅ Yes |

## Future Enhancements

Potential improvements:

1. **Token expiry warnings** - Notify when long-term token is nearing expiration
2. **Automatic token rotation** - Generate new token before expiration
3. **Multiple token support** - Switch between different accounts
4. **Token encryption** - Encrypt tokens at rest

## Troubleshooting

### Error: "Custom expires_in not allowed for scope 'user:profile'"

**Cause:** You're trying to use a regular OAuth token with custom expiry.

**Solution:** Use the `--setup-token` command which uses the correct minimal scope (`user:inference` only):

```bash
python cli.py --setup-token
```

### Error: "No authentication tokens found"

**Cause:** No tokens are stored and no token was provided.

**Solutions:**
1. Set environment variable: `export ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."`
2. Use CLI argument: `python cli.py --headless --token "sk-ant-oat01-..."`
3. Login first: `python cli.py` → Select option 2 → Then run headless

### Error: "Invalid token format"

**Cause:** Token doesn't match expected format.

**Solution:** Ensure token starts with `sk-ant-oat01-` and contains only valid characters (alphanumeric, hyphens, underscores).

### Long-term token expired after 1 year

**Cause:** Long-term tokens cannot be refreshed.

**Solution:** Generate a new long-term token:

```bash
python cli.py --setup-token
```

### Regular OAuth tokens keep expiring

**Cause:** You're using regular OAuth flow tokens (1 hour expiry) instead of long-term tokens.

**Solution:**
- For headless mode, use `--setup-token` to generate a 1-year token
- Or let the proxy auto-refresh (it will use the refresh token automatically)
