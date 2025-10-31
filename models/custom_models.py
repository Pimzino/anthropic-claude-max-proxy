"""Custom model configuration and management"""

from typing import Dict, Optional, Any
import logging

from config.loader import load_custom_models
from .registry import _register_model, OPENAI_MODELS_LIST
from .specifications import ModelRegistryEntry

logger = logging.getLogger(__name__)

# Custom models configuration
CUSTOM_MODELS_CONFIG: Dict[str, Dict[str, Any]] = {}


def _load_custom_models() -> None:
    """Load custom models from models.json and add them to the registry"""
    custom_models = load_custom_models()

    for model_config in custom_models:
        model_id = model_config["id"]

        # Store the full config for later use (API key, base_url, etc.)
        # Use lowercase key for case-insensitive lookup
        CUSTOM_MODELS_CONFIG[model_id.lower()] = model_config

        # Create registry entry for the custom model
        entry = ModelRegistryEntry(
            openai_id=model_id,
            anthropic_id="",  # Not an Anthropic model
            created=0,  # Custom models don't have a creation timestamp
            owned_by=model_config.get("owned_by", "custom"),
            context_length=model_config.get("context_length", 200000),
            max_completion_tokens=model_config.get("max_completion_tokens", 4096),
            reasoning_level=None,
            reasoning_budget=None,
            use_1m_context=False,
            include_in_listing=True,
        )

        _register_model(entry)
        logger.debug(f"Registered custom model: {model_id}")


def is_custom_model(model_id: str) -> bool:
    """Check if a model ID is a custom model (not Anthropic)

    Args:
        model_id: The model identifier

    Returns:
        True if the model is a custom model, False otherwise
    """
    return model_id.lower() in CUSTOM_MODELS_CONFIG


def get_custom_model_config(model_id: str) -> Optional[Dict[str, Any]]:
    """Get the configuration for a custom model

    Args:
        model_id: The model identifier

    Returns:
        The model configuration dict, or None if not a custom model
    """
    return CUSTOM_MODELS_CONFIG.get(model_id.lower())


# Load custom models on module import
_load_custom_models()

# Re-sort models list after adding custom models
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]
