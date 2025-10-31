# Smoke Tests

⚠️ **WARNING**: These tests make real API calls to Anthropic and may incur costs!

## What are Smoke Tests?

Smoke tests validate that the proxy can successfully communicate with the real Anthropic API. Unlike unit and integration tests that use mocks, these tests make actual HTTP requests.

## When to Run Smoke Tests

- After major changes to API communication code
- Before releasing a new version
- To validate OAuth token functionality
- To verify API format compatibility

## Requirements

1. **Valid OAuth Token**: You need a valid Anthropic OAuth token (Pro or Max subscription)
2. **Explicit Opt-In**: Set `ENABLE_SMOKE_TESTS=1` environment variable

## How to Run

### Generate an OAuth Token

First, generate a long-term token:

```powershell
# PowerShell
python cli.py --setup-token
```

This will open your browser and generate a 1-year token.

### Run the Tests

```powershell
# PowerShell
$env:ENABLE_SMOKE_TESTS="1"
$env:ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-your-token-here"
pytest tests/smoke/ -v
```

Or use the Makefile:

```powershell
make test-smoke
```

## Cost Considerations

- Each test sends a small request (< 100 tokens typically)
- Total cost per test run: negligible (< $0.01)
- Tests use Claude Sonnet 4 by default
- All requests are designed to be minimal

## Test Coverage

Current smoke tests cover:

- ✅ Basic message sending
- ✅ System message handling
- ✅ Token usage reporting
- ✅ Streaming responses
- ✅ Error handling

## Skipping Smoke Tests

By default, smoke tests are **automatically skipped** if:

1. `ENABLE_SMOKE_TESTS` is not set to `1`
2. `ANTHROPIC_OAUTH_TOKEN` is not set

When running the full test suite with `make test` or `pytest`, smoke tests are skipped automatically.

## CI/CD Integration

Smoke tests are **not run** in CI/CD pipelines by default to avoid:

- API costs
- Token management complexity
- External dependencies

Only run smoke tests manually when needed.
