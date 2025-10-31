"""Model registry for managing available models"""

from typing import Dict, List
import logging

from .specifications import ModelRegistryEntry, BASE_MODELS
from .reasoning import REASONING_BUDGET_MAP

logger = logging.getLogger(__name__)

MODEL_REGISTRY: Dict[str, ModelRegistryEntry] = {}
OPENAI_MODELS_LIST: List[Dict[str, int | str | bool]] = []


def _register_model(entry: ModelRegistryEntry) -> None:
    """Register a model in the registry"""
    # Avoid accidental overwrites with differing definitions
    existing = MODEL_REGISTRY.get(entry.openai_id)
    if existing and existing != entry:
        logger.debug("Overwriting model registry entry for %s", entry.openai_id)
    MODEL_REGISTRY[entry.openai_id] = entry
    if entry.include_in_listing:
        OPENAI_MODELS_LIST.append(entry.to_model_listing())


def _build_registry() -> None:
    """Build the model registry from base models"""
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


# Build the registry on module import
_build_registry()

# Ensure models list is stable (sorted for deterministic output)
OPENAI_MODELS_LIST.sort(key=lambda model: model["id"])  # type: ignore[index]
