# Writing Tests - Contributor Guide

This guide helps you write high-quality tests for ccmaxproxy. Whether you're fixing a bug, adding a feature, or improving coverage, these guidelines will help you write effective tests.

## General Principles

### 1. Test Behavior, Not Implementation

✅ **Good** - Test what the code does:
```python
def test_token_expiry_detection(self):
    """Test that expired tokens are correctly identified"""
    storage = TokenStorage()
    storage.save_tokens("token", "refresh", expires_in=1)
    time.sleep(2)
    assert storage.is_token_expired() is True
```

❌ **Bad** - Test internal implementation:
```python
def test_token_expiry_calculation(self):
    """Test the exact formula for expiry time"""
    storage = TokenStorage()
    # Don't test internal time calculations
    assert storage._expires_at == time.time() + 3600
```

### 2. One Test, One Concept

Each test should verify a single behavior:

✅ **Good**:
```python
def test_valid_oauth_token_format(self):
    """Test validation of valid OAuth token format"""
    token = "sk-ant-sid01-abcdefghijklmnopqrstuvwxyz"
    assert validate_token_format(token) is True

def test_invalid_token_format(self):
    """Test validation of invalid token formats"""
    assert validate_token_format("") is False
    assert validate_token_format("invalid") is False
```

❌ **Bad**:
```python
def test_token_validation(self):
    """Test everything about tokens"""
    # Testing too many things at once
    assert validate_token_format("sk-ant-sid01-test") is True
    assert validate_token_format("invalid") is False
    storage = TokenStorage()
    storage.save_tokens("token", "refresh", 3600)
    assert storage.is_authenticated() is True
```

### 3. Use Descriptive Names

Test names should clearly describe what is being tested:

✅ **Good**:
```python
def test_resolve_model_with_reasoning_variant_high(self):
def test_oauth_token_refresh_after_expiration(self):
def test_convert_openai_tools_to_anthropic_format(self):
```

❌ **Bad**:
```python
def test_model(self):
def test_token(self):
def test_convert(self):
```

## Using Fixtures

### Available Fixtures

from `conftest.py`, common fixtures are readily available:

```python
def test_example(
    mock_token_storage,           # TokenStorage with temp file
    valid_oauth_token,            # Valid token dict
    mock_anthropic_text_response, # Sample Anthropic response
    fastapi_test_client,          # TestClient for endpoints
):
    # Your test code
    pass
```

See `tests/conftest.py` for the full list.

### Creating Custom Fixtures

For test-specific fixtures, define them in the test file or a local `conftest.py`:

```python
@pytest.fixture
def custom_model_config():
    """Custom model configuration for testing"""
    return {
        "id": "test-model",
        "base_url": "https://test.com/v1",
        "api_key": "test-key",
        "context_length": 100000,
    }

def test_custom_model(custom_model_config):
    model_id = custom_model_config["id"]
    assert model_id == "test-model"
```

## Testing Async Code

### Basic Async Tests

Mark async tests with `@pytest.mark.asyncio` (or just use `async def`, pytest-asyncio auto-detects):

```python
import pytest

async def test_async_token_refresh():
    """Test async token refresh"""
    storage = TokenStorage()
    # ... setup ...
    
    result = await refresh_tokens(storage)
    assert result is True
```

### Async Fixtures

```python
@pytest.fixture
async def async_client():
    """Create async HTTP client"""
    async with AsyncClient() as client:
        yield client

async def test_with_async_client(async_client):
    response = await async_client.get("https://example.com")
    assert response.status_code == 200
```

### Mocking Async Functions

Use `AsyncMock` for async functions:

```python
from unittest.mock import AsyncMock, patch

@patch('oauth.token_manager.refresh_tokens')
async def test_with_mocked_refresh(mock_refresh):
    """Test with mocked async function"""
    mock_refresh.return_value = True
    
    result = await some_function_that_calls_refresh()
    assert result is True
    mock_refresh.assert_called_once()
```

## Mocking External APIs

### Using respx for httpx

For mocking `httpx` requests, use `respx`:

```python
import respx
from httpx import Response

@respx.mock
async def test_anthropic_api_call():
    """Test Anthropic API call with mocked response"""
    # Mock the API endpoint
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            200,
            json={
                "id": "msg_123",
                "type": "message",
                "content": [{"type": "text", "text": "Hello"}],
                "usage": {"input_tokens": 10, "output_tokens": 5}
            }
        )
    )
    
    # Make the actual call
    response = await make_anthropic_request({...}, "token", None)
    
    assert response.status_code == 200
    assert response.json()["type"] == "message"
```

### Mocking with Patterns

```python
@respx.mock
async def test_custom_provider():
    """Mock any custom provider URL"""
    # Mock using regex pattern
    respx.post(url__regex=r"https://api\..*/v1/chat/completions").mock(
        return_value=Response(200, json={...})
    )
    
    # Will match api.z.ai, api.openrouter.ai, etc.
    response = await make_request_to_custom_provider()
    assert response.status_code == 200
```

## Testing Endpoints

### Using TestClient

For FastAPI endpoints, use `TestClient`:

```python
def test_health_endpoint(fastapi_test_client):
    """Test health check endpoint"""
    response = fastapi_test_client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

### Testing with Authentication

Mock the OAuth manager:

```python
from unittest.mock import patch, AsyncMock

