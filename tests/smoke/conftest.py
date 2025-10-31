"""Smoke test fixtures and configuration

These tests require a valid ANTHROPIC_OAUTH_TOKEN environment variable
and will make actual API calls to Anthropic. Use with caution.
"""
import os
import pytest


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
