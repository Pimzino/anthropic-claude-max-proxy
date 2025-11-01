"""Utility functions for ChatGPT OAuth and API interactions"""

import base64
import json
from typing import Any, Dict, List, Optional, Tuple


def parse_jwt_claims(token: str) -> Optional[Dict[str, Any]]:
    """Parse JWT token and extract claims from payload

    Args:
        token: JWT token string

    Returns:
        Dictionary of claims, or None if parsing fails
    """
    if not token or token.count(".") != 2:
        return None

    try:
        _, payload, _ = token.split(".")
        # Add padding if needed
        padded = payload + "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(padded.encode())
        return json.loads(data.decode())
    except Exception:
        return None


def get_effective_chatgpt_auth(
    access_token: Optional[str],
    id_token: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Get effective ChatGPT authentication credentials

    Args:
        access_token: OAuth access token
        id_token: OAuth ID token

    Returns:
        Tuple of (access_token, account_id)
    """
    if not access_token or not id_token:
        return None, None

    # Extract account ID from ID token claims
    id_claims = parse_jwt_claims(id_token) or {}
    auth_claims = id_claims.get("https://api.openai.com/auth", {})
    account_id = auth_claims.get("chatgpt_account_id")

    return access_token, account_id


def convert_chat_messages_to_responses_input(
    messages: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Convert OpenAI chat messages to ChatGPT Responses API input format

    Args:
        messages: List of OpenAI format messages

    Returns:
        List of Responses API input items
    """
    def _normalize_image_data_url(url: str) -> str:
        """Normalize base64 image data URLs"""
        try:
            if not isinstance(url, str) or not url.startswith("data:image/"):
                return url
            if ";base64," not in url:
                return url

            header, data = url.split(",", 1)

            # URL decode if needed
            try:
                from urllib.parse import unquote
                data = unquote(data)
            except Exception:
                pass

            # Clean up base64 data
            data = data.strip().replace("\n", "").replace("\r", "")
            data = data.replace("-", "+").replace("_", "/")

            # Add padding
            pad = (-len(data)) % 4
            if pad:
                data = data + ("=" * pad)

            # Validate base64
            try:
                base64.b64decode(data, validate=True)
            except Exception:
                return url

            return f"{header},{data}"
        except Exception:
            return url

    input_items: List[Dict[str, Any]] = []

    for message in messages:
        role = message.get("role")

        # Skip system messages (handled separately as instructions)
        if role == "system":
            continue

        # Handle tool result messages
        if role == "tool":
            call_id = message.get("tool_call_id") or message.get("id")
            if isinstance(call_id, str) and call_id:
                content = message.get("content", "")
                if isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict):
                            t = part.get("text") or part.get("content")
                            if isinstance(t, str) and t:
                                texts.append(t)
                    content = "\n".join(texts)
                if isinstance(content, str):
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": content,
                    })
            continue

        # Handle assistant tool calls
        if role == "assistant" and isinstance(message.get("tool_calls"), list):
            for tc in message.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                tc_type = tc.get("type", "function")
                if tc_type != "function":
                    continue

                call_id = tc.get("id") or tc.get("call_id")
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                name = fn.get("name") if isinstance(fn, dict) else None
                args = fn.get("arguments") if isinstance(fn, dict) else None

                if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                    input_items.append({
                        "type": "function_call",
                        "name": name,
                        "arguments": args,
                        "call_id": call_id,
                    })

        # Handle message content
        content = message.get("content", "")
        content_items: List[Dict[str, Any]] = []

        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue

                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text") or part.get("content") or ""
                    if isinstance(text, str) and text:
                        kind = "output_text" if role == "assistant" else "input_text"
                        content_items.append({"type": kind, "text": text})

                elif ptype == "image_url":
                    image = part.get("image_url")
                    url = image.get("url") if isinstance(image, dict) else image
                    if isinstance(url, str) and url:
                        content_items.append({
                            "type": "input_image",
                            "image_url": _normalize_image_data_url(url)
                        })

        elif isinstance(content, str) and content:
            kind = "output_text" if role == "assistant" else "input_text"
            content_items.append({"type": kind, "text": content})

        if not content_items:
            continue

        role_out = "assistant" if role == "assistant" else "user"
        input_items.append({
            "type": "message",
            "role": role_out,
            "content": content_items
        })

    return input_items


def convert_tools_chat_to_responses(
    tools: Any
) -> List[Dict[str, Any]]:
    """Convert OpenAI tool definitions to Responses API format

    Args:
        tools: OpenAI format tool definitions

    Returns:
        List of Responses API tool definitions
    """
    out: List[Dict[str, Any]] = []

    if not isinstance(tools, list):
        return out

    for t in tools:
        if not isinstance(t, dict):
            continue
        if t.get("type") != "function":
            continue

        fn = t.get("function") if isinstance(t.get("function"), dict) else {}
        name = fn.get("name") if isinstance(fn, dict) else None

        if not isinstance(name, str) or not name:
            continue

        desc = fn.get("description") if isinstance(fn, dict) else None
        params = fn.get("parameters") if isinstance(fn, dict) else None

        if not isinstance(params, dict):
            params = {"type": "object", "properties": {}}

        out.append({
            "type": "function",
            "name": name,
            "description": desc or "",
            "strict": False,
            "parameters": params,
        })

    return out
