"""
Logging utilities for request debugging and tracing.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def log_request(request_id: str, request_data: Dict[str, Any], endpoint: str, headers: Optional[Dict[str, str]] = None):
    """Log incoming request details including headers"""
    logger.debug(f"[{request_id}] RAW REQUEST CAPTURE")
    logger.debug(f"[{request_id}] Endpoint: {endpoint}")
    logger.debug(f"[{request_id}] Model: {request_data.get('model', 'unknown')}")
    logger.debug(f"[{request_id}] Stream: {request_data.get('stream', False)}")
    logger.debug(f"[{request_id}] Max Tokens: {request_data.get('max_tokens', 'unknown')}")

    # Log incoming headers
    if headers:
        logger.debug(f"[{request_id}] ===== INCOMING HEADERS FROM CLIENT =====")
        for header_name, header_value in headers.items():
            # Redact sensitive headers
            if header_name.lower() in ['authorization', 'x-api-key', 'api-key']:
                logger.debug(f"[{request_id}] {header_name}: [REDACTED]")
            else:
                logger.debug(f"[{request_id}] {header_name}: {header_value}")

        # Specifically check for anthropic-beta header
        if 'anthropic-beta' in headers:
            logger.debug(f"[{request_id}] *** ANTHROPIC-BETA HEADER FOUND: {headers['anthropic-beta']} ***")

    # Log thinking parameters
    thinking = request_data.get('thinking')
    if thinking:
        logger.debug(f"[{request_id}] THINKING FIELDS DETECTED: {thinking}")

    # Check for alternative thinking fields
    alt_thinking_fields = ['max_thinking_tokens', 'thinking_enabled', 'thinking_budget']
    detected_fields = {field: request_data.get(field) for field in alt_thinking_fields if field in request_data}
    if detected_fields:
        logger.debug(f"[{request_id}] ALTERNATIVE THINKING FIELDS: {detected_fields}")

