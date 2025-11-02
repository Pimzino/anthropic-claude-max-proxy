# Authentication

LLMux authenticates to provider accounts through their OAuth flows and stores the resulting tokens for proxy requests. Use this guide when you need to renew access or understand how each provider exchange works.

## Anthropic Claude

- **API endpoint:** `https://api.anthropic.com/v1/messages`
- **Headers:** Requests include beta feature headers such as `oauth-2025-04-20`, and conditionally `context-1m-2025-08-07` and `interleaved-thinking-2025-05-14` based on the selected model features.
- **OAuth flow:**
  1. Begin at `https://claude.ai/oauth/authorize` (set `code=true`).
  2. The browser redirects to `https://console.anthropic.com/oauth/code/callback`.
  3. Exchange the authorization code at `https://console.anthropic.com/v1/oauth/token`.
  4. Use the returned access token via the `Authorization: Bearer <token>` header for all downstream calls.
- **Cache behavior:** LLMux automatically applies ephemeral cache control on system messages and maintains a small cache of the last two user messages for better performance.

## ChatGPT (OpenAI)

- **API endpoint:** `https://chatgpt.com/backend-api/codex/responses`
- **OAuth flow:**
  1. Start authentication at `https://auth.openai.com/oauth/authorize`.
  2. The callback returns to `http://localhost:1455/auth/callback`.
  3. Exchange the authorization code at `https://auth.openai.com/oauth/token`.
  4. Use the resulting access token via the `Authorization: Bearer <token>` header.
- **Additional headers:** A `chatgpt-account-id` header is included to identify the account when relaying requests.
- **Token storage:** Tokens are saved to `~/.llmux/chatgpt/tokens.json`. Legacy locations such as `~/.chatgpt-local/tokens.json` are migrated automatically.

## Token Management Tips

- Run `python cli.py` and choose **Authentication** from the menu to launch the interactive OAuth process for either provider.
- Use the `python cli.py --setup-token` helper to mint a long-lived (365-day) token after authenticating Anthropic once. The proxy saves the token and prints it for reuse on other machines.
- Short-lived OAuth tokens include refresh tokens, so the proxy renews them automatically during normal operation.
- For headless or container deployments, pass tokens explicitly via environment variables or CLI flags. See `docs/headless.md` for details.
