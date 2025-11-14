"""Custom models configuration and registration"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import settings

from models.registry import ModelRegistryEntry, _register_model, OPENAI_MODELS_LIST
from config.loader import load_custom_models

logger = logging.getLogger(__name__)

# System prompts for ChatGPT models (from ChatMock/Codex CLI)
# These are injected as instructions to ensure proper model behavior

def _read_prompt_file(filename: str) -> Optional[str]:
    """Read a prompt file from the prompts directory

    Args:
        filename: Name of the prompt file to read

    Returns:
        The file contents as a string, or None if not found
    """
    candidates = [
        Path(__file__).parent.parent / "prompts" / filename,
        Path(__file__).parent / "prompts" / filename,
        Path.cwd() / "prompts" / filename,
    ]

    for candidate in candidates:
        try:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
        except Exception as e:
            logger.debug(f"Failed to read {candidate}: {e}")
            continue

    return None


def _load_base_instructions() -> str:
    """Load base GPT-5 instructions from markdown file

    Returns:
        The base instructions string

    Raises:
        FileNotFoundError: If the prompt file cannot be found
    """
    content = _read_prompt_file("gpt5_base.md")
    if content is None:
        raise FileNotFoundError("Failed to read prompts/gpt5_base.md; expected in prompts/ directory")
    return content


def _load_gpt5_codex_instructions(fallback: str) -> str:
    """Load GPT-5 Codex instructions from markdown file

    Args:
        fallback: Fallback instructions if file not found

    Returns:
        The Codex instructions string, or fallback if not found
    """
    content = _read_prompt_file("gpt5_codex.md")
    return content if isinstance(content, str) and content.strip() else fallback


# Load instructions from markdown files (matching ChatMock behavior)
CHATGPT_BASE_INSTRUCTIONS = _load_base_instructions()
CHATGPT_GPT5_CODEX_INSTRUCTIONS = _load_gpt5_codex_instructions(CHATGPT_BASE_INSTRUCTIONS)

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
            "id": "gpt5",
            "openai_id": "gpt-5",  # Actual OpenAI model ID (hidden)
            "owned_by": "openai-chatgpt",
            "context_length": 400000,  # 400k context window (official spec)
            "max_completion_tokens": 128000,  # 128k max output tokens (official spec)
            "supports_reasoning": True,  # Supports reasoning with effort levels
            "supports_vision": True,  # Supports text and image input
            "default_instructions": CHATGPT_BASE_INSTRUCTIONS,
        },
        {
            "id": "gpt5codex",
            "openai_id": "gpt-5-codex",  # Actual OpenAI model ID (hidden)
            "owned_by": "openai-chatgpt",
            # Note: gpt-5-codex uses same base as gpt-5 with coding optimizations
            "context_length": 400000,  # Same as gpt-5
            "max_completion_tokens": 128000,  # Same as gpt-5
            "supports_reasoning": True,  # Supports reasoning for coding tasks
            "supports_vision": True,  # Supports text and image input
            "default_instructions": CHATGPT_GPT5_CODEX_INSTRUCTIONS,
        },
        {
            "id": "gpt51",
            "openai_id": "gpt-5.1",  # Actual OpenAI model ID (hidden)
            "owned_by": "openai-chatgpt",
            "context_length": 400000,  # 400k context window (official spec)
            "max_completion_tokens": 128000,  # 128k max output tokens (official spec)
            "supports_reasoning": True,  # Supports reasoning with effort levels
            "supports_vision": True,  # Supports text and image input
            "default_instructions": CHATGPT_BASE_INSTRUCTIONS,
        },
        {
            "id": "gpt51codex",
            "openai_id": "gpt-5.1-codex",  # Actual OpenAI model ID (hidden)
            "owned_by": "openai-chatgpt",
            # Note: gpt-5.1-codex uses same base as gpt-5.1 with coding optimizations
            "context_length": 400000,  # Same as gpt-5.1
            "max_completion_tokens": 128000,  # Same as gpt-5.1
            "supports_reasoning": True,  # Supports reasoning for coding tasks
            "supports_vision": True,  # Supports text and image input
            "default_instructions": CHATGPT_GPT5_CODEX_INSTRUCTIONS,
        },
        {
            "id": "codexmini",
            "openai_id": "codex-mini-latest",  # Actual OpenAI model ID (hidden)
            "owned_by": "openai-chatgpt",
            # Note: codex-mini is a smaller, faster variant
            # Exact specs not publicly documented, using conservative estimates
            "context_length": 128000,  # Estimated based on similar models
            "max_completion_tokens": 16000,  # Conservative estimate for mini variant
            "supports_reasoning": False,  # Mini variant typically doesn't have reasoning
            "supports_vision": False,  # Mini variant typically text-only
            "default_instructions": CHATGPT_BASE_INSTRUCTIONS,
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
        openai_model_id = model_config.get("openai_id", model_id)

        # Store config for later use (using our custom ID)
        CHATGPT_MODELS_CONFIG[model_id.lower()] = model_config
        # Also store using the actual OpenAI ID for lookup
        CHATGPT_MODELS_CONFIG[openai_model_id.lower()] = model_config

        # Create registry entry (advertised with our custom ID)
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

        # Add OpenAI native ID as hidden alias (not listed)
        if openai_model_id != model_id:
            alias_entry = ModelRegistryEntry(
                openai_id=openai_model_id,
                anthropic_id="",
                created=0,
                owned_by=model_config["owned_by"],
                context_length=model_config["context_length"],
                max_completion_tokens=model_config["max_completion_tokens"],
                reasoning_level=None,
                reasoning_budget=None,
                supports_vision=model_config.get("supports_vision", False),
                use_1m_context=False,
                include_in_listing=False,  # Hidden alias
            )
            _register_model(alias_entry)
            logger.debug(f"Registered ChatGPT alias: {openai_model_id}")

    # Register reasoning effort variants if enabled
    if settings.CHATGPT_EXPOSE_REASONING_VARIANTS:
        reasoning_efforts = ["minimal", "low", "medium", "high"]
        reasoning_models = ["gpt5", "gpt5codex", "gpt51", "gpt51codex"]

        for base_model in reasoning_models:
            # Look up config using our custom ID
            base_config = CHATGPT_MODELS_CONFIG.get(base_model.lower())
            if not base_config or not base_config.get("supports_reasoning"):
                continue

            # Get the actual OpenAI model ID for this base model
            openai_base_id = base_config.get("openai_id", base_model)

            for effort in reasoning_efforts:
                # Our custom variant ID (e.g., gpt5-reasoning-low)
                variant_id = f"{base_model}-reasoning-{effort}"
                # OpenAI native variant ID (e.g., gpt-5-low) - hidden alias
                openai_variant_id = f"{openai_base_id}-{effort}"

                variant_config = base_config.copy()
                variant_config["id"] = variant_id
                variant_config["reasoning_effort"] = effort

                # Store with our custom ID
                CHATGPT_MODELS_CONFIG[variant_id.lower()] = variant_config
                # Also store using OpenAI native ID for lookup
                CHATGPT_MODELS_CONFIG[openai_variant_id.lower()] = variant_config

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

                # Add OpenAI native ID as hidden alias for reasoning variant
                alias_variant_entry = ModelRegistryEntry(
                    openai_id=openai_variant_id,
                    anthropic_id="",
                    created=0,
                    owned_by=base_config["owned_by"],
                    context_length=base_config["context_length"],
                    max_completion_tokens=base_config["max_completion_tokens"],
                    reasoning_level=effort,
                    reasoning_budget=None,
                    supports_vision=base_config.get("supports_vision", False),
                    use_1m_context=False,
                    include_in_listing=False,  # Hidden alias
                )
                _register_model(alias_variant_entry)
                logger.debug(f"Registered ChatGPT reasoning alias: {openai_variant_id}")


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

    Supports both advertised IDs (gpt5, gpt5-reasoning-low) and
    OpenAI native IDs (gpt-5, gpt-5-low)

    Args:
        model_id: The model identifier

    Returns:
        True if the model is a ChatGPT model, False otherwise
    """
    return model_id.lower() in CHATGPT_MODELS_CONFIG


