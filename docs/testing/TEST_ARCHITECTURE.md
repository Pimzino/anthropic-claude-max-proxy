# Test Architecture

This document describes the architecture and organization of the ccmaxproxy test suite.

## Overview

The test suite is designed with three tiers:

1. **Unit Tests** - Fast, isolated component testing
2. **Integration Tests** - Component interaction and API endpoint testing  
3. **Smoke Tests** - Real API validation (opt-in)

## Directory Structure

```
tests/
├── __init__.py                 # Test package marker
├── conftest.py                 # Shared fixtures for all tests
├── fixtures/                   # Test data and fixtures
│   ├── __init__.py
│   ├── loader.py               # Fixture loading utilities
│   ├── anthropic_responses.json
│   ├── openai_requests.json
│   ├── tokens.json
│   └── models_config.json
├── unit/                       # Unit tests (fast, isolated)
│   ├── test_oauth/
│   │   ├── __init__.py
│   │   ├── test_pkce.py
│   │   ├── test_validators.py
│   │   ├── test_token_exchange.py
│   │   ├── test_token_refresh.py
│   │   └── test_token_manager.py
│   ├── test_converters/
│   │   ├── __init__.py
│   │   ├── test_request_converter.py
│   │   ├── test_response_converter.py
│   │   ├── test_stream_converter.py
│   │   ├── test_message_converter.py
│   │   └── test_tool_converter.py
│   ├── test_models/
│   │   ├── __init__.py
│   │   ├── test_resolution.py
│   │   ├── test_registry.py
│   │   ├── test_reasoning.py
│   │   └── test_custom_models.py
│   ├── test_utils/
│   │   ├── __init__.py
│   │   ├── test_storage.py
│   │   └── test_thinking_cache.py
│   └── test_config/
│       ├── __init__.py
│       └── test_loader.py
├── integration/                # Integration tests
│   ├── __init__.py
│   ├── test_endpoints.py       # All API endpoints
│   ├── test_streaming_flow.py  # End-to-end streaming
│   ├── test_custom_providers.py
│   └── test_oauth_flow.py
└── smoke/                      # Smoke tests (opt-in, real API)
    ├── __init__.py
    ├── conftest.py             # Smoke test configuration
    ├── test_real_anthropic.py
    ├── test_real_streaming.py
    └── README.md               # Usage instructions
```

## Test Categories

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation

**Characteristics**:
- **Fast**: Run in milliseconds
- **Isolated**: No external dependencies
- **Mocked**: All I/O and network calls mocked
- **Deterministic**: Same input always produces same output

**Coverage Areas**:

| Package | Test Coverage | Key Tests |
|---------|--------------|-----------|
| `oauth/` | Token validation, PKCE generation, token exchange/refresh logic | `test_pkce.py`, `test_validators.py`, `test_token_manager.py` |
| `openai_compat/` | Request/response conversion, streaming, tool handling | `test_request_converter.py`, `test_response_converter.py`, `test_stream_converter.py` |
| `models/` | Model resolution, variant parsing, registry building | `test_resolution.py`, `test_registry.py`, `test_custom_models.py` |
| `utils/` | Token storage, thinking cache | `test_storage.py`, `test_thinking_cache.py` |
| `config/` | Configuration loading, env vars | `test_loader.py` |

**Example Structure**:
```python
@pytest.mark.unit
class TestPKCE:
    """Test suite for PKCE functionality"""
    
    def test_generate_pkce_pair(self):
        """Test PKCE pair generation"""
        code_verifier, code_challenge = generate_pkce_pair()
        assert len(code_verifier) >= 43
        assert len(code_challenge) > 0
```

### Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions and API endpoints

**Characteristics**:
- **Medium Speed**: Run in seconds
- **Partial Mocking**: External APIs mocked, internal calls real
- **End-to-End Flows**: Test complete request/response cycles
- **FastAPI TestClient**: Use real HTTP server in test mode

**Coverage Areas**:

| Test File | Coverage |
|-----------|----------|
| `test_endpoints.py` | All 5 API endpoints (`/health`, `/v1/models`, `/oauth/status`, `/v1/messages`, `/v1/chat/completions`) |
| `test_streaming_flow.py` | SSE streaming for both Anthropic and OpenAI formats |
| `test_custom_providers.py` | Custom provider routing and OpenAI passthrough |
| `test_oauth_flow.py` | Complete OAuth authorization and token exchange flow |

