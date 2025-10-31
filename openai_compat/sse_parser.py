"""
Server-Sent Events (SSE) parser for streaming responses.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SSEEvent:
    """Represents a parsed Server-Sent Events frame."""
    event: Optional[str]
    data: str


class SSEParser:
    """Incremental parser for text/event-stream payloads."""

    def __init__(self) -> None:
        self._buffer = ""
        self._current_event: Optional[str] = None
        self._current_data: List[str] = []

    def feed(self, chunk: str) -> List[SSEEvent]:
        """Consume raw chunk text and yield completed events."""
        events: List[SSEEvent] = []
        if not chunk:
            return events

        self._buffer += chunk

        while True:
            newline_idx = self._buffer.find("\n")
            if newline_idx == -1:
                break

            line = self._buffer[:newline_idx]
            self._buffer = self._buffer[newline_idx + 1:]

            # Trim CR from Windows-style endings
            if line.endswith("\r"):
                line = line[:-1]

            if line == "":
                # Blank line terminates the current event
                if self._current_event is not None or self._current_data:
                    data = "\n".join(self._current_data)
                    events.append(SSEEvent(event=self._current_event, data=data))
                self._current_event = None
                self._current_data = []
                continue

            if line.startswith(":"):
                # Comment line - ignore
                continue

            if line.startswith("event:"):
                self._current_event = line[6:].lstrip()
                continue

            if line.startswith("data:"):
                data_value = line[5:]
                if data_value.startswith(" "):
                    data_value = data_value[1:]
                self._current_data.append(data_value)
                continue

            # Fallback: treat as data line (defensive)
            self._current_data.append(line)

        return events

    def flush(self) -> List[SSEEvent]:
        """Flush any remaining buffered event (used at stream end)."""
        events: List[SSEEvent] = []
        if self._current_event is not None or self._current_data:
            data = "\n".join(self._current_data)
            events.append(SSEEvent(event=self._current_event, data=data))
        if self._buffer:
            events.append(SSEEvent(event=None, data=self._buffer))
        self._current_event = None
        self._current_data = []
        self._buffer = ""
        return events
