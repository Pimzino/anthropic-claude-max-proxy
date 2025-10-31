"""Beta header management for Anthropic API"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def build_beta_headers(
    anthropic_request: Dict[str, Any],
    client_beta_headers: Optional[str] = None,
    request_id: Optional[str] = None,
    for_streaming: bool = False
) -> str:
    """Build beta header value based on request features

    Args:
        anthropic_request: The Anthropic API request data
        client_beta_headers: Optional client-provided beta headers
        request_id: Optional request ID for logging
        for_streaming: Whether this is for a streaming request

    Returns:
        Comma-separated beta header value
    """
    # Core required beta header for OAuth authentication
    required_betas: List[str] = ["oauth-2025-04-20"]

    # Check for 1M context variant (only for streaming)
    if for_streaming:
        use_1m_context = anthropic_request.get("_use_1m_context", False)
        if use_1m_context:
            required_betas.append("context-1m-2025-08-07")
            if request_id:
                logger.debug(f"[{request_id}] Adding context-1m beta (1M context model variant requested)")

    # Check if thinking is enabled
    thinking = anthropic_request.get("thinking")
    if thinking and thinking.get("type") == "enabled":
        required_betas.append("interleaved-thinking-2025-05-14")
        if request_id:
            logger.debug(f"[{request_id}] Adding interleaved-thinking beta (thinking enabled)")

    # Check if tools are present (non-streaming only)
    if not for_streaming and anthropic_request.get("tools"):
        required_betas.append("fine-grained-tool-streaming-2025-05-14")

    # Handle client beta headers
    if for_streaming:
        # For streaming, ignore client beta headers as they may request tier-4-only features
        if client_beta_headers and request_id:
            logger.debug(f"[{request_id}] Ignoring client beta headers (not supported): {client_beta_headers}")
    else:
        # For non-streaming, merge with client beta headers if provided
        if client_beta_headers:
            client_betas = [beta.strip() for beta in client_beta_headers.split(",")]
            all_betas = list(dict.fromkeys(required_betas + client_betas))
            required_betas = all_betas

    beta_header_value = ",".join(required_betas)

    if request_id:
        logger.debug(f"[{request_id}] Final beta headers: {beta_header_value}")

    return beta_header_value
