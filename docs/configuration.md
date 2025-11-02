# Configuration

LLMux reads configuration from multiple sources, allowing you to tailor the proxy to your environment.

## Priority Order

1. Environment variables (highest priority)
2. `.env` file
3. Built-in defaults (lowest priority)

## `.env` Setup

1. Copy the provided template: `cp .env.example .env`.
2. Update entries such as the proxy port, bind address, timeouts, or logging options.
3. Environment variables override any `.env` values.

## CLI Flags

Key CLI arguments include:

- `--bind <address>` – override the default bind host (`0.0.0.0`).
- `--port <number>` – set the listening port.
- `--headless` – run without interactive prompts (see `docs/headless.md`).
- `--no-auto-start` – skip automatically launching the server after auth.
- `--debug` – enable verbose logging output.
- `--token <value>` – provide an OAuth token during startup.
- `--setup-token` – run the long-term token helper for Anthropic.

## Environment Variable Tips

Use environment variables when deploying to servers or containers where `.env` files are not ideal. Examples:

- `LLMUX_BIND=127.0.0.1`
- `LLMUX_PORT=8081`
- `ANTHROPIC_OAUTH_TOKEN=sk-ant-oat01-...`
- `OPENAI_API_KEY=dummy` (for clients pointing to LLMux)

Combine environment variables with CLI flags for one-off overrides or to keep secrets outside of the repository.
