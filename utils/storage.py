import json
import os
import platform
from pathlib import Path
from typing import Optional, Dict, Any
import time

from settings import TOKEN_FILE

class TokenStorage:
    """Secure token storage with file permissions (plan.md sections 3.6 and 10)"""

    OLD_TOKEN_DIR = Path.home() / ".anthropic-claude-max-proxy"
    OLD_TOKEN_PATH = OLD_TOKEN_DIR / "tokens.json"

    def __init__(self, token_file: Optional[str] = None):
        self.token_path = Path(token_file if token_file else TOKEN_FILE)
        self._ensure_secure_directory()

    def _ensure_secure_directory(self):
        """Create parent directory with secure permissions"""
        parent_dir = self.token_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
            # Set directory permissions to 700 on Unix-like systems
            if platform.system() != "Windows":
                os.chmod(parent_dir, 0o700)

    def _migrate_from_old_path_if_present(self) -> Optional[Dict[str, Any]]:
        """If old token exists and new one doesn't, migrate content to new path."""
        try:
            if not self.token_path.exists() and self.OLD_TOKEN_PATH.exists():
                data = json.loads(self.OLD_TOKEN_PATH.read_text())
                # Write to new path
                self._ensure_secure_directory()
                self.token_path.write_text(json.dumps(data, indent=2))
                if platform.system() != "Windows":
                    os.chmod(self.token_path, 0o600)
                return data
        except Exception:
            pass
        return None

    def save_tokens(self, access_token: str, refresh_token: str, expires_in: int):
        """Save tokens with computed expiry time (plan.md section 3.4)"""
        expires_at = int(time.time()) + expires_in
        data = {
            "token_type": "oauth_flow",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at
        }

        # Write tokens to file
        self.token_path.write_text(json.dumps(data, indent=2))

        # Set file permissions to 600 on Unix-like systems (plan.md section 10)
        if platform.system() != "Windows":
            os.chmod(self.token_path, 0o600)

    def save_long_term_token(self, access_token: str, expires_in: Optional[int] = None):
        """Save a long-term OAuth token (e.g., from claude setup-token)

        Args:
            access_token: The long-term OAuth token (format: sk-ant-oat01-...)
            expires_in: Optional expiry time in seconds (default: 1 year)
        """
        # Default to 1 year expiry for long-term tokens
        if expires_in is None:
            expires_in = 365 * 24 * 60 * 60  # 1 year in seconds

        expires_at = int(time.time()) + expires_in
        data = {
            "token_type": "long_term",
            "access_token": access_token,
            "expires_at": expires_at
        }

        # Write tokens to file
        self.token_path.write_text(json.dumps(data, indent=2))

        # Set file permissions to 600 on Unix-like systems
        if platform.system() != "Windows":
            os.chmod(self.token_path, 0o600)

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load tokens from storage"""
        if not self.token_path.exists():
            # Attempt migration from old path
            migrated = self._migrate_from_old_path_if_present()
            if migrated is not None:
                return migrated
            return None

        try:
            data = json.loads(self.token_path.read_text())
            # Migrate old token format (no token_type field)
            if "token_type" not in data:
                data["token_type"] = "oauth_flow"
            return data
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
        # Add 5 second buffer before expiry
        return int(time.time()) >= (expires_at - 5)

    def is_authenticated(self) -> bool:
        """Check if there is a valid, non-expired token"""
        tokens = self.load_tokens()
        if not tokens:
            return False

        return not self.is_token_expired()

    def get_token_type(self) -> Optional[str]:
        """Get the type of stored token (oauth_flow or long_term)"""
        tokens = self.load_tokens()
        if not tokens:
            return None
        return tokens.get("token_type", "oauth_flow")

    def is_long_term_token(self) -> bool:
        """Check if the stored token is a long-term token"""
        return self.get_token_type() == "long_term"

    def get_access_token(self) -> Optional[str]:
        """Get the current access token if valid"""
        tokens = self.load_tokens()
        if not tokens:
            return None

        if self.is_token_expired():
            return None

        return tokens.get("access_token")

    def get_refresh_token(self) -> Optional[str]:
        """Get the refresh token (only available for oauth_flow tokens)"""
        tokens = self.load_tokens()
        if not tokens:
            return None

        # Long-term tokens don't have refresh tokens
        if tokens.get("token_type") == "long_term":
            return None

        return tokens.get("refresh_token")

    def get_status(self) -> Dict[str, Any]:
        """Get token status without exposing secrets (plan.md section 4.4)"""
        tokens = self.load_tokens()
        if not tokens:
            return {
                "has_tokens": False,
                "is_expired": True,
                "expires_at": None,
                "time_until_expiry": "No tokens",
                "token_type": None
            }

        expires_at = tokens.get("expires_at", 0)
        current_time = int(time.time())
        token_type = tokens.get("token_type", "oauth_flow")

        # Convert timestamp to ISO format string for display
        from datetime import datetime
        expires_dt = datetime.fromtimestamp(expires_at)
        expires_str = expires_dt.isoformat()

        if current_time >= expires_at:
            time_since = current_time - expires_at
            hours_since = time_since // 3600
            mins_since = (time_since % 3600) // 60

            if hours_since > 0:
                time_str = f"{hours_since}h {mins_since}m ago"
            else:
                time_str = f"{mins_since}m ago"

            return {
                "has_tokens": True,
                "is_expired": True,
                "expires_at": expires_str,
                "time_until_expiry": time_str,
                "token_type": token_type
            }

        time_remaining = expires_at - current_time
        hours = time_remaining // 3600
        minutes = (time_remaining % 3600) // 60
        days = hours // 24

        # For long-term tokens, show days if > 24 hours
        if token_type == "long_term" and days > 0:
            time_str = f"{days}d {hours % 24}h"
        elif hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"

        return {
            "has_tokens": True,
            "is_expired": False,
            "expires_at": expires_str,
            "time_until_expiry": time_str,
            "expires_in_seconds": time_remaining,
            "token_type": token_type
        }

    @property
    def token_file(self) -> Path:
        """Get the token file path"""
        return self.token_path
