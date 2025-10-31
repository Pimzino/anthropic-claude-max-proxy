"""System message injection for Claude Code authentication bypass"""

import logging
from typing import Dict, Any

from headers import CLAUDE_CODE_SPOOF_MESSAGE

logger = logging.getLogger(__name__)


def inject_claude_code_system_message(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Inject Claude Code system message to bypass authentication detection

    Args:
        request_data: Request data dictionary

    Returns:
        Modified request data with injected system message
    """
    modified_request = request_data.copy()

    claude_code_spoof = CLAUDE_CODE_SPOOF_MESSAGE
    spoof_block = {"type": "text", "text": claude_code_spoof}

    existing_system = modified_request.get("system")

    if isinstance(existing_system, list):
        if existing_system and isinstance(existing_system[0], dict) and existing_system[0].get("text") == claude_code_spoof:
            return modified_request
        modified_request["system"] = [spoof_block] + existing_system
    elif isinstance(existing_system, str):
        if existing_system.startswith(claude_code_spoof):
            return modified_request
        modified_request["system"] = [spoof_block, {"type": "text", "text": existing_system}]
    elif existing_system is None:
        modified_request["system"] = [spoof_block]
    elif isinstance(existing_system, dict) and existing_system.get("text") == claude_code_spoof:
        modified_request["system"] = [existing_system]
    else:
        # Unrecognized format, wrap it to ensure spoof is first
        modified_request["system"] = [spoof_block, existing_system] if existing_system else [spoof_block]

    logger.debug("Injected Claude Code system message for Anthropic authentication bypass")
    return modified_request
