# Code Coverage Guide

This document describes the code coverage requirements and practices for ccmaxproxy.

## Coverage Requirements

The project maintains a **minimum 80% code coverage** threshold for critical components.

### Coverage Targets by Component

| Component | Target | Priority | Notes |
|-----------|--------|----------|-------|
| **oauth/** | 80%+ | 🔴 Critical | Authentication is security-critical |
| **openai_compat/** | 80%+ | 🔴 Critical | Format conversion must be reliable |
| **models/** | 80%+ | 🔴 Critical | Model resolution affects all requests |
| **proxy/endpoints/** | 80%+ | 🔴 Critical | Public API surface |
| **anthropic/** | 75%+ | 🟡 Important | API client integration |
| **proxy/handlers/** | 75%+ | 🟡 Important | Request/response processing |
| **utils/** | 70%+ | 🟡 Important | Shared utilities |
| **config/** | 70%+ | 🟡 Important | Configuration loading |
| **providers/** | 70%+ | 🟡 Important | Custom provider support |
| **cli/** | 50%+ | 🟢 Nice to have | Interactive UI, hard to test |
| **headers/** | 50%+ | 🟢 Nice to have | Mostly constants |

## Running Coverage Reports

### Basic Coverage

```powershell
# Run tests with coverage
pytest --cov=.

# With missing lines highlighted
pytest --cov=. --cov-report=term-missing
```

### HTML Coverage Report

```powershell
# Generate HTML report
pytest --cov=. --cov-report=html

# Open the report
# Open htmlcov/index.html in your browser
```

### JSON Coverage Report

```powershell
# Generate JSON report
pytest --cov=. --cov-report=json

# View coverage.json
cat coverage.json
```

### Using Makefile

```powershell
# Generate coverage report (HTML + terminal)
make test-cov

# The HTML report will be in htmlcov/
```

## Understanding Coverage Reports

### Terminal Output

```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
oauth/__init__.py                          10      0   100%
oauth/pkce.py                              25      2    92%   45-46
oauth/validators.py                        30      3    90%   67, 89-90
oauth/token_exchange.py                    45      5    89%   120-124
---------------------------------------------------------------------
TOTAL                                     500     40    92%
```

**Columns**:
- **Stmts**: Total statements
- **Miss**: Uncovered statements
- **Cover**: Coverage percentage
- **Missing**: Line numbers not covered

### HTML Report

The HTML report provides:
- 📊 Overall coverage percentage
- 📁 Coverage by directory
- 📄 Coverage by file
- 🔍 Line-by-line coverage highlighting
- 🌿 Branch coverage (if enabled)

**Color Coding**:
- 🟢 Green: Line is covered
- 🔴 Red: Line is not covered
- 🟡 Yellow: Partial branch coverage

## What Counts as Coverage

### Covered Lines

✅ A line is covered if:
- It was executed during test runs
- All branches (if/else) were taken
- Exception handlers were triggered

### Not Covered

❌ A line is not covered if:
- Never executed
- Branch not taken (e.g., else clause not tested)
- Exception handler not triggered

### Example

```python
def divide(a, b):
    if b == 0:              # ✅ Covered if tested with b=0
        raise ValueError    # ✅ Covered if exception raised
    return a / b            # ✅ Covered if tested with b≠0
```

**Full coverage requires**:
- Test with `b = 0` (tests if branch and exception)
- Test with `b ≠ 0` (tests else branch and return)

## Improving Coverage

### Finding Uncovered Code

1. **Run coverage report**:
   ```powershell
   pytest --cov=oauth --cov-report=term-missing
   ```

2. **Look for "Missing" lines**:
   ```
   oauth/token_manager.py    80%   45-50, 67
   ```

3. **Open the file** and check lines 45-50 and 67

4. **Write tests** for those code paths

### Common Uncovered Patterns

#### Error Handling

```python
# Often uncovered
try:
    result = risky_operation()
except SomeError:
    logger.error("Failed")  # ❌ Not covered
    raise
```

**Solution**: Test the error case:
```python
def test_error_handling(mocker):
    mocker.patch('module.risky_operation', side_effect=SomeError())
    with pytest.raises(SomeError):
        function_that_calls_risky()
```

#### Edge Cases

```python
def process_list(items):
    if not items:
        return []  # ❌ Often not tested
    return [process(item) for item in items]
```

**Solution**: Test with empty input:
```python
def test_empty_list():
    result = process_list([])
    assert result == []
```

#### Branch Coverage

```python
def format_response(data, verbose=False):
    result = {"data": data}
    if verbose:
        result["metadata"] = {...}  # ❌ Not covered if verbose never True
    return result
```

**Solution**: Test both branches:
```python
def test_format_response_normal():
    result = format_response("test", verbose=False)
    assert "metadata" not in result

def test_format_response_verbose():
    result = format_response("test", verbose=True)
    assert "metadata" in result
```

## Coverage Exclusions

Some code is intentionally excluded from coverage requirements.

### Excluded Patterns

In `pytest.ini`:
```ini
[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod
    pass
```

### Using `# pragma: no cover`

Mark code that shouldn't affect coverage:

```python
def debug_function():  # pragma: no cover
    """Only used for debugging, not in production"""
    print(internal_state)
    
if __name__ == "__main__":  # pragma: no cover
    # Script entry point, tested separately
    main()
```

**Use sparingly!** Don't abuse this to hide untested code.

## Coverage Best Practices

### DO ✅

1. **Focus on critical paths first**
   - OAuth flow
   - Request/response conversion
   - API endpoints

2. **Test both success and failure cases**
   ```python
   def test_success_case():
       assert function("valid") == expected
   
   def test_failure_case():
       with pytest.raises(ValueError):
           function("invalid")
   ```

3. **Test edge cases**
   - Empty inputs
   - Null values
   - Boundary conditions

4. **Use coverage to find gaps**
   - Not to chase 100%
   - To ensure critical code is tested

### DON'T ❌

1. **Don't write tests just for coverage**
   - Tests should verify behavior
   - Not just execute code

2. **Don't test third-party code**
   ```python
   # Don't test httpx internals
   def test_httpx_library():  # ❌ Bad
       client = httpx.AsyncClient()
       assert client.timeout is not None
   ```

3. **Don't chase 100% coverage**
   - Diminishing returns after 80-90%
   - Some code is OK to leave uncovered

4. **Don't mock everything**
   - Tests won't catch real issues
   - Use mocks only when necessary

## Coverage in CI/CD

### Enforcing Requirements

In `pytest.ini`:
```ini
[pytest]
addopts = 
    --cov-fail-under=80
```

This fails the build if coverage drops below 80%.

### GitHub Actions

```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=. --cov-report=term --cov-fail-under=80
    
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.json
```

### Coverage Badges

Add to README:

```markdown
[![Coverage](https://codecov.io/gh/Pimzino/ccmaxproxy/branch/main/graph/badge.svg)](https://codecov.io/gh/Pimzino/ccmaxproxy)
```

## Troubleshooting

### Coverage Not Showing

**Problem**: Tests pass but coverage is 0%

**Solutions**:
```powershell
# Make sure pytest-cov is installed
pip install pytest-cov

# Run from project root
cd d:\LLMProxy\ccmaxproxy
pytest --cov=.

# Check that .coveragerc or pytest.ini is configured correctly
```

### Incorrect Coverage

**Problem**: Coverage shows lines as covered that aren't

**Solution**: This often happens with:
- Import-time code execution
- Decorators
- Class definitions

Check the HTML report for accurate line-by-line coverage.

### Excluded Files Not Excluded

**Problem**: Test files show in coverage report

**Solution**: Check `pytest.ini` omit patterns:
```ini
[coverage:run]
omit =
    */tests/*
    *test_*.py
```

## Current Coverage Status

To check current coverage:

```powershell
# Overall coverage
make test-cov

# Per-component coverage
pytest --cov=oauth --cov-report=term
pytest --cov=openai_compat --cov-report=term
pytest --cov=models --cov-report=term
```

## Coverage Goals

### Short Term (MVP)

- ✅ 80% coverage for oauth/
- ✅ 80% coverage for openai_compat/
- ✅ 80% coverage for models/
- ✅ 80% coverage for proxy/endpoints/

### Medium Term

- 🎯 85% overall project coverage
- 🎯 90% coverage for critical paths
- 🎯 Branch coverage tracking

### Long Term

- 🎯 95% coverage for core components
- 🎯 Mutation testing for critical code
- 🎯 Property-based testing for converters

## Resources

- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Codecov Documentation](https://docs.codecov.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

## Next Steps

- **Writing Tests**: See [WRITING_TESTS.md](./WRITING_TESTS.md)
- **Test Architecture**: See [TEST_ARCHITECTURE.md](./TEST_ARCHITECTURE.md)
- **Running Tests**: See [TESTING.md](./TESTING.md)
