"""Session management for ChatGPT prompt caching

Generates stable session IDs based on request fingerprints to enable
efficient prompt caching across requests.
"""

import hashlib
import json
import threading
import uuid
from typing import Any, Dict, List, Optional


# Thread-safe session cache
_LOCK = threading.Lock()
_FINGERPRINT_TO_UUID: Dict[str, str] = {}
_ORDER: List[str] = []
_MAX_ENTRIES = 10000


def _canonicalize_first_user_message(
    input_items: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Extract the first stable user message from Responses input items

    Used for fingerprinting to enable prompt caching.

    Args:
        input_items: Responses API input items

    Returns:
        Canonicalized first user message, or None if not found
    """
    for item in input_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue

        role = item.get("role")
        if role != "user":
            continue

        content = item.get("content")
        if not isinstance(content, list):
            continue

        norm_content = []
        for part in content:
            if not isinstance(part, dict):
                continue

            ptype = part.get("type")
            if ptype == "input_text":
                text = part.get("text") if isinstance(part.get("text"), str) else ""
                if text:
                    norm_content.append({"type": "input_text", "text": text})

            elif ptype == "input_image":
                url = part.get("image_url") if isinstance(part.get("image_url"), str) else None
                if url:
                    norm_content.append({"type": "input_image", "image_url": url})

        if norm_content:
            return {"type": "message", "role": "user", "content": norm_content}

    return None


def canonicalize_prefix(
    instructions: Optional[str],
    input_items: List[Dict[str, Any]]
) -> str:
    """Create canonical representation of request prefix for fingerprinting

    Args:
        instructions: System instructions
        input_items: Responses API input items

    Returns:
        JSON string representing the canonical prefix
    """
    prefix: Dict[str, Any] = {}

    if isinstance(instructions, str) and instructions.strip():
        prefix["instructions"] = instructions.strip()

    first_user = _canonicalize_first_user_message(input_items)
    if first_user is not None:
        prefix["first_user_message"] = first_user

    return json.dumps(prefix, sort_keys=True, separators=(",", ":"))


def _fingerprint(s: str) -> str:
    """Generate SHA256 fingerprint of a string

    Args:
        s: String to fingerprint

    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _remember(fp: str, sid: str) -> None:
    """Remember a fingerprint → session ID mapping

    Maintains LRU cache with max size.

    Args:
        fp: Fingerprint string
        sid: Session ID
    """
    if fp in _FINGERPRINT_TO_UUID:
        return

    _FINGERPRINT_TO_UUID[fp] = sid
    _ORDER.append(fp)

    # Evict oldest entry if cache is full
    if len(_ORDER) > _MAX_ENTRIES:
        oldest = _ORDER.pop(0)
        _FINGERPRINT_TO_UUID.pop(oldest, None)


def ensure_session_id(
    instructions: Optional[str],
    input_items: List[Dict[str, Any]],
    client_supplied: Optional[str] = None,
) -> str:
    """Ensure a stable session ID for prompt caching

    If client supplies a session ID, use it. Otherwise, generate a stable
    session ID based on the request fingerprint.

    Args:
        instructions: System instructions
        input_items: Responses API input items
        client_supplied: Optional client-supplied session ID

    Returns:
        Session ID string
    """
    # Use client-supplied session ID if provided
    if isinstance(client_supplied, str) and client_supplied.strip():
        return client_supplied.strip()

    # Generate fingerprint from request prefix
    canon = canonicalize_prefix(instructions, input_items)
    fp = _fingerprint(canon)

    # Thread-safe lookup/creation
    with _LOCK:
        if fp in _FINGERPRINT_TO_UUID:
            return _FINGERPRINT_TO_UUID[fp]

        # Generate new session ID
        sid = str(uuid.uuid4())
        _remember(fp, sid)
        return sid
