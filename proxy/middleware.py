"""
FastAPI middleware for request logging and timing.
"""
import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


async def log_requests_middleware(request: Request, call_next):
    """Middleware for request logging and timing"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Only log API endpoints, not static files
    if request.url.path.startswith("/v1/"):
        logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

    return response


