"""
LLMux - Modular proxy server package.

This package provides a proxy server for the Anthropic API with OpenAI compatibility,
custom provider support, and advanced features like prompt caching and thinking modes.
"""
from .server import ProxyServer
from .app import app

__version__ = "1.0.0"

__all__ = [
    'ProxyServer',
    'app',
]
