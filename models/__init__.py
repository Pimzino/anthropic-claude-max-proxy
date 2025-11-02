"""Model registry and specifications package for ccmaxproxy"""

from .reasoning import REASONING_BUDGET_MAP
from .specifications import BaseModelSpec, ModelRegistryEntry, BASE_MODELS
from .registry import MODEL_REGISTRY, OPENAI_MODELS_LIST
from .custom_models import (
    CUSTOM_MODELS_CONFIG,
    CHATGPT_MODELS_CONFIG,
    is_custom_model,
    is_chatgpt_model,
    get_custom_model_config,
    get_chatgpt_model_config,
    get_chatgpt_default_instructions,
    get_openai_model_id,
)
from .resolution import resolve_model_metadata

__all__ = [
    "REASONING_BUDGET_MAP",
    "BaseModelSpec",
    "ModelRegistryEntry",
    "BASE_MODELS",
    "MODEL_REGISTRY",
    "OPENAI_MODELS_LIST",
    "CUSTOM_MODELS_CONFIG",
    "CHATGPT_MODELS_CONFIG",
    "is_custom_model",
    "is_chatgpt_model",
    "get_custom_model_config",
    "get_chatgpt_model_config",
    "get_chatgpt_default_instructions",
    "get_openai_model_id",
    "resolve_model_metadata",
]
