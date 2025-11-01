"""Custom model configuration and management"""

from typing import Dict, Optional, Any, List
import logging

from config.loader import load_custom_models
from .registry import _register_model, OPENAI_MODELS_LIST
from .specifications import ModelRegistryEntry
import settings

logger = logging.getLogger(__name__)

# Custom models configuration
CUSTOM_MODELS_CONFIG: Dict[str, Dict[str, Any]] = {}

# ChatGPT models configuration
CHATGPT_MODELS_CONFIG: Dict[str, Dict[str, Any]] = {}


def _load_chatgpt_models() -> None:
    """Auto-register ChatGPT models with optional overrides from models.json"""
    # Base ChatGPT models with accurate specifications from OpenAI documentation
    # Source: https://platform.openai.com/docs/models/gpt-5
    base_models = [
        {
            "id": "gpt-5",
            "owned_by": "openai-chatgpt",
            "context_length": 400000,  # 400k context window (official spec)
            "max_completion_tokens": 128000,  # 128k max output tokens (official spec)
            "supports_reasoning": True,  # Supports reasoning with effort levels
            "supports_vision": True,  # Supports text and image input
        },
        {
            "id": "gpt-5-codex",
            "owned_by": "openai-chatgpt",
            # Note: gpt-5-codex uses same base as gpt-5 with coding optimizations
            "context_length": 400000,  # Same as gpt-5
            "max_completion_tokens": 128000,  # Same as gpt-5
            "supports_reasoning": True,  # Supports reasoning for coding tasks
            "supports_vision": True,  # Supports text and image input
        },
        {
            "id": "codex-mini-latest",
            "owned_by": "openai-chatgpt",
            # Note: codex-mini is a smaller, faster variant
            # Exact specs not publicly documented, using conservative estimates
            "context_length": 128000,  # Estimated based on similar models
            "max_completion_tokens": 16000,  # Conservative estimate for mini variant
            "supports_reasoning": False,  # Mini variant typically doesn't have reasoning
            "supports_vision": False,  # Mini variant typically text-only
        },
    ]

    # Load overrides from models.json if present
    try:
        from config.loader import get_config_loader
        config = get_config_loader()
        chatgpt_overrides = config.get("chatgpt_models", [])

        # Apply overrides
        override_map = {m["id"]: m for m in chatgpt_overrides if isinstance(m, dict) and "id" in m}
        for model in base_models:
            if model["id"] in override_map:
                model.update(override_map[model["id"]])
                logger.info(f"Applied overrides for ChatGPT model: {model['id']}")
    except Exception as e:
        logger.debug(f"No ChatGPT model overrides found: {e}")

    # Register base models
    for model_config in base_models:
        model_id = model_config["id"]

        # Store config for later use
        CHATGPT_MODELS_CONFIG[model_id.lower()] = model_config

        # Create registry entry
        entry = ModelRegistryEntry(
            openai_id=model_id,
            anthropic_id="",  # Not an Anthropic model
            created=0,
            owned_by=model_config["owned_by"],
            context_length=model_config["context_length"],
            max_completion_tokens=model_config["max_completion_tokens"],
            reasoning_level=None,
            reasoning_budget=None,
            supports_vision=model_config.get("supports_vision", False),
            use_1m_context=False,
            include_in_listing=True,
        )

        _register_model(entry)
        logger.debug(f"Registered ChatGPT model: {model_id}")

    # Register reasoning effort variants if enabled
    if settings.CHATGPT_EXPOSE_REASONING_VARIANTS:
        reasoning_efforts = ["minimal", "low", "medium", "high"]
        reasoning_models = ["gpt-5", "gpt-5-codex"]

        for base_model in reasoning_models:
            base_config = CHATGPT_MODELS_CONFIG.get(base_model.lower())
            if not base_config or not base_config.get("supports_reasoning"):
                continue

            for effort in reasoning_efforts:
                variant_id = f"{base_model}-{effort}"
                variant_config = base_config.copy()
                variant_config["id"] = variant_id
                variant_config["reasoning_effort"] = effort

                CHATGPT_MODELS_CONFIG[variant_id.lower()] = variant_config

                entry = ModelRegistryEntry(
                    openai_id=variant_id,
                    anthropic_id="",
                    created=0,
                    owned_by=base_config["owned_by"],
                    context_length=base_config["context_length"],
                    max_completion_tokens=base_config["max_completion_tokens"],
                    reasoning_level=effort,
                    reasoning_budget=None,
                    supports_vision=base_config.get("supports_vision", False),
                    use_1m_context=False,
                    include_in_listing=True,
                )

                _register_model(entry)
                logger.debug(f"Registered ChatGPT reasoning variant: {variant_id}")


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
            supports_vision=model_config.get("vision", model_config.get("supports_vision", False)),
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


def is_chatgpt_model(model_id: str) -> bool:
    """Check if a model ID is a ChatGPT model

    Args:
        model_id: The model identifier

    Returns:
        True if the model is a ChatGPT model, False otherwise
    """
    # Strip reasoning effort suffix if present
    model_lower = model_id.lower()
    for effort in ["minimal", "low", "medium", "high"]:
        if model_lower.endswith(f"-{effort}"):
            model_lower = model_lower[:-len(f"-{effort}")]
            break

    return model_lower in CHATGPT_MODELS_CONFIG


def get_custom_model_config(model_id: str) -> Optional[Dict[str, Any]]:
    """Get the configuration for a custom model

    Args:
        model_id: The model identifier

    Returns:
        The model configuration dict, or None if not a custom model
    """
    return CUSTOM_MODELS_CONFIG.get(model_id.lower())


def get_chatgpt_model_config(model_id: str) -> Optional[Dict[str, Any]]:
    """Get the configuration for a ChatGPT model

    Args:
        model_id: The model identifier

    Returns:
        The model configuration dict, or None if not a ChatGPT model
    """
    return CHATGPT_MODELS_CONFIG.get(model_id.lower())


# Load ChatGPT models first
_load_chatgpt_models()

# Load custom models on module import
_load_custom_models()

# Re-sort models list after adding custom models
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]
