import json
import os
import platform
from pathlib import Path
from typing import Optional, Dict, Any
import time

from settings import TOKEN_FILE

class TokenStorage:
    """Secure token storage with file permissions (plan.md sections 3.6 and 10)"""

    def __init__(self):
        self.token_path = Path(TOKEN_FILE)
        self._ensure_secure_directory()

    def _ensure_secure_directory(self):
        """Create parent directory with secure permissions"""
        parent_dir = self.token_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
            # Set directory permissions to 700 on Unix-like systems
            if platform.system() != "Windows":
                os.chmod(parent_dir, 0o700)

    def save_tokens(self, access_token: str, refresh_token: str, expires_in: int):
        """Save tokens with computed expiry time (plan.md section 3.4)"""
        expires_at = int(time.time()) + expires_in
        data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }

        # Write tokens to file
        self.token_path.write_text(json.dumps(data, indent=2))

        # Set file permissions to 600 on Unix-like systems (plan.md section 10)
        if platform.system() != "Windows":
            os.chmod(self.token_path, 0o600)

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load tokens from storage"""
        if not self.token_path.exists():
            return None

        try:
            return json.loads(self.token_path.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    def clear_tokens(self):
        """Remove stored tokens"""
        if self.token_path.exists():
            self.token_path.unlink()

    def is_token_expired(self) -> bool:
        """Check if the stored token is expired"""
        tokens = self.load_tokens()
        if not tokens:
            return True

        expires_at = tokens.get("expires_at", 0)
        # Add 60 second buffer before expiry
        return int(time.time()) >= (expires_at - 60)

    def get_access_token(self) -> Optional[str]:
        """Get the current access token if valid"""
        tokens = self.load_tokens()
        if not tokens:
            return None

        if self.is_token_expired():
            return None

        return tokens.get("access_token")

    def get_refresh_token(self) -> Optional[str]:
        """Get the refresh token"""
        tokens = self.load_tokens()
        if not tokens:
            return None
        return tokens.get("refresh_token")

    def get_status(self) -> Dict[str, Any]:
        """Get token status without exposing secrets (plan.md section 4.4)"""
        tokens = self.load_tokens()
        if not tokens:
            return {"status": "missing", "message": "No tokens found"}

        expires_at = tokens.get("expires_at", 0)
        current_time = int(time.time())

        if current_time >= expires_at:
            return {"status": "expired", "expires_at": expires_at}

        return {
            "status": "valid",
            "expires_at": expires_at,
            "expires_in_seconds": expires_at - current_time
        }