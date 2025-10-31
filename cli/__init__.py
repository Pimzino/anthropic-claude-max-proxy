"""CLI package for Anthropic Claude Max Proxy

This package provides a modular command-line interface for managing
the Anthropic Claude Max Proxy server.
"""

from cli.cli_app import AnthropicProxyCLI
from cli.main import main

__all__ = [
    "AnthropicProxyCLI",
    "main",
]
