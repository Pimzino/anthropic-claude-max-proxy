# Testing Guide

Welcome to the ccmaxproxy testing documentation! This guide covers everything you need to know about running and writing tests for the project.

## Quick Start

### Install Test Dependencies

```powershell
# Install development dependencies
pip install -r requirements-dev.txt
```

### Run All Tests

```powershell
# Using Make (recommended)
make test

# Or using pytest directly
pytest
```

### Run Specific Test Suites

```powershell
# Unit tests only (fast)
make test-unit
# or
pytest tests/unit/ -v

# Integration tests only
make test-integration
# or
pytest tests/integration/ -v

# Smoke tests (requires real API token)
make test-smoke
# or
ENABLE_SMOKE_TESTS=1 pytest tests/smoke/ -v
```

### Run with Coverage

```powershell
# Generate coverage report
make test-cov

# View HTML coverage report
# Open htmlcov/index.html in your browser
```

## Test Organization

The test suite is organized into three main categories:

### 1. Unit Tests (`tests/unit/`)

**Purpose**: Fast, isolated tests that verify individual components

**Characteristics**:
- No external dependencies
- Heavy use of mocks and fixtures
- Run in milliseconds
- High coverage of edge cases

**Structure**:
```
tests/unit/
├── test_oauth/         # OAuth components
│   ├── test_pkce.py
│   ├── test_validators.py
│   └── test_token_manager.py
├── test_models/        # Model registry and resolution
│   ├── test_resolution.py
│   ├── test_reasoning.py
│   └── test_custom_models.py
├── test_utils/         # Utilities
│   ├── test_storage.py
│   └── test_thinking_cache.py
└── test_converters/    # Format converters
    ├── test_request_converter.py
    ├── test_response_converter.py
    └── test_stream_converter.py
```

**When to run**: Always, before every commit

### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions and API endpoints

**Characteristics**:
- Use FastAPI TestClient
- Mock external APIs (Anthropic, custom providers)
- Test request/response flows
- Verify endpoint behavior

**Structure**:
```
tests/integration/
├── test_endpoints.py         # All API endpoints
├── test_streaming_flow.py    # End-to-end streaming
├── test_custom_providers.py  # Custom provider routing
└── test_oauth_flow.py         # OAuth authentication flow
```

**When to run**: Before pushing code, in CI/CD

### 3. Smoke Tests (`tests/smoke/`)

**Purpose**: Validate real API communication

**Characteristics**:
- Make actual API calls
- Require valid OAuth token
- Opt-in only (explicitly enabled)
- May incur small costs

**Structure**:
```
tests/smoke/
├── test_real_anthropic.py    # Real Anthropic API calls
├── test_real_streaming.py    # Real streaming validation
├── conftest.py               # Smoke test configuration
└── README.md                 # Warning and instructions
```

**When to run**: Manually, before releases

See [Smoke Tests Guide](../smoke/README.md) for details.

## Running Tests

### Basic Commands

```powershell
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run tests in parallel (faster)
pytest -n auto

# Run specific test file
pytest tests/unit/test_oauth/test_pkce.py

# Run specific test class
pytest tests/unit/test_oauth/test_pkce.py::TestPKCE

# Run specific test method
pytest tests/unit/test_oauth/test_pkce.py::TestPKCE::test_generate_pkce_pair
```

### Using Markers

Tests are categorized with markers for selective execution:

```powershell
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only smoke tests
pytest -m smoke

# Exclude slow tests
pytest -m "not slow"

# Combine markers
pytest -m "unit and not slow"
```

### Coverage Options

```powershell
# Run with coverage
pytest --cov=.

# Generate HTML report
pytest --cov=. --cov-report=html

# Show missing lines
pytest --cov=. --cov-report=term-missing

# Fail if coverage below 80%
pytest --cov=. --cov-fail-under=80
```

## Makefile Commands

For convenience, use the Makefile:

| Command | Description |
|---------|-------------|
| `make test` | Run all tests (unit + integration) |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make test-smoke` | Run smoke tests (requires tokens) |
| `make test-cov` | Run tests with coverage report |
| `make test-watch` | Auto-run tests on file changes |
| `make lint` | Run linters (ruff, mypy) |
| `make format` | Format code with black |

## Test Configuration

Tests are configured in `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

asyncio_mode = auto
markers =
    unit: Unit tests
    integration: Integration tests
    smoke: Smoke tests (require real API)
    slow: Slow tests
```

## Coverage Requirements

The project maintains **80% code coverage** for critical components:

- ✅ OAuth flow: 80%+
- ✅ Converters: 80%+
- ✅ Model resolution: 80%+
- ✅ API endpoints: 80%+

See [COVERAGE.md](./COVERAGE.md) for details.

## CI/CD Integration

Tests run automatically on:

- Every push to main branch
- Every pull request
- Python versions: 3.8, 3.9, 3.10, 3.11, 3.12

See `.github/workflows/test.yml` for configuration.

## Troubleshooting

### Common Issues

**Import errors when running tests**:
```powershell
# Make sure dev dependencies are installed
pip install -r requirements-dev.txt
```

**Tests can't find modules**:
```powershell
# Run pytest from project root
cd d:\LLMProxy\ccmaxproxy
pytest
```

**Async test warnings**:
```powershell
# Make sure pytest-asyncio is installed
pip install pytest-asyncio
```

**Coverage reports missing**:
```powershell
# Install coverage dependencies
pip install pytest-cov
```

### Getting Help

- 📖 [Writing Tests Guide](./WRITING_TESTS.md)
- 🏗️ [Test Architecture](./TEST_ARCHITECTURE.md)
- 📊 [Coverage Guide](./COVERAGE.md)
- 💬 Open an issue on GitHub

## Next Steps

- **Writing Tests**: See [WRITING_TESTS.md](./WRITING_TESTS.md)
- **Test Architecture**: See [TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md)
- **Contributing**: See main README for contribution guidelines
