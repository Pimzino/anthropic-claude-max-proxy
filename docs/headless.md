# Headless Operation

LLMux can run without user prompts, making it suitable for CI/CD pipelines, Docker containers, and remote servers.

## Running in Headless Mode

Start the proxy without interactive prompts by adding `--headless` to the CLI invocation:

```bash
python cli.py --headless
```

You can combine `--headless` with other options:

- `--bind 127.0.0.1` to override the bind address.
- `--no-auto-start` to skip automatically launching the proxy server after authentication.
- `--debug` to enable verbose logging.
- `--token <value>` to supply a token explicitly on the command line.

## Authentication Strategies

Headless mode requires valid provider tokens before starting. Use one of the following approaches:

### 1. Long-Term Token (Recommended)

Generate a 1-year Anthropic token with the helper command:

```bash
python cli.py --setup-token
```

This does the normal OAuth browser flow, saves the long-term token, and displays it for reuse elsewhere. After running this, `python cli.py --headless` works on the same machine without extra setup.

### 2. Reuse Saved OAuth Tokens

Authenticate interactively once via `python cli.py`, then rerun in headless mode. The proxy refreshes short-lived tokens automatically using the stored refresh token.

### 3. Provide Tokens Explicitly

You can provide tokens through environment variables or CLI flags:

```bash
# Environment variable
export ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."
python cli.py --headless

# CLI flag
python cli.py --headless --token "sk-ant-oat01-..."
```

## Container & CI Examples

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Provide tokens through environment variables or secrets
ENV ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."

CMD ["python", "cli.py", "--headless"]
```

### docker-compose

```yaml
version: '3.8'
services:
  llmux:
    build: .
    ports:
      - "8081:8081"
    environment:
      - ANTHROPIC_OAUTH_TOKEN=${ANTHROPIC_OAUTH_TOKEN}
    command: python cli.py --headless
```

## Runtime Behavior

When running headless, the CLI:

1. Detects tokens from explicit input or saved files.
2. Validates them, saving new tokens when provided.
3. Auto-refreshes OAuth tokens that carry a refresh token.
4. Starts the proxy server automatically unless disabled.
5. Handles graceful shutdowns on SIGINT/SIGTERM.
6. Fails fast with a clear error if authentication is missing or invalid.