**Example Structure**:
```python
@pytest.mark.integration
class TestOpenAIChatEndpoint:
    """Test suite for /v1/chat/completions"""
    
    @respx.mock
    @patch('proxy.endpoints.openai_chat.oauth_manager')
    async def test_simple_chat_completion(
        self,
        mock_manager,
        fastapi_test_client,
    ):
        # Mock OAuth and Anthropic API
        mock_manager.get_valid_token_async = AsyncMock(return_value="token")
        respx.post("https://api.anthropic.com/v1/messages").mock(...)
        
        # Test endpoint
        response = fastapi_test_client.post("/v1/chat/completions", json={...})
        assert response.status_code == 200
```

### Smoke Tests (`tests/smoke/`)

**Purpose**: Validate real API communication

**Characteristics**:
- **Slow**: Make real network calls
- **Opt-In**: Explicitly enabled via environment variable
- **Real Costs**: May incur small API charges
- **Validation**: Confirm API format compatibility

**Coverage Areas**:

| Test File | Coverage |
|-----------|----------|
| `test_real_anthropic.py` | Basic messages, system messages, token usage |
| `test_real_streaming.py` | Real SSE streaming, thinking blocks, tool use |

**Example Structure**:
```python
@pytest.mark.smoke
@pytest.mark.slow
class TestRealAnthropicAPI:
    """Smoke tests for real API"""
    
    async def test_simple_message(self, real_oauth_token, smoke_test_enabled):
        """Test real Anthropic API call"""
        response = await make_anthropic_request({...}, real_oauth_token, None)
        assert response.status_code == 200
```

**Opt-In Mechanism**:
```powershell
# Smoke tests are skipped by default
pytest  # Skips smoke tests

# Enable explicitly
$env:ENABLE_SMOKE_TESTS="1"
$env:ANTHROPIC_OAUTH_TOKEN="sk-ant-oat01-..."
pytest tests/smoke/
```

## Fixtures System

### Shared Fixtures (`tests/conftest.py`)

Global fixtures available to all tests:

| Fixture | Purpose | Usage |
|---------|---------|-------|
| `temp_token_file` | Temporary token storage file | Testing TokenStorage without side effects |
| `mock_token_storage` | TokenStorage instance with temp file | Quick TokenStorage setup |
| `valid_oauth_token` | Valid OAuth token dict | Testing with valid auth |
| `expired_oauth_token` | Expired OAuth token dict | Testing token expiry |
| `long_term_token` | Long-term OAuth token dict | Testing long-term tokens |
| `mock_anthropic_text_response` | Sample Anthropic response | Mocking API responses |
| `mock_anthropic_tool_response` | Tool use response | Testing tool handling |
| `openai_simple_request` | Basic OpenAI request | Testing request conversion |
| `openai_tools_request` | OpenAI request with tools | Testing tool conversion |
| `fastapi_test_client` | FastAPI TestClient | Testing endpoints |
| `mock_httpx_client` | respx mock for httpx | Mocking HTTP calls |
| `mock_oauth_manager` | Mocked OAuthManager | Testing without real auth |

### Fixture Data (`tests/fixtures/`)

JSON files with reusable test data:

| File | Contents |
|------|----------|
| `anthropic_responses.json` | Sample Anthropic API responses (text, tools, thinking, streaming) |
| `openai_requests.json` | Sample OpenAI requests (basic, tools, reasoning, vision) |
| `tokens.json` | Token structures (valid, expired, long-term, refresh) |
| `models_config.json` | Custom model configurations for testing |

**Loading Fixtures**:
```python
from tests.fixtures.loader import get_anthropic_response, get_openai_request

response = get_anthropic_response("tool_use_response")
request = get_openai_request("with_reasoning")
```

## Mocking Strategy

### What to Mock

| Component | Mock? | Reason |
|-----------|-------|--------|
| External HTTP calls (Anthropic API) | ✅ Yes | Avoid rate limits, costs, network issues |
| Custom provider APIs | ✅ Yes | Same as above |
| File I/O (token storage) | ✅ Yes | Use temp files instead of real storage |
| OAuth browser flow | ✅ Yes | Can't automate browser in tests |
| Time (for expiry tests) | ⚠️ Sometimes | Use `freezegun` when testing time-sensitive code |
| Configuration loading | ⚠️ Sometimes | Use `monkeypatch` for env vars |
| Internal converters | ❌ No | Test real implementation |
| Model registry | ❌ No | Test real implementation |

