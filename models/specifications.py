"""Model specifications and registry entry definitions"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List

from .reasoning import REASONING_BUDGET_MAP


@dataclass(frozen=True)
class BaseModelSpec:
    openai_id: str
    anthropic_id: str
    created: int
    owned_by: str
    context_length: int
    max_completion_tokens: int
    supports_reasoning: bool = True
    supports_vision: bool = True
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
    supports_vision: bool = True
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
        if self.supports_vision:
            data["supports_vision"] = True
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
