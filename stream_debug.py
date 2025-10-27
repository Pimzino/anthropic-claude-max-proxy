"""
Utilities to capture raw streaming chunks for troubleshooting.

The tracer writes Anthropic SSE frames and converted OpenAI chunks to disk
when stream tracing is enabled via configuration.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional


class StreamTracer:
    """Captures streaming data into a request-scoped log file."""

    def __init__(self, request_id: str, route: str, base_dir: str, max_bytes: Optional[int]):
        safe_route = route.replace(" ", "-")
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        self.request_id = request_id
        self.route = safe_route
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.path = self.base_dir / f"{timestamp}_{safe_route}_{request_id}.log"
        self._file = self.path.open("w", encoding="utf-8")

        self._max_bytes = max_bytes if isinstance(max_bytes, int) and max_bytes > 0 else None
        self._written = 0
        self._truncated = False

        self.log_note("stream tracer initialized")

    def log_source_chunk(self, chunk: str) -> None:
        """Record a raw Anthropic SSE chunk."""
        self._write("ANTHROPIC", chunk)

    def log_converted_chunk(self, chunk: str) -> None:
        """Record the chunk returned to the OpenAI client."""
        self._write("OPENAI", chunk)

    def log_note(self, note: str) -> None:
        self._write("NOTE", note)

    def log_error(self, message: str) -> None:
        self._write("ERROR", message)

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            self.log_note("stream tracer closed")
        finally:
            self._file.close()

    def _write(self, label: str, payload: str) -> None:
        if self._file.closed:
            return

        if not isinstance(payload, str):
            payload = repr(payload)

        timestamp = datetime.datetime.utcnow().isoformat(timespec="milliseconds")
        entry = f"[{timestamp}] [{label}] len={len(payload)}\n{payload}\n"
        encoded = entry.encode("utf-8", "replace")

        if self._max_bytes is not None:
            remaining = self._max_bytes - self._written

            if remaining <= 0:
                if not self._truncated:
                    self._file.write("[stream trace truncated]\n")
                    self._file.flush()
                    self._truncated = True
                return

            if len(encoded) > remaining:
                partial = encoded[:remaining]
                self._file.write(partial.decode("utf-8", "ignore"))
                self._file.write("\n[stream trace truncated]\n")
                self._file.flush()
                self._written = self._max_bytes
                self._truncated = True
                return

        self._file.write(entry)
        self._file.flush()

        if self._max_bytes is not None:
            self._written += len(encoded)


def maybe_create_stream_tracer(
    enabled: bool,
    request_id: str,
    route: str,
    base_dir: str,
    max_bytes: Optional[int],
) -> Optional[StreamTracer]:
    """Factory helper that respects the global enable flag."""
    if not enabled:
        return None
    return StreamTracer(request_id=request_id, route=route, base_dir=base_dir, max_bytes=max_bytes)
