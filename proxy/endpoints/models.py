"""
Models listing endpoint.
"""
from fastapi import APIRouter
from models import OPENAI_MODELS_LIST

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint with reasoning variants"""
    return {
        "object": "list",
        "data": [model.copy() for model in OPENAI_MODELS_LIST]
    }

