"""
Health check and status endpoints.
"""
import time
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}


@router.get("/healthz")
async def healthz_check():
    """Alternative health check endpoint (Kubernetes style)"""
    return {"status": "ok", "timestamp": time.time()}