@patch('proxy.endpoints.openai_chat.oauth_manager')
async def test_chat_endpoint(mock_manager, fastapi_test_client):
    """Test chat endpoint with authentication"""
    # Mock valid token
    mock_manager.get_valid_token_async = AsyncMock(
        return_value="test-token"
    )
    
    response = fastapi_test_client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100
        }
    )
    
    assert response.status_code == 200
```

## Testing with Fixtures

### Using Fixture Data

Load test data from fixtures:

```python
from tests.fixtures.loader import get_openai_request

def test_request_conversion():
    """Test converting OpenAI request"""
    request = get_openai_request("with_tools")
    
    # request contains the fixture data
    assert "tools" in request
    assert len(request["tools"]) > 0
```

### Creating Temporary Files

Use temporary files for testing storage:

```python
def test_token_persistence(temp_token_file):
    """Test token file persistence"""
    storage = TokenStorage(token_file=temp_token_file)
    storage.save_tokens("token", "refresh", 3600)
    
    # Create new instance with same file
    storage2 = TokenStorage(token_file=temp_token_file)
    assert storage2.get_access_token() == "token"
```

## Parameterized Tests

Test multiple scenarios with one test:

```python
@pytest.mark.parametrize("model,expected_base", [
    ("claude-sonnet-4-20250514", "claude-sonnet-4-20250514"),
    ("claude-sonnet-4-20250514-reasoning-low", "claude-sonnet-4-20250514"),
    ("claude-sonnet-4-20250514-1m", "claude-sonnet-4-20250514"),
    ("claude-sonnet-4-20250514-1m-reasoning-high", "claude-sonnet-4-20250514"),
])
def test_strip_model_variants(model, expected_base):
    """Test stripping variants from various model names"""
    result = strip_model_variants(model)
    assert result == expected_base
```

## Testing Streaming

### Testing SSE Streams

```python
async def test_sse_stream_parsing(sample_sse_chunks):
    """Test SSE chunk parsing"""
    events = []
    
    async for chunk in parse_sse_stream(sample_sse_chunks):
        events.append(chunk)
    
    assert len(events) > 0
    assert events[0]["type"] == "message_start"
```

### Testing Stream Conversion

```python
async def test_anthropic_to_openai_stream():
    """Test converting Anthropic stream to OpenAI format"""
    anthropic_chunks = [...]  # Anthropic SSE events
    
    converted_chunks = []
    async for chunk in convert_anthropic_stream_to_openai(
        anthropic_chunks,
        "claude-sonnet-4-20250514",
        "req_123"
    ):
        converted_chunks.append(chunk)
    
    # Verify OpenAI format
    assert b"data: " in converted_chunks[0]
```

## Test Organization Best Practices

### File Organization

```
tests/unit/test_oauth/
├── __init__.py
├── test_pkce.py              # One module, one test file
├── test_validators.py
└── test_token_manager.py
```

### Class Organization

Group related tests in classes:

```python
@pytest.mark.unit
class TestTokenValidators:
    """Test suite for token format validators"""
    
    def test_valid_oauth_token_format(self):
        pass
    
    def test_valid_long_term_token_format(self):
        pass
    
    def test_invalid_token_format(self):
        pass
```

## Code Coverage

### Checking Coverage

```powershell
# Run with coverage
pytest --cov=oauth --cov-report=term-missing

# See which lines are not covered
pytest --cov=oauth --cov-report=html
# Open htmlcov/index.html
```

### Improving Coverage

Focus on:
1. **Happy paths** - Normal usage
2. **Error paths** - What happens when things go wrong
3. **Edge cases** - Boundary conditions, empty inputs, etc.

```python
def test_happy_path():
    """Test normal usage"""
    result = function("valid input")
    assert result == expected

def test_error_handling():
    """Test error conditions"""
    with pytest.raises(ValueError):
        function("invalid input")

def test_edge_case_empty_input():
    """Test with empty input"""
    result = function("")
    assert result is None
```

## Common Patterns

### Testing Exceptions

```python
def test_invalid_request_raises_error():
    """Test that invalid request raises HTTPException"""
    with pytest.raises(HTTPException) as exc_info:
        validate_request({})
    
    assert exc_info.value.status_code == 400
    assert "required" in str(exc_info.value.detail)
```

### Testing Logging

```python
def test_logging_output(caplog):
    """Test that function logs correctly"""
    with caplog.at_level(logging.INFO):
        some_function()
    
    assert "Expected log message" in caplog.text
```

### Testing Environment Variables

```python
def test_with_env_vars(monkeypatch):
    """Test with custom environment variables"""
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    
    config = load_config()
    assert config.port == 9000
```

## Checklist for New Tests

Before submitting your tests:

- [ ] Test names clearly describe what is being tested
- [ ] Each test verifies one behavior
- [ ] Tests are isolated (no shared state between tests)
- [ ] External dependencies are mocked
- [ ] Async tests use proper async fixtures/mocks
- [ ] Tests include assertions (no test without asserts)
- [ ] Tests pass consistently
- [ ] Added appropriate markers (`@pytest.mark.unit`, etc.)
- [ ] Documentation strings explain the test purpose

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [respx Documentation](https://lundberg.github.io/respx/)
- [Testing FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)

## Getting Help

- Check existing tests for examples
- See [TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md) for structure
- Ask questions in GitHub issues
