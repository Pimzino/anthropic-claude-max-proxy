"""
Ephemeral cache for Anthropic signed thinking blocks.

We key cached thinking by tool_use id(s) from the assistant message that
produced them. This lets us reattach a previously signed thinking block to
the next request when the client doesn't include it.

Entries are short‑lived and capped to avoid unbounded growth.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple


class _ThinkingCache:
    def __init__(self, max_entries: int = 256, ttl_seconds: int = 600) -> None:
        self._data: Dict[str, Tuple[dict, float]] = {}
        self._max = max_entries
        self._ttl = ttl_seconds

    def put(self, tool_use_id: str, thinking_block: dict) -> None:
        """Store a signed thinking block for a given tool_use id."""
        if not tool_use_id:
            return
        # Require the fields Anthropic expects on input
        if not isinstance(thinking_block, dict):
            return
        if "thinking" not in thinking_block or "signature" not in thinking_block:
            return

        now = time.time()
        self._data[tool_use_id] = (thinking_block, now)
        self._evict_if_needed()
        self._cleanup()

    def get(self, tool_use_id: str) -> Optional[dict]:
        """Retrieve a valid, non‑expired thinking block for the tool_use id."""
        entry = self._data.get(tool_use_id)
        if not entry:
            return None
        thinking_block, ts = entry
        if time.time() - ts > self._ttl:
            self._data.pop(tool_use_id, None)
            return None
        return thinking_block

    def _evict_if_needed(self) -> None:
        if len(self._data) <= self._max:
            return
        # Evict oldest entries
        items = sorted(self._data.items(), key=lambda kv: kv[1][1])
        for key, _ in items[: len(self._data) - self._max]:
            self._data.pop(key, None)

    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, (_, ts) in self._data.items() if now - ts > self._ttl]
        for k in expired:
            self._data.pop(k, None)


THINKING_CACHE = _ThinkingCache()

