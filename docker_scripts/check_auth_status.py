#!/usr/bin/env python3
"""
Check if authentication tokens are valid.
Exit code 0 = valid, 1 = invalid/expired
"""

import os
import sys
from typing import TypedDict

# Override token file path for Docker environment
os.environ["TOKEN_FILE"] = "/app/data/tokens.json"

from storage import TokenStorage


class TokenStatus(TypedDict):
    has_tokens: bool
    is_expired: bool


def main() -> None:
    storage = TokenStorage()
    status_dict = storage.get_status()
    status = TokenStatus(has_tokens=status_dict["has_tokens"], is_expired=status_dict["is_expired"])

    not_valid = not status["has_tokens"] or status["is_expired"]
    sys.exit(int(not_valid))


if __name__ == "__main__":
    main()
