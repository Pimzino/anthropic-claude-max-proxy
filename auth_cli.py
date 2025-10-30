import webbrowser
import __main__
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt

from oauth import OAuthManager
from storage import TokenStorage
from debug_console import create_debug_console

# Console will be configured based on debug mode
console = Console()

class CLIAuthFlow:
    """Handle OAuth authentication flow in CLI"""

    def __init__(self):
        self.oauth = OAuthManager()
        self.storage = TokenStorage()
        self._setup_debug_console()

    def _setup_debug_console(self):
        """Setup debug console if debug mode is enabled"""
        global console

        # Check if debug mode is enabled via the main module
        if hasattr(__main__, '_proxy_debug_enabled') and __main__._proxy_debug_enabled:
            debug_logger = getattr(__main__, '_proxy_debug_logger', None)
            if debug_logger:
                console = create_debug_console(debug_enabled=True, debug_logger=debug_logger)
                debug_logger.debug("[AUTH] ===== AUTH CLI INITIALIZED =====")

    async def authenticate(self) -> bool:
        """
        Run the OAuth authentication flow
        Returns True if successful, False otherwise
        """
        # Log authentication start
        if hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[AUTH] Starting authentication flow")

        try:
            # Step 1: Generate auth URL and open browser
            console.print("\n[bold]Step 1:[/bold] Opening browser for authentication...")
            auth_url = self.oauth.get_authorize_url()

            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] Generated auth URL: {auth_url[:50]}...")

            # Try to open browser
            if webbrowser.open(auth_url):
                console.print("[green][OK][/green] Browser opened successfully")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Browser opened successfully")
            else:
                console.print("[yellow]Could not open browser automatically[/yellow]")
                console.print(f"Please open this URL manually:\n{auth_url}")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Could not open browser automatically")

            # Step 2: Instructions
            console.print("\n[bold]Step 2:[/bold] Complete the login process in your browser")
            console.print("  1. Login to your Claude Pro/Max account if prompted")
            console.print("  2. Authorize the application")
            console.print("  3. You will see an authorization code on the Anthropic page")

            # Step 3: Get code from user
            console.print("\n[bold]Step 3:[/bold] Paste the authorization code below")
            console.print("[dim]The code should look like: CODE#STATE[/dim]\n")

            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[AUTH] Waiting for user to enter authorization code")

            # Use simple input to avoid event loop conflicts
            try:
                code = input("Authorization code: ")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[AUTH] User entered code (length: {len(code.strip()) if code else 0})")
            except KeyboardInterrupt:
                console.print("\n[yellow]Authentication cancelled by user[/yellow]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Authentication cancelled by user (KeyboardInterrupt)")
                return False

            if not code or len(code.strip()) < 10:
                console.print("[red]Invalid or missing code. Please paste the complete code from the browser.[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Invalid or missing authorization code")
                return False

            # Step 4: Exchange code for tokens
            console.print("\n[bold]Step 4:[/bold] Exchanging code for tokens...")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[AUTH] Exchanging authorization code for tokens")

            result = await self.oauth.exchange_code(code.strip())

            if result and result.get("status") == "success":
                console.print("[green][OK][/green] Authentication successful!")
                console.print("[dim]Using OAuth Bearer token for requests[/dim]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] OAuth tokens obtained successfully")

                # Show token status
                status = self.storage.get_status()
                if status["expires_at"]:
                    console.print(f"Token expires at: {status['expires_at']}")
                    if hasattr(__main__, '_proxy_debug_logger'):
                        __main__._proxy_debug_logger.debug(f"[AUTH] Token expires at: {status['expires_at']}")

                return True
            else:
                console.print("[red][ERROR][/red] Failed to exchange code for tokens")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[AUTH] Failed to exchange code for tokens: {result}")
                return False

        except Exception as e:
            console.print(f"[red][ERROR][/red] Authentication failed: {e}")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] Authentication failed with exception: {e}")

            # Offer retry
            retry = Prompt.ask("\nWould you like to try again?", choices=["y", "n"], default="n")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] User retry choice: {retry}")
            if retry.lower() == "y":
                return await self.authenticate()

            return False

    async def refresh_token(self) -> bool:
        """
        Attempt to refresh the access token
        Returns True if successful, False otherwise
        """
        try:
            console.print("Refreshing access token...")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[AUTH] Attempting to refresh access token")

            success = await self.oauth.refresh_tokens()

            if success:
                console.print("[green][OK][/green] Token refreshed successfully")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Token refreshed successfully")

                # Show new expiry
                status = self.storage.get_status()
                if status["expires_at"]:
                    console.print(f"New expiry: {status['expires_at']}")
                    if hasattr(__main__, '_proxy_debug_logger'):
                        __main__._proxy_debug_logger.debug(f"[AUTH] New token expiry: {status['expires_at']}")

                return True
            else:
                console.print("[red][ERROR][/red] Token refresh failed")
                console.print("You may need to login again")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Token refresh failed")
                return False

        except Exception as e:
            console.print(f"[red][ERROR][/red] Refresh failed: {e}")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] Token refresh failed with exception: {e}")
            return False

    async def setup_long_term_token(self) -> Optional[str]:
        """
        Run the OAuth authentication flow to get a long-term token (1 year)
        Returns the access token if successful, None otherwise
        """
        # Log authentication start
        if hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[AUTH] Starting long-term token setup flow")

        try:
            # Step 1: Generate auth URL and open browser
            console.print("\n[bold]Step 1:[/bold] Opening browser for authentication...")
            auth_url = self.oauth.get_authorize_url_for_long_term_token()

            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] Generated auth URL: {auth_url[:50]}...")

            # Try to open browser
            if webbrowser.open(auth_url):
                console.print("[green][OK][/green] Browser opened successfully")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Browser opened successfully")
            else:
                console.print("[yellow]Could not open browser automatically[/yellow]")
                console.print(f"Please open this URL manually:\n{auth_url}")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Could not open browser automatically")

            # Step 2: Instructions
            console.print("\n[bold]Step 2:[/bold] Complete the login process in your browser")
            console.print("  1. Login to your Claude Pro/Max account if prompted")
            console.print("  2. Authorize the application")
            console.print("  3. You will see an authorization code on the Anthropic page")

            # Step 3: Get code from user
            console.print("\n[bold]Step 3:[/bold] Paste the authorization code below")
            console.print("[dim]The code should look like: CODE#STATE[/dim]\n")

            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[AUTH] Waiting for user to enter authorization code")

            # Use simple input to avoid event loop conflicts
            try:
                code = input("Authorization code: ")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[AUTH] User entered code (length: {len(code.strip()) if code else 0})")
            except KeyboardInterrupt:
                console.print("\n[yellow]Authentication cancelled by user[/yellow]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Authentication cancelled by user (KeyboardInterrupt)")
                return None

            if not code or len(code.strip()) < 10:
                console.print("[red]Invalid or missing code. Please paste the complete code from the browser.[/red]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Invalid or missing authorization code")
                return None

            # Step 4: Exchange code for long-term token
            console.print("\n[bold]Step 4:[/bold] Exchanging code for long-term token (1 year validity)...")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[AUTH] Exchanging authorization code for long-term token")

            result = await self.oauth.exchange_code_for_long_term_token(code.strip())

            if result and result.get("status") == "success":
                console.print("[green][OK][/green] Long-term token obtained successfully!")
                console.print(f"[dim]Token valid for {result.get('expires_in', 31536000) // 86400} days[/dim]")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[AUTH] Long-term OAuth token obtained successfully")

                return result.get("access_token")
            else:
                console.print("[red][ERROR][/red] Failed to exchange code for long-term token")
                if hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[AUTH] Failed to exchange code for long-term token: {result}")
                return None

        except Exception as e:
            console.print(f"[red][ERROR][/red] Long-term token setup failed: {e}")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] Long-term token setup failed with exception: {e}")

            # Offer retry
            retry = Prompt.ask("\nWould you like to try again?", choices=["y", "n"], default="n")
            if hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[AUTH] User retry choice: {retry}")
            if retry.lower() == "y":
                return await self.setup_long_term_token()

            return None