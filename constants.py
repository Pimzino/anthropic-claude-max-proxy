"""
Centralized model and reasoning metadata for the proxy.

This module defines the OpenAI-compatible model ids that the proxy exposes
and how they map to Anthropic's underlying model identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

# Reasoning effort to thinking budget mapping (tokens)
REASONING_BUDGET_MAP: Dict[str, int] = {
    "low": 8000,
    "medium": 16000,
    "high": 32000,
}


@dataclass(frozen=True)
class BaseModelSpec:
    openai_id: str
    anthropic_id: str
    created: int
    owned_by: str
    context_length: int
    max_completion_tokens: int
    supports_reasoning: bool = True
    use_1m_context: bool = False


@dataclass(frozen=True)
class ModelRegistryEntry:
    openai_id: str
    anthropic_id: str
    created: int
    owned_by: str
    context_length: int
    max_completion_tokens: int
    reasoning_level: Optional[str] = None
    reasoning_budget: Optional[int] = None
    use_1m_context: bool = False
    include_in_listing: bool = True

    def to_model_listing(self) -> Dict[str, int | str | bool]:
        data: Dict[str, int | str | bool] = {
            "id": self.openai_id,
            "object": "model",
            "created": self.created,
            "owned_by": self.owned_by,
            "context_length": self.context_length,
            "max_completion_tokens": self.max_completion_tokens,
        }
        if self.reasoning_level:
            data["reasoning_capable"] = True
            data["reasoning_budget"] = self.reasoning_budget or REASONING_BUDGET_MAP.get(self.reasoning_level)
        return data


BASE_MODELS: List[BaseModelSpec] = [
    BaseModelSpec(
        openai_id="sonnet-4-5",
        anthropic_id="claude-sonnet-4-5-20250929",
        created=1727654400,
        owned_by="anthropic",
        context_length=200_000,
        max_completion_tokens=65_536,
    ),
    BaseModelSpec(
        openai_id="haiku-4-5",
        anthropic_id="claude-haiku-4-5-20251001",
        created=1727827200,
        owned_by="anthropic",
        context_length=200_000,
        max_completion_tokens=65_536,
    ),
    BaseModelSpec(
        openai_id="opus-4-1",
        anthropic_id="claude-opus-4-1-20250805",
        created=1722816000,
        owned_by="anthropic",
        context_length=200_000,
        max_completion_tokens=32_768,
    ),
    BaseModelSpec(
        openai_id="sonnet-4",
        anthropic_id="claude-sonnet-4-20250514",
        created=1_715_644_800,
        owned_by="anthropic",
        context_length=200_000,
        max_completion_tokens=65_536,
    ),
]

MODEL_REGISTRY: Dict[str, ModelRegistryEntry] = {}
OPENAI_MODELS_LIST: List[Dict[str, int | str | bool]] = []


def _register_model(entry: ModelRegistryEntry) -> None:
    # Avoid accidental overwrites with differing definitions
    existing = MODEL_REGISTRY.get(entry.openai_id)
    if existing and existing != entry:
        logger.debug("Overwriting model registry entry for %s", entry.openai_id)
    MODEL_REGISTRY[entry.openai_id] = entry
    if entry.include_in_listing:
        OPENAI_MODELS_LIST.append(entry.to_model_listing())


def _build_registry() -> None:
    for base in BASE_MODELS:
        # Base entry (no reasoning)
        base_entry = ModelRegistryEntry(
            openai_id=base.openai_id,
            anthropic_id=base.anthropic_id,
            created=base.created,
            owned_by=base.owned_by,
            context_length=base.context_length,
            max_completion_tokens=base.max_completion_tokens,
            use_1m_context=base.use_1m_context,
        )
        _register_model(base_entry)

        # Reasoning variants for OpenAI-friendly ids
        if base.supports_reasoning:
            for level, budget in REASONING_BUDGET_MAP.items():
                reasoning_entry = ModelRegistryEntry(
                    openai_id=f"{base.openai_id}-reasoning-{level}",
                    anthropic_id=base.anthropic_id,
                    created=base.created,
                    owned_by=base.owned_by,
                    context_length=base.context_length,
                    max_completion_tokens=base.max_completion_tokens,
                    reasoning_level=level,
                    reasoning_budget=budget,
                    use_1m_context=base.use_1m_context,
                )
                _register_model(reasoning_entry)

        # Alias for Anthropic native id (no listing)
        _register_model(
            ModelRegistryEntry(
                openai_id=base.anthropic_id,
                anthropic_id=base.anthropic_id,
                created=base.created,
                owned_by=base.owned_by,
                context_length=base.context_length,
                max_completion_tokens=base.max_completion_tokens,
                include_in_listing=False,
                use_1m_context=base.use_1m_context,
            )
        )

        # Alias for Anthropic-style reasoning ids (no listing)
        if base.supports_reasoning:
            for level, budget in REASONING_BUDGET_MAP.items():
                _register_model(
                    ModelRegistryEntry(
                        openai_id=f"{base.anthropic_id}-reasoning-{level}",
                        anthropic_id=base.anthropic_id,
                        created=base.created,
                        owned_by=base.owned_by,
                        context_length=base.context_length,
                        max_completion_tokens=base.max_completion_tokens,
                        reasoning_level=level,
                        reasoning_budget=budget,
                        include_in_listing=False,
                        use_1m_context=base.use_1m_context,
                    )
                )


_build_registry()

# Ensure models list is stable (sorted for deterministic output)
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]


# Load and register custom models from models.json
CUSTOM_MODELS_CONFIG: Dict[str, Dict[str, any]] = {}

def _load_custom_models() -> None:
    """Load custom models from models.json and add them to the registry"""
    from config_loader import load_custom_models

    custom_models = load_custom_models()

    for model_config in custom_models:
        model_id = model_config["id"]

        # Store the full config for later use (API key, base_url, etc.)
        CUSTOM_MODELS_CONFIG[model_id] = model_config

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

# Load custom models on module import
_load_custom_models()

# Re-sort models list after adding custom models
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]


def is_custom_model(model_id: str) -> bool:
    """Check if a model ID is a custom model (not Anthropic)

    Args:
        model_id: The model identifier

    Returns:
        True if the model is a custom model, False otherwise
    """
    return model_id in CUSTOM_MODELS_CONFIG


def get_custom_model_config(model_id: str) -> Optional[Dict[str, any]]:
    """Get the configuration for a custom model

    Args:
        model_id: The model identifier

    Returns:
        The model configuration dict, or None if not a custom model
    """
    return CUSTOM_MODELS_CONFIG.get(model_id)


def _parse_legacy_model_name(model_name: str) -> Tuple[str, Optional[str], bool]:
    """
    Parse legacy Anthropic model names with -1m / -reasoning suffixes.
    """
    use_1m_context = False
    reasoning_level: Optional[str] = None
    base_model = model_name

    if "-1m" in base_model:
        use_1m_context = True
        base_model = base_model.replace("-1m", "")

    if "-reasoning-" in base_model:
        parts = base_model.rsplit("-reasoning-", 1)
        base_model = parts[0]
        maybe_level = parts[1] if len(parts) > 1 else None
        if maybe_level in REASONING_BUDGET_MAP:
            reasoning_level = maybe_level
        else:
            logger.warning(
                "Invalid reasoning level in legacy model name '%s'. Valid levels: %s",
                model_name,
                list(REASONING_BUDGET_MAP.keys()),
            )

    return base_model, reasoning_level, use_1m_context


def resolve_model_metadata(model_name: str) -> Tuple[str, Optional[str], bool]:
    """
    Resolve an incoming model name to (anthropic_id, reasoning_level, use_1m_context).
    Supports both the new OpenAI-compatible ids and legacy Anthropic ids.
    """
    entry = MODEL_REGISTRY.get(model_name)
    if entry:
        return entry.anthropic_id, entry.reasoning_level, entry.use_1m_context

    base_model, reasoning_level, use_1m_context = _parse_legacy_model_name(model_name)
    return base_model, reasoning_level, use_1m_context


__all__ = [
    "REASONING_BUDGET_MAP",
    "BASE_MODELS",
    "MODEL_REGISTRY",
    "OPENAI_MODELS_LIST",
    "resolve_model_metadata",
    "CLAUDE_CODE_SPOOF_MESSAGE",
    "USER_AGENT",
    "X_APP_HEADER",
    "STAINLESS_HEADERS",
    "CUSTOM_MODELS_CONFIG",
    "is_custom_model",
    "get_custom_model_config",
]

# HTTP Request Headers and Spoofing Constants
# These values are used to spoof requests as coming from the official Claude CLI
CLAUDE_CODE_SPOOF_MESSAGE = "You are Claude Code, Anthropic's official CLI for Claude."

# User-Agent string for API requests
USER_AGENT = "claude-cli/1.0.113 (external, cli)"

# x-app header value
X_APP_HEADER = "cli"

# Stainless SDK headers (mimics official Claude CLI behavior)
STAINLESS_HEADERS = {
    "X-Stainless-Retry-Count": "0",
    "X-Stainless-Timeout": "600",
    "X-Stainless-Lang": "js",
    "X-Stainless-Package-Version": "0.60.0",
    "X-Stainless-OS": "Windows",
    "X-Stainless-Arch": "x64",
    "X-Stainless-Runtime": "node",
    "X-Stainless-Runtime-Version": "v22.19.0",
    "x-stainless-helper-method": "stream",
}
