#!/usr/bin/env python3
"""
Docker container authentication handler.
Checks token status and handles authentication flow when needed.
"""

import asyncio
import os
import sys
from typing import TypedDict, cast

# Override token file path for Docker environment
os.environ["TOKEN_FILE"] = "/app/data/tokens.json"

from auth_cli import CLIAuthFlow
from storage import TokenStorage


class TokenStatus(TypedDict):
    has_tokens: bool
    is_expired: bool


def main() -> None:
    """Check tokens and run authentication if needed"""
    storage = TokenStorage()
    status = cast(TokenStatus, storage.get_status())

    if status["has_tokens"] and not status["is_expired"]:
        print("✓ Authentication already valid")
        sys.exit(0)

    auth_flow = CLIAuthFlow()
    try:
        failed_to_authenticate = not asyncio.run(auth_flow.authenticate())
        sys.exit(int(failed_to_authenticate))

    except KeyboardInterrupt:
        print("\nAuthentication cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"Authentication error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