### Mocking Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `respx` | Mock httpx requests | `respx.post("https://api.anthropic.com/...").mock(...)` |
| `unittest.mock` | Mock Python objects/functions | `@patch('module.function')` |
| `AsyncMock` | Mock async functions | `mock.return_value = AsyncMock(return_value=...)` |
| `monkeypatch` | Modify env vars, attributes | `monkeypatch.setenv("PORT", "9000")` |
| `freezegun` | Mock datetime | `@freeze_time("2025-10-31")` |

## Test Markers

Tests use markers for categorization and selective execution:

| Marker | Purpose | Command |
|--------|---------|---------|
| `@pytest.mark.unit` | Unit test | `pytest -m unit` |
| `@pytest.mark.integration` | Integration test | `pytest -m integration` |
| `@pytest.mark.smoke` | Smoke test (real API) | `pytest -m smoke` |
| `@pytest.mark.slow` | Slow test (> 1 second) | `pytest -m "not slow"` |

**Combining Markers**:
```powershell
# Run fast unit tests only
pytest -m "unit and not slow"

# Run integration and unit, skip smoke
pytest -m "unit or integration"
```

## Coverage Configuration

### Coverage Targets

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| OAuth flow | 80%+ | 🔴 Critical |
| Converters | 80%+ | 🔴 Critical |
| Model resolution | 80%+ | 🔴 Critical |
| API endpoints | 80%+ | 🔴 Critical |
| Utils | 70%+ | 🟡 Important |
| CLI | 50%+ | 🟢 Nice to have |

### Exclusions

Files/patterns excluded from coverage (see `pytest.ini`):

- `*/tests/*` - Test files themselves
- `cli.py`, `auth_cli.py` - Legacy entry points
- `stream_debug.py` - Debug utility
- `__pycache__/*` - Bytecode
- `venv/`, `.venv/` - Virtual environments

## CI/CD Integration

### GitHub Actions Workflow

File: `.github/workflows/test.yml`

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: make test-cov
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

**What runs in CI**:
- ✅ Unit tests
- ✅ Integration tests
- ❌ Smoke tests (require tokens, opt-in only)

## Performance Considerations

### Test Speed Targets

| Category | Target Speed | Actual |
|----------|-------------|--------|
| Single unit test | < 10ms | ~5ms |
| Full unit suite | < 5s | ~2s |
| Single integration test | < 500ms | ~200ms |
| Full integration suite | < 30s | ~10s |
| Single smoke test | < 5s | ~3s |
| Full smoke suite | < 30s | ~15s |

### Optimization Strategies

1. **Use fixtures wisely**: Scope fixtures appropriately (`function`, `class`, `module`, `session`)
2. **Parallel execution**: Use `pytest-xdist` for parallel test runs
3. **Mock expensive operations**: Don't make real API calls in unit tests
4. **Minimize I/O**: Use in-memory data structures when possible
5. **Share setup**: Use class/module-scoped fixtures for expensive setup

## Maintenance Guidelines

### When to Add Tests

✅ **Always add tests for**:
- New features
- Bug fixes (regression tests)
- Public APIs
- Critical paths (OAuth, converters, endpoints)

⚠️ **Consider adding tests for**:
- Internal utilities
- Edge cases
- Performance-critical code

❌ **Don't need tests for**:
- Trivial getters/setters
- Third-party library wrappers (unless adding logic)
- Debug/logging utilities

### Keeping Tests Maintainable

1. **DRY**: Use fixtures for repeated setup
2. **Clear names**: Test names should be self-documenting
3. **One assertion focus**: Each test verifies one behavior
4. **Minimal mocking**: Only mock what's necessary
5. **Regular cleanup**: Remove obsolete tests when removing features

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [respx Documentation](https://lundberg.github.io/respx/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

## Next Steps

- **Writing Tests**: See [WRITING_TESTS.md](./WRITING_TESTS.md)
- **Running Tests**: See [TESTING.md](./TESTING.md)
- **Coverage Details**: See [COVERAGE.md](./COVERAGE.md)
