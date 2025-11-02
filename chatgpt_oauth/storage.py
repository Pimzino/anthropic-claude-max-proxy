"""Token storage for ChatGPT OAuth"""

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import settings

logger = logging.getLogger(__name__)


class ChatGPTTokenStorage:
    """Manages persistent storage of ChatGPT OAuth tokens"""

    OLD_TOKEN_FILE = Path.home() / ".chatgpt-local" / "tokens.json"

    def __init__(self, token_file: Optional[Path] = None):
        """Initialize token storage

        Args:
            token_file: Path to token file (default: ~/.llmux/chatgpt/tokens.json)
        """
        if token_file is None:
            token_file = Path(settings.CHATGPT_TOKEN_FILE)

        self.token_file = Path(token_file)
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure storage directory exists"""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

    def _maybe_migrate_from_old(self) -> Optional[Dict[str, Any]]:
        """If old ChatGPT token file exists and new doesn't, migrate it."""
        try:
            if not self.token_file.exists() and self.OLD_TOKEN_FILE.exists():
                data = json.loads(self.OLD_TOKEN_FILE.read_text())
                self._ensure_directory()
                self.token_file.write_text(json.dumps(data, indent=2))
                try:
                    self.token_file.chmod(0o600)
                except Exception:
                    pass
                logger.info(f"Migrated ChatGPT tokens to {self.token_file}")
                return data
        except Exception as e:
            logger.debug(f"ChatGPT token migration skipped: {e}")
        return None

    def save_tokens(self, auth_data: Dict[str, Any]) -> bool:
        """Save authentication data to disk

        Args:
            auth_data: Dictionary containing tokens and metadata

        Returns:
            True if save was successful
        """
        try:
            self._ensure_directory()

            # Write with restrictive permissions
            self.token_file.write_text(json.dumps(auth_data, indent=2))
            try:
                self.token_file.chmod(0o600)
            except Exception:
                pass

            logger.debug(f"Saved ChatGPT tokens to {self.token_file}")
            return True

        except (OSError, IOError) as e:
            logger.error(f"Failed to save ChatGPT tokens: {e}")
            return False

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load authentication data from disk

        Returns:
            Dictionary containing tokens and metadata, or None if not found
        """
        if not self.token_file.exists():
            migrated = self._maybe_migrate_from_old()
            if migrated is not None:
                return migrated
            logger.debug("No ChatGPT token file found")
            return None

        try:
            data = json.loads(self.token_file.read_text())
            logger.debug("Loaded ChatGPT tokens from disk")
            return data

        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load ChatGPT tokens: {e}")
            return None

    def clear_tokens(self) -> bool:
        """Clear stored tokens

        Returns:
            True if tokens were cleared successfully
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Cleared ChatGPT tokens")
            return True

        except OSError as e:
            logger.error(f"Failed to clear ChatGPT tokens: {e}")
            return False

    def get_access_token(self) -> Optional[str]:
        """Get access token from storage

        Returns:
            Access token string, or None if not available
        """
        data = self.load_tokens()
        if not data:
            return None

        tokens = data.get("tokens", {})
        return tokens.get("access_token")

    def get_refresh_token(self) -> Optional[str]:
        """Get refresh token from storage

        Returns:
            Refresh token string, or None if not available
        """
        data = self.load_tokens()
        if not data:
            return None

        tokens = data.get("tokens", {})
        return tokens.get("refresh_token")

    def get_account_id(self) -> Optional[str]:
        """Get ChatGPT account ID from storage

        Returns:
            Account ID string, or None if not available
        """
        data = self.load_tokens()
        if not data:
            return None

        tokens = data.get("tokens", {})
        return tokens.get("account_id")

    def is_token_expired(self) -> bool:
        """Check if stored access token is expired

        Returns:
            True if token is expired or not available
        """
        from .token_refresh import should_refresh_access_token

        data = self.load_tokens()
        if not data:
            return True

        tokens = data.get("tokens", {})
        access_token = tokens.get("access_token")
        last_refresh = data.get("last_refresh")

        return should_refresh_access_token(access_token, last_refresh)

    def get_status(self) -> Dict[str, Any]:
        """Get authentication status information

        Returns:
            Dictionary with status information
        """
        data = self.load_tokens()

        if not data:
            return {
                "has_tokens": False,
                "is_expired": True,
                "account_id": None,
                "expires_at": None,
                "time_until_expiry": None,
            }

        tokens = data.get("tokens", {})
        access_token = tokens.get("access_token")
        account_id = tokens.get("account_id")

        # Parse token expiry
        from .utils import parse_jwt_claims
        claims = parse_jwt_claims(access_token) if access_token else {}
        exp = claims.get("exp")

        expires_at = None
        time_until_expiry = None

        if isinstance(exp, (int, float)):
            try:
                expires_at = datetime.datetime.fromtimestamp(
                    float(exp),
                    datetime.timezone.utc
                )
                now = datetime.datetime.now(datetime.timezone.utc)
                delta = expires_at - now

                if delta.total_seconds() > 0:
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    time_until_expiry = f"{hours}h {minutes}m"
                else:
                    time_until_expiry = "expired"
            except (OverflowError, OSError, ValueError):
                pass

        return {
            "has_tokens": bool(access_token),
            "is_expired": self.is_token_expired(),
            "account_id": account_id,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "time_until_expiry": time_until_expiry,
        }
