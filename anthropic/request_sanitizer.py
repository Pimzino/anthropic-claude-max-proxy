"""Request sanitization and validation for Anthropic API"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def sanitize_anthropic_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize and validate request for Anthropic API

    Args:
        request_data: Raw request data dictionary

    Returns:
        Sanitized request data dictionary
    """
    sanitized = request_data.copy()

    # Universal parameter validation - clean invalid values regardless of thinking mode
    if 'top_p' in sanitized:
        top_p_val = sanitized['top_p']
        if top_p_val is None or top_p_val == "" or not isinstance(top_p_val, (int, float)):
            logger.debug(f"Removing invalid top_p value: {top_p_val} (type: {type(top_p_val)})")
            del sanitized['top_p']
        elif not (0.0 <= top_p_val <= 1.0):
            logger.debug(f"Removing out-of-range top_p value: {top_p_val}")
            del sanitized['top_p']

    if 'temperature' in sanitized:
        temp_val = sanitized['temperature']
        if temp_val is None or temp_val == "" or not isinstance(temp_val, (int, float)):
            logger.debug(f"Removing invalid temperature value: {temp_val} (type: {type(temp_val)})")
            del sanitized['temperature']

    if 'top_k' in sanitized:
        top_k_val = sanitized['top_k']
        if top_k_val is None or top_k_val == "" or not isinstance(top_k_val, int):
            logger.debug(f"Removing invalid top_k value: {top_k_val} (type: {type(top_k_val)})")
            del sanitized['top_k']
        elif top_k_val <= 0:
            logger.debug(f"Removing invalid top_k value (must be positive): {top_k_val}")
            del sanitized['top_k']

    # Handle tools parameter - remove if null or empty list
    if 'tools' in sanitized:
        tools_val = sanitized.get('tools')
        if tools_val is None:
            logger.debug("Removing null tools parameter (Anthropic API doesn't accept null values)")
            del sanitized['tools']
        elif isinstance(tools_val, list) and len(tools_val) == 0:
            logger.debug("Removing empty tools list (Anthropic API doesn't accept empty tools list)")
            del sanitized['tools']
        elif not isinstance(tools_val, list):
            logger.debug(f"Removing invalid tools parameter (must be a list): {type(tools_val)}")
            del sanitized['tools']

    # Handle thinking parameter - remove if null/None as Anthropic API doesn't accept null values
    thinking = sanitized.get('thinking')
    if thinking is None:
        logger.debug("Removing null thinking parameter (Anthropic API doesn't accept null values)")
        sanitized.pop('thinking', None)
    elif thinking and thinking.get('type') == 'enabled':
        logger.debug("Thinking enabled - applying Anthropic API constraints")

        # Apply Anthropic thinking constraints
        if 'temperature' in sanitized and sanitized['temperature'] is not None and sanitized['temperature'] != 1.0:
            logger.debug(f"Adjusting temperature from {sanitized['temperature']} to 1.0 (thinking enabled)")
            sanitized['temperature'] = 1.0

        if 'top_p' in sanitized and sanitized['top_p'] is not None and not (0.95 <= sanitized['top_p'] <= 1.0):
            adjusted_top_p = max(0.95, min(1.0, sanitized['top_p']))
            logger.debug(f"Adjusting top_p from {sanitized['top_p']} to {adjusted_top_p} (thinking constraints)")
            sanitized['top_p'] = adjusted_top_p

        # Remove top_k as it's not allowed with thinking
        if 'top_k' in sanitized:
            logger.debug("Removing top_k parameter (not allowed with thinking)")
            del sanitized['top_k']

    return sanitized
