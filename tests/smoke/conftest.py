"""Smoke test fixtures and configuration

These tests require a valid ANTHROPIC_OAUTH_TOKEN environment variable
and will make actual API calls to Anthropic. Use with caution.
"""
import os
import pytest

# Import from the installed anthropic package, not the local module
try:
    from anthropic import Anthropic as AnthropicClient
except ImportError:
    # If anthropic package is not installed, skip smoke tests
    AnthropicClient = None


def pytest_configure(config):
    """Configure smoke tests"""
    config.addinivalue_line(
        "markers", "smoke: Smoke tests that require real API tokens"
    )


@pytest.fixture(scope="session")
def real_oauth_token():
    """Get real OAuth token from environment

    Skips tests if token is not available.
    """
    token = os.getenv("ANTHROPIC_OAUTH_TOKEN")
    if not token:
        pytest.skip("ANTHROPIC_OAUTH_TOKEN not set - skipping smoke tests")
    return token


@pytest.fixture(scope="session")
def smoke_test_enabled():
    """Check if smoke tests should run

    Set ENABLE_SMOKE_TESTS=1 to enable
    """
    enabled = os.getenv("ENABLE_SMOKE_TESTS", "0") == "1"
    if not enabled:
        pytest.skip("Smoke tests disabled - set ENABLE_SMOKE_TESTS=1 to enable")
    return True


@pytest.fixture(scope="session")
def real_anthropic_client(real_oauth_token, smoke_test_enabled):
    """Create a real Anthropic client using OAuth token from environment

    This fixture creates an actual Anthropic client that will make real API calls.
    Use with caution and only in smoke tests.
    """
    if AnthropicClient is None:
        pytest.skip("anthropic package not installed - skipping smoke tests")

    client = AnthropicClient(api_key=real_oauth_token)
    return client
