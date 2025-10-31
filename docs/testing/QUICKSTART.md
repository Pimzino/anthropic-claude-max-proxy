# Testing Quick Start Guide

Get started with testing ccmaxproxy in 5 minutes!

## Step 1: Install Dependencies

```powershell
# Make sure you're in the project root
cd d:\LLMProxy\ccmaxproxy

# Activate virtual environment (if using one)
.\venv\Scripts\Activate.ps1

# Install development dependencies
pip install -r requirements-dev.txt
```

## Step 2: Run Your First Tests

```powershell
# Run all tests
make test

# Or use pytest directly
pytest
```

You should see output like:

```
======================= test session starts =======================
collected 38 items

tests/unit/test_oauth/test_pkce.py ......                   [ 15%]
tests/unit/test_oauth/test_validators.py ....               [ 26%]
tests/unit/test_utils/test_storage.py ........              [ 47%]
tests/unit/test_models/test_resolution.py .........         [ 71%]
tests/integration/test_endpoints.py ........                [100%]

======================= 38 passed in 2.14s ========================
```

## Step 3: Generate Coverage Report

```powershell
# Run tests with coverage
make test-cov

# Open the HTML report
# File: htmlcov/index.html
```

## Step 4: Run Specific Test Suites

```powershell
# Only unit tests (fast)
make test-unit

# Only integration tests
make test-integration

# Specific test file
pytest tests/unit/test_oauth/test_pkce.py -v

# Specific test
pytest tests/unit/test_oauth/test_pkce.py::TestPKCE::test_generate_pkce_pair -v
```

## Step 5: Write Your First Test

Create a new test file:

```python
# tests/unit/test_example.py
import pytest

@pytest.mark.unit
class TestExample:
    """Example test suite"""
    
    def test_something(self):
        """Test something important"""
        result = 2 + 2
        assert result == 4
```

Run it:

```powershell
pytest tests/unit/test_example.py -v
```

## Common Commands

### Testing

| Command | What it does |
|---------|--------------|
| `make test` | Run all tests (unit + integration) |
| `make test-unit` | Run only unit tests |
| `make test-integration` | Run only integration tests |
| `make test-cov` | Run tests with coverage report |
| `pytest -v` | Run all tests with verbose output |
| `pytest -k "test_name"` | Run tests matching name pattern |
| `pytest -m unit` | Run tests with specific marker |

### Code Quality

| Command | What it does |
|---------|--------------|
| `make format` | Format code with black |
| `make lint` | Run linters and auto-fix |
| `make check` | Check code quality (no changes) |

### Utilities

| Command | What it does |
|---------|--------------|
| `make clean` | Remove build artifacts and cache |
| `make help` | Show all available commands |

## Using Fixtures

Fixtures are pre-defined test data you can use in your tests:

```python
def test_with_token(valid_oauth_token):
    """Test using a valid OAuth token fixture"""
    assert valid_oauth_token['token_type'] == 'Bearer'
    assert 'access_token' in valid_oauth_token

def test_with_storage(mock_token_storage):
    """Test using a mocked TokenStorage"""
    mock_token_storage.save_tokens("token", "refresh", 3600)
    assert mock_token_storage.is_authenticated() is True
```

See `tests/conftest.py` for all available fixtures.

## Testing Async Code

For async functions, just use `async def`:

```python
async def test_async_function():
    """Test an async function"""
    result = await some_async_function()
    assert result is not None
```

pytest-asyncio automatically detects and runs async tests.

## Mocking External APIs

Use `respx` to mock HTTP calls:

```python
import respx
from httpx import Response

@respx.mock
async def test_api_call():
    """Test with mocked API"""
    # Mock the endpoint
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, json={"id": "msg_123"})
    )
    
    # Your test code that calls the API
    response = await make_request()
    assert response.status_code == 200
```

## Debugging Failed Tests

### See detailed output

```powershell
# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb
```

### Check specific test

```powershell
# Run one test file
pytest tests/unit/test_oauth/test_pkce.py -v

# Run one test class
pytest tests/unit/test_oauth/test_pkce.py::TestPKCE -v

# Run one test method
pytest tests/unit/test_oauth/test_pkce.py::TestPKCE::test_generate_pkce_pair -v
```

## Checking Coverage

### Which files need tests?

```powershell
# Show missing lines
pytest --cov=oauth --cov-report=term-missing

# Generate HTML report
pytest --cov=oauth --cov-report=html
# Open htmlcov/index.html
```

### Focus on specific package

```powershell
# OAuth package only
pytest tests/unit/test_oauth/ --cov=oauth

# Converters package only
pytest tests/unit/test_converters/ --cov=openai_compat

# Models package only
pytest tests/unit/test_models/ --cov=models
```

## Testing Best Practices

1. **One test, one concept**
   ```python
   # Good
   def test_valid_token():
       assert validate("sk-ant-sid01-xyz") is True
   
   def test_invalid_token():
       assert validate("invalid") is False
   
   # Bad - testing too many things
   def test_tokens():
       assert validate("sk-ant-sid01-xyz") is True
       assert validate("invalid") is False
       storage = TokenStorage()
       # ...
   ```

2. **Descriptive names**
   ```python
   # Good
   def test_save_token_creates_file():
   def test_expired_token_returns_none():
   
   # Bad
   def test_token():
   def test_1():
   ```

3. **Use fixtures**
   ```python
   # Good - use fixture
   def test_something(mock_token_storage):
       mock_token_storage.save_tokens(...)
   
   # Bad - setup in every test
   def test_something():
       storage = TokenStorage()
       storage.save_tokens(...)
   ```

## Common Issues

### Import errors

**Problem**: `ModuleNotFoundError: No module named 'pytest'`

**Solution**:
```powershell
pip install -r requirements-dev.txt
```

### Tests not found

**Problem**: `collected 0 items`

**Solution**: Make sure you're in the project root:
```powershell
cd d:\LLMProxy\ccmaxproxy
pytest
```

### Async warnings

**Problem**: Warnings about async tests

**Solution**: `pytest-asyncio` should be installed:
```powershell
pip install pytest-asyncio
```

## Next Steps

- 📖 Read the [Testing Guide](TESTING.md) for complete documentation
- 📝 Check [Writing Tests](WRITING_TESTS.md) for advanced patterns
- 🏗️ See [Test Architecture](TEST_ARCHITECTURE.md) for structure details
- 📊 Review [Coverage Guide](COVERAGE.md) for coverage requirements

## Getting Help

- Check existing tests for examples
- See documentation in `docs/testing/`
- Open an issue on GitHub
- Ask in the project Discord/community

---

**Happy Testing!** 🎉

Remember: Good tests make code changes fearless!
