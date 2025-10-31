"""Model name resolution and legacy parsing"""

from typing import Optional, Tuple
import logging

from .registry import MODEL_REGISTRY
from .reasoning import REASONING_BUDGET_MAP

logger = logging.getLogger(__name__)


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
