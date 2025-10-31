"""
Endpoint handlers for the proxy server.
"""
from .health import router as health_router
from .models import router as models_router
from .auth import router as auth_router
from .anthropic_messages import router as anthropic_messages_router
from .openai_chat import router as openai_chat_router

__all__ = [
    'health_router',
    'models_router',
    'auth_router',
    'anthropic_messages_router',
    'openai_chat_router',
]

