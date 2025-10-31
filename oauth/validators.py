"""OAuth token validation utilities"""

import re


def is_long_term_token_format(token: str) -> bool:
    """Check if a token matches the long-term OAuth token format (sk-ant-oat01-...)

    Args:
        token: The token string to validate

    Returns:
        True if token matches long-term format, False otherwise
    """
    if not token:
        return False
    # Long-term OAuth tokens start with sk-ant-oat01-
    return token.startswith("sk-ant-oat01-")


def validate_token_format(token: str) -> bool:
    """Validate that a token has the correct format

    Args:
        token: The token string to validate

    Returns:
        True if token format is valid, False otherwise
    """
    if not token:
        return False
    # Check for OAuth token format (sk-ant-oat01-...)
    # Token should be at least 20 characters and contain only valid characters
    if is_long_term_token_format(token):
        return len(token) > 20 and re.match(r'^sk-ant-oat01-[A-Za-z0-9_-]+$', token) is not None
    return False
