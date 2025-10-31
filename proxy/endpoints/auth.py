"""
Authentication status endpoint.
"""
from fastapi import APIRouter
from utils.storage import TokenStorage

router = APIRouter()
token_storage = TokenStorage()


@router.get("/auth/status")
async def auth_status():
    """Get token status without exposing secrets"""
    return token_storage.get_status()

