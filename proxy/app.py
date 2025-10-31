"""
FastAPI application initialization and configuration.
"""
import logging
from fastapi import FastAPI

from .middleware import log_requests_middleware
from .endpoints import (
    health_router,
    models_router,
    auth_router,
    anthropic_messages_router,
    openai_chat_router,
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Anthropic Claude Max Proxy", version="1.0.0")

# Add middleware
app.middleware("http")(log_requests_middleware)

# Register routers
app.include_router(health_router)
app.include_router(models_router)
app.include_router(auth_router)
app.include_router(anthropic_messages_router)
app.include_router(openai_chat_router)

logger.debug("FastAPI application initialized with all routers and middleware")
