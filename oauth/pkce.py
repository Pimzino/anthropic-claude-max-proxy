"""PKCE (Proof Key for Code Exchange) generation and management"""

import base64
import hashlib
import json
import secrets
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class PKCEManager:
    """Manages PKCE code verifier and challenge generation and storage"""

    def __init__(self):
        self.code_verifier: Optional[str] = None
        self.state: Optional[str] = None
        self.pkce_file = Path(tempfile.gettempdir()) / "anthropic_oauth_pkce.json"

    def generate_pkce(self) -> Tuple[str, str]:
        """Generate PKCE code verifier and challenge

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate high-entropy code_verifier (43-128 chars)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        # Create code_challenge using SHA-256
        challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')

        return code_verifier, code_challenge

    def save_pkce(self):
        """Save PKCE values temporarily to disk"""
        self.pkce_file.write_text(json.dumps({
            "code_verifier": self.code_verifier,
            "state": self.state
        }))

    def load_pkce(self) -> Tuple[Optional[str], Optional[str]]:
        """Load saved PKCE values from disk

        Returns:
            Tuple of (code_verifier, state) or (None, None) if not found
        """
        if self.pkce_file.exists():
            try:
                data = json.loads(self.pkce_file.read_text())
                return data.get("code_verifier"), data.get("state")
            except (json.JSONDecodeError, IOError):
                pass
        return None, None

    def clear_pkce(self):
        """Clear PKCE values after use"""
        if self.pkce_file.exists():
            self.pkce_file.unlink()
        self.code_verifier = None
        self.state = None
