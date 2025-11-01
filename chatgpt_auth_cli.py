"""ChatGPT OAuth authentication CLI flow"""

import webbrowser
import __main__
import http.server
import threading
import time
from typing import Optional
from urllib.parse import urlparse, parse_qs
from rich.console import Console
from rich.prompt import Prompt

from chatgpt_oauth import (
    ChatGPTOAuthManager,
    ChatGPTTokenStorage,
    AuthorizationURLBuilder,
    PKCEManager,
    exchange_code_for_tokens,
)
from utils.debug_console import create_debug_console

# Console will be configured based on debug mode
console = Console()


class ChatGPTCLIAuthFlow:
    """Handle ChatGPT OAuth authentication flow in CLI"""

    def __init__(self):
        self.oauth_manager = ChatGPTOAuthManager()
        self.storage = ChatGPTTokenStorage()
        self.pkce_manager = PKCEManager()
        self._setup_debug_console()

    def _setup_debug_console(self):
        """Setup debug console if debug mode is enabled"""
        global console

        # Check if debug mode is enabled via the main module
        if hasattr(__main__, '_proxy_debug_enabled') and __main__._proxy_debug_enabled:
            debug_logger = getattr(__main__, '_proxy_debug_logger', None)
            if debug_logger:
                console = create_debug_console(debug_enabled=True, debug_logger=debug_logger)
                debug_logger.debug("[CHATGPT_AUTH] ===== CHATGPT AUTH CLI INITIALIZED =====")

    async def authenticate(self) -> bool:
        """Run the ChatGPT OAuth authentication flow

        Returns:
            True if successful, False otherwise
        """
        # Log authentication start
        if hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Starting authentication flow")

        try:
            # Step 1: Generate auth URL and open browser
            console.print("\n[bold]Step 1:[/bold] Opening browser for ChatGPT authentication...")

            auth_builder = AuthorizationURLBuilder(self.pkce_manager)
            auth_url = auth_builder.get_authorize_url()

            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CHATGPT_AUTH] Generated auth URL: {auth_url[:50]}...")

            # Try to open browser
            if webbrowser.open(auth_url):
                console.print("[green][OK][/green] Browser opened successfully")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Browser opened successfully")
            else:
                console.print("[yellow]Could not open browser automatically[/yellow]")
                console.print(f"Please open this URL manually:\n{auth_url}")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Could not open browser automatically")

            # Step 2: Instructions
            console.print("\n[bold]Step 2:[/bold] Complete the login process in your browser")
            console.print("  1. Login to your ChatGPT Plus/Pro account if prompted")
            console.print("  2. Authorize the application")
            console.print("  3. You will be redirected to a callback URL")

            # Step 3: Get callback URL from user
            console.print("\n[bold]Step 3:[/bold] Paste the callback URL below")
            console.print("[dim]The URL should start with: http://localhost:1455/auth/callback?code=[/dim]\n")

            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Waiting for user to enter callback URL")

            # Use simple input to avoid event loop conflicts
            try:
                callback_url = input("Callback URL: ")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CHATGPT_AUTH] User entered URL (length: {len(callback_url.strip()) if callback_url else 0})")
            except KeyboardInterrupt:
                console.print("\n[yellow]Authentication cancelled by user[/yellow]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Authentication cancelled by user (KeyboardInterrupt)")
                return False

            if not callback_url or not callback_url.strip().startswith("http"):
                console.print("[red]Invalid callback URL. Please paste the complete URL from the browser.[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Invalid callback URL")
                return False

            # Parse callback URL to extract code
            try:
                parsed = urlparse(callback_url.strip())
                params = parse_qs(parsed.query)
                code = params.get("code", [None])[0]
                state = params.get("state", [None])[0]

                if not code:
                    console.print("[red]No authorization code found in URL[/red]")
                    if hasattr(__main__, '_proxy_debug_logger'):
                        __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] No authorization code in callback URL")
                    return False

                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CHATGPT_AUTH] Extracted code from URL (length: {len(code)})")

            except Exception as e:
                console.print(f"[red]Failed to parse callback URL: {e}[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CHATGPT_AUTH] Failed to parse callback URL: {e}")
                return False

            # Step 4: Exchange code for tokens
            console.print("\n[bold]Step 4:[/bold] Exchanging code for tokens...")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Exchanging authorization code for tokens")

            try:
                auth_bundle = await exchange_code_for_tokens(code, self.pkce_manager)
            except Exception as e:
                console.print(f"[red]Token exchange error: {e}[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CHATGPT_AUTH] Token exchange error: {e}", exc_info=True)
                return False

            if not auth_bundle:
                console.print("[red]Failed to exchange code for tokens[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Token exchange failed")
                return False

            # Step 5: Save tokens
            console.print("\n[bold]Step 5:[/bold] Saving tokens...")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Saving tokens to storage")

            auth_data = {
                "tokens": {
                    "id_token": auth_bundle.token_data.id_token,
                    "access_token": auth_bundle.token_data.access_token,
                    "refresh_token": auth_bundle.token_data.refresh_token,
                    "account_id": auth_bundle.token_data.account_id,
                },
                "last_refresh": auth_bundle.last_refresh,
            }

            if self.storage.save_tokens(auth_data):
                console.print("[green][OK][/green] Authentication successful!")
                console.print("[dim]Using OAuth Bearer token for ChatGPT requests[/dim]")

                # Show account info
                if auth_bundle.token_data.account_id:
                    console.print(f"\n[bold]Account ID:[/bold] {auth_bundle.token_data.account_id}")

                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Authentication successful, tokens saved")

                return True
            else:
                console.print("[red]Failed to save tokens[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CHATGPT_AUTH] Failed to save tokens")
                return False

        except Exception as e:
            console.print(f"[red]Authentication error: {e}[/red]")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CHATGPT_AUTH] Authentication error: {e}", exc_info=True)
            return False
