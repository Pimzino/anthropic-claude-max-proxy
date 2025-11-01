"""PKCE (Proof Key for Code Exchange) manager for ChatGPT OAuth"""

import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional, Tuple

from .models import PkceCodes


class PKCEManager:
    """Manages PKCE codes for secure OAuth flow

    PKCE prevents authorization code interception attacks by requiring
    the client to prove it initiated the OAuth flow.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize PKCE manager

        Args:
            storage_dir: Directory to store PKCE state (default: ~/.chatgpt-local)
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".chatgpt-local"

        self.storage_dir = storage_dir
        self.pkce_file = storage_dir / "pkce.json"
        self.code_verifier: Optional[str] = None
        self.state: Optional[str] = None

    def generate_pkce(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate random code verifier (128 hex characters = 64 bytes)
        code_verifier = secrets.token_hex(64)

        # Generate code challenge (SHA256 hash, base64url encoded)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        # Base64url encoding without padding
        code_challenge = (
            digest.hex()
            .encode()
            .hex()
        )
        # Proper base64url encoding
        import base64
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

        self.code_verifier = code_verifier
        return code_verifier, code_challenge

    def save_pkce(self) -> None:
        """Save PKCE state to disk for retrieval after OAuth redirect"""
        if not self.code_verifier or not self.state:
            return

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        pkce_data = {
            "code_verifier": self.code_verifier,
            "state": self.state,
        }

        self.pkce_file.write_text(json.dumps(pkce_data, indent=2))
        # Set restrictive permissions
        self.pkce_file.chmod(0o600)

    def load_pkce(self) -> bool:
        """Load PKCE state from disk

        Returns:
            True if PKCE state was loaded successfully
        """
        if not self.pkce_file.exists():
            return False

        try:
            pkce_data = json.loads(self.pkce_file.read_text())
            self.code_verifier = pkce_data.get("code_verifier")
            self.state = pkce_data.get("state")
            return bool(self.code_verifier and self.state)
        except (json.JSONDecodeError, OSError):
            return False

    def clear_pkce(self) -> None:
        """Clear PKCE state from disk"""
        if self.pkce_file.exists():
            self.pkce_file.unlink()
        self.code_verifier = None
        self.state = None