def get_openai_model_id(model_id: str) -> str:
    """Get the actual OpenAI model ID from our custom model ID

    Maps our custom IDs (gpt5, gpt5-reasoning-low) to OpenAI native IDs (gpt-5, gpt-5-low)

    Args:
        model_id: Our custom model identifier

    Returns:
        The OpenAI native model ID to use in API calls
    """
    model_lower = model_id.lower()

    # Look up the config
    config = CHATGPT_MODELS_CONFIG.get(model_lower)
    if not config:
        # Not a ChatGPT model, return as-is
        return model_id

    # Get the base OpenAI ID
    openai_base_id = config.get("openai_id")
    if not openai_base_id:
        # No mapping, return as-is
        return model_id

    # Check if this is a reasoning variant
    reasoning_effort = config.get("reasoning_effort")
    if reasoning_effort:
        # Return OpenAI format: gpt-5-low, gpt-5-codex-medium, etc.
        return f"{openai_base_id}-{reasoning_effort}"

    # Return the base OpenAI ID
    return openai_base_id


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


def get_chatgpt_default_instructions(model_id: str) -> Optional[str]:
    """Get the default system instructions for a ChatGPT model

    Args:
        model_id: The model identifier (e.g., "gpt5", "gpt5codex", "gpt5-reasoning-low", "gpt-5")

    Returns:
        The default instructions string, or None if not a ChatGPT model
    """
    # Look up the config directly
    config = CHATGPT_MODELS_CONFIG.get(model_id.lower())
    if config:
        return config.get("default_instructions")

    return None


# Load ChatGPT models first
_load_chatgpt_models()

# Load custom models on module import
_load_custom_models()

# Re-sort models list after adding custom models
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]
