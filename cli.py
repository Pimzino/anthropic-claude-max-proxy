import asyncio
import sys
import threading
import time
import logging
import argparse
import __main__
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import print as rprint

import settings
import proxy
from storage import TokenStorage
from oauth import OAuthManager
from auth_cli import CLIAuthFlow
from proxy import ProxyServer
from debug_console import create_debug_console

# Global console - will be configured based on debug mode
console = Console()

class AnthropicProxyCLI:
    """Main CLI interface for Anthropic Claude Max Proxy"""

    MAX_RETRIES = 3  # Maximum number of retry attempts for network errors

    def __init__(
        self,
        debug: bool = False,
        debug_sse: bool = False,
        bind_address: str = None,
        stream_trace_enabled: bool = False
    ):
        self.storage = TokenStorage()
        self.oauth = OAuthManager()
        self.auth_flow = CLIAuthFlow()
        self.proxy_server = ProxyServer(
            debug=debug,
            debug_sse=debug_sse,
            bind_address=bind_address
        )
        self.server_thread: Optional[threading.Thread] = None
        self.server_running = False
        self.debug = debug
        self.debug_sse = debug_sse
        self.bind_address = bind_address or self.proxy_server.bind_address
        self.stream_trace_enabled = stream_trace_enabled

        # Configure debug console if debug mode is enabled
        self._setup_debug_console()

        # Debug mode notification
        if debug:
            console.print("[yellow]Debug mode enabled - verbose logging will be written to proxy_debug.log[/yellow]")
        if debug_sse:
            console.print("[yellow]SSE debug mode enabled - detailed streaming events will be logged[/yellow]")
        if stream_trace_enabled:
            console.print("[yellow]Stream tracing enabled - raw SSE chunks will be logged to disk (may include sensitive data).[/yellow]")

        # Create a single event loop for the CLI session
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def _setup_debug_console(self):
        """Setup debug console based on debug mode"""
        global console

        if self.debug:
            # Check if proxy has set up debug logging
            debug_logger = getattr(__main__, '_proxy_debug_logger', None) if hasattr(__main__, '_proxy_debug_logger') else None

            if debug_logger:
                # Replace global console with debug capturing console
                console = create_debug_console(debug_enabled=True, debug_logger=debug_logger)
                # Log CLI session start
                debug_logger.debug("[CLI] ===== CLI SESSION STARTED =====")
                debug_logger.debug(f"[CLI] Debug mode: {self.debug}, SSE debug: {self.debug_sse}")
                debug_logger.debug(f"[CLI] Bind address: {self.bind_address}")

    def clear_screen(self):
        """Clear the terminal screen"""
        console.clear()

    def display_header(self):
        """Display the application header"""
        console.print("=" * 50)
        console.print("    Anthropic Claude Max Proxy", style="bold")
        console.print("=" * 50)

    def get_auth_status(self) -> tuple[str, str]:
        """Get authentication status and expiry info"""
        status = self.storage.get_status()

        if not status["has_tokens"]:
            return "NO AUTH", "No tokens available"

        if status["is_expired"]:
            return "EXPIRED", f"Expired {status['time_until_expiry']}"

        # Calculate time remaining
        if status["expires_at"]:
            expires_dt = datetime.fromisoformat(status["expires_at"])
            now = datetime.now()
            delta = expires_dt - now

            if delta.total_seconds() < 0:
                return "EXPIRED", "Token expired"

            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)

            if hours > 0:
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = f"{minutes}m"

            return "VALID", f"Expires in {time_str}"

        return "UNKNOWN", "Unable to determine status"

    def check_and_refresh_auth(self) -> tuple[bool, str, str]:
        """
        Check authentication status and attempt refresh if needed
        Returns: (success: bool, status: str, message: str)
        """
        # Get the current token status
        status = self.storage.get_status()

        # No tokens at all
        if not status["has_tokens"]:
            return False, "NO_AUTH", "No authentication tokens found. Please login first (option 2)"

        # Token is still valid
        if not status["is_expired"]:
            return True, "VALID", f"Token valid for: {status['time_until_expiry']}"

        # Token is expired - check for refresh token
        refresh_token = self.storage.get_refresh_token()
        if not refresh_token:
            return False, "NO_REFRESH", "Token expired and no refresh token available. Please login again (option 2)"

        # Attempt to refresh the token
        console.print("[yellow]Token expired, attempting automatic refresh...[/yellow]")

        try:
            # Run the async refresh_tokens method using the event loop
            success = self.loop.run_until_complete(self.oauth.refresh_tokens())

            if success:
                # Get updated status after refresh
                new_status = self.storage.get_status()
                time_remaining = new_status.get("time_until_expiry", "unknown")
                return True, "REFRESHED", f"Automatically refreshed expired token. Token valid for: {time_remaining}"
            else:
                # Refresh failed but we don't know why (generic failure)
                return False, "REFRESH_FAILED", "Refresh token invalid or expired. Please login again (option 2)"

        except httpx.NetworkError:
            return False, "NETWORK_ERROR", "Network error during token refresh. Check connection and retry"

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                return False, "INVALID_TOKEN", "Refresh token invalid or expired. Please login again (option 2)"
            elif 500 <= e.response.status_code < 600:
                return False, "SERVER_ERROR", f"Server error during token refresh (HTTP {e.response.status_code}). Try again later"
            else:
                return False, "HTTP_ERROR", f"Token refresh failed (HTTP {e.response.status_code}). Please login (option 2)"

        except Exception as e:
            # Unknown error
            return False, "UNKNOWN_ERROR", f"Token refresh failed: {str(e)}. Please login (option 2)"

    def display_menu(self):
        """Display the main menu"""
        auth_status, auth_detail = self.get_auth_status()

        # Status color based on state
        if auth_status == "VALID":
            status_style = "green"
        elif auth_status == "EXPIRED":
            status_style = "yellow"
        else:
            status_style = "red"

        console.print(f" Auth Status: [{status_style}]{auth_status}[/{status_style}] ({auth_detail})")

        if self.server_running:
            console.print(f" Server Status: [green]RUNNING[/green] at http://{self.bind_address}:8081")
        else:
            console.print(" Server Status: [dim]STOPPED[/dim]")

        console.print("-" * 50)

        # Menu options
        if self.server_running:
            console.print(" 1. Stop Proxy Server")
        else:
            console.print(" 1. Start Proxy Server")

        console.print(" 2. Login / Re-authenticate")
        console.print(" 3. Refresh Token")
        console.print(" 4. Show Token Status")
        console.print(" 5. Logout (Clear Tokens)")
        console.print(" 6. Setup Long-Term Token")
        console.print(" 7. Exit")
        console.print("=" * 50)

    def show_token_status(self):
        """Display detailed token status"""
        status = self.storage.get_status()

        table = Table(title="Token Status Details")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Has Tokens", "Yes" if status["has_tokens"] else "No")
        table.add_row("Is Expired", "Yes" if status["is_expired"] else "No")

        if status["expires_at"]:
            table.add_row("Expires At", status["expires_at"])
            table.add_row("Time Until Expiry", status["time_until_expiry"])

        table.add_row("Token File", str(self.storage.token_file))

        console.print(table)
        console.print("\nPress Enter to continue...")
        input()

    def start_proxy_server(self, retry_count: int = 0):
        """Start the proxy server in a background thread

        Args:
            retry_count: Number of retry attempts made so far (used internally)
        """
        if self.debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Starting proxy server (retry_count: {retry_count})")

        if self.server_running:
            console.print("[yellow]Server is already running[/yellow]")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Server already running, skipping start")
            return

        # Check authentication with automatic refresh
        auth_ok, auth_status, message = self.check_and_refresh_auth()

        if not auth_ok:
            console.print(f"[red]ERROR:[/red] {message}")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Server start failed - auth issue: {auth_status} - {message}")

            # For network errors, offer retry option
            if auth_status == "NETWORK_ERROR":
                if retry_count < self.MAX_RETRIES:
                    console.print(f"\n[yellow]Retry attempt {retry_count + 1} of {self.MAX_RETRIES}[/yellow]")
                    console.print("\nWould you like to:")
                    console.print("1. Retry token refresh")
                    console.print("2. Return to main menu")
                    choice = Prompt.ask("Select option", choices=["1", "2"])

                    if choice == "1":
                        # Retry the refresh with incremented counter
                        self.start_proxy_server(retry_count + 1)
                        return
                else:
                    # Max retries reached
                    console.print(f"\n[red]Maximum retry attempts ({self.MAX_RETRIES}) reached.[/red]")
                    console.print("Please check your network connection and try again later.")

            console.print("\nPress Enter to continue...")
            input()
            return

        # Show success message if token was refreshed
        if auth_status == "REFRESHED":
            console.print(f"[green]{message}[/green]")

        console.print("Starting proxy server...")

        try:
            # Start server in background thread
            self.server_thread = threading.Thread(target=self.proxy_server.run, daemon=True)
            self.server_thread.start()
            self.server_running = True

            # Wait a moment for server to start
            time.sleep(1)

            console.print(f"[green][OK][/green] Proxy running at http://{self.bind_address}:8081")
            console.print(f"\n[bold cyan]Native Anthropic API:[/bold cyan]")
            console.print(f"  Base URL: http://{self.bind_address}:8081")
            console.print(f"  Endpoint: /v1/messages")
            console.print(f"\n[bold cyan]OpenAI-Compatible API:[/bold cyan]")
            console.print(f"  Base URL: http://{self.bind_address}:8081/v1")
            console.print(f"  Endpoint: /v1/chat/completions")
            console.print(f"\n[dim]API Key: any-placeholder-string[/dim]")

            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Proxy server started successfully at {self.bind_address}:8081")

            console.print("\nPress Enter to continue...")
            input()

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to start server: {e}")
            self.server_running = False
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Failed to start server: {e}")
            console.print("\nPress Enter to continue...")
            input()

    def stop_proxy_server(self):
        """Stop the proxy server"""
        if self.debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Stopping proxy server")

        if not self.server_running:
            console.print("[yellow]Server is not running[/yellow]")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Server not running, skipping stop")
            return

        console.print("Stopping proxy server...")

        try:
            self.proxy_server.stop()
            self.server_running = False
            console.print("[green][OK][/green] Server stopped")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Proxy server stopped successfully")

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to stop server: {e}")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Failed to stop server: {e}")

        console.print("\nPress Enter to continue...")
        input()

    def login(self):
        """Handle the login flow"""
        console.print("Starting OAuth login flow...")

        try:
            # Log authentication attempt
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Starting authentication flow")

            # Use the event loop to run the async authenticate method
            success = self.loop.run_until_complete(self.auth_flow.authenticate())

            if success:
                console.print("[green]Authentication successful![/green]")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Authentication successful")
            else:
                console.print("[red]Authentication failed[/red]")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Authentication failed")

        except Exception as e:
            console.print(f"[red]ERROR:[/red] {e}")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Authentication error: {e}")

        console.print("\nPress Enter to continue...")
        input()

    def refresh_token(self):
        """Attempt to refresh the access token"""
        console.print("Attempting to refresh token...")

        if self.debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Manual token refresh requested")

        # Check if we have a refresh token first
        if not self.storage.get_refresh_token():
            console.print("[red]No refresh token available - please login first[/red]")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] No refresh token available for manual refresh")
            console.print("\nPress Enter to continue...")
            input()
            return

        try:
            success = self.loop.run_until_complete(self.oauth.refresh_tokens())

            if success:
                console.print("[green]Token refreshed successfully![/green]")
                # Show updated token status
                auth_status, auth_detail = self.get_auth_status()
                console.print(f"Status: [{('green' if auth_status == 'VALID' else 'yellow')}]{auth_status}[/] ({auth_detail})")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CLI] Manual token refresh successful - {auth_status}: {auth_detail}")
            else:
                console.print("[red]Token refresh failed - please login again[/red]")
                console.print("This usually happens when the refresh token has expired.")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Manual token refresh failed")

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Token refresh failed: {e}")
            console.print("Please try logging in again (option 2)")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Manual token refresh error: {e}")

        console.print("\nPress Enter to continue...")
        input()

    def logout(self):
        """Clear stored tokens"""
        if self.debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Logout confirmation requested")

        if Confirm.ask("Are you sure you want to clear all tokens?"):
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] User confirmed logout")
            try:
                self.storage.clear_tokens()
                console.print("[green]Tokens cleared successfully[/green]")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Tokens cleared successfully")
            except Exception as e:
                console.print(f"[red]ERROR:[/red] {e}")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CLI] Logout error: {e}")
        else:
            console.print("Logout cancelled")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] User cancelled logout")

        console.print("\nPress Enter to continue...")
        input()

    def setup_long_term_token(self):
        """Setup a long-term OAuth token (similar to claude setup-token)"""
        console.print("\n[bold]Setup Long-Term OAuth Token[/bold]")
        console.print("This will generate a long-term token valid for 1 year (365 days).\n")

        if self.debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Starting long-term token setup")

        try:
            # Run the long-term token OAuth flow
            access_token = self.loop.run_until_complete(self.auth_flow.setup_long_term_token())

            if access_token:
                # Verify token was saved
                status = self.storage.get_status()

                console.print("\n[green]✓ Long-term token generated and saved successfully![/green]\n")
                console.print("[bold]Your OAuth Token:[/bold]")
                console.print(f"[cyan]{access_token}[/cyan]\n")

                console.print("[bold]Token Details:[/bold]")
                console.print(f"• Type: Long-term (1 year)")
                console.print(f"• Expires: {status.get('expires_at', 'unknown')}")
                console.print(f"• Time remaining: {status.get('time_until_expiry', 'unknown')}")
                console.print(f"• Saved to: {self.storage.token_file}\n")

                console.print("[bold green]✓ Ready to use![/bold green]")
                console.print("You can now run headless mode without any additional setup:\n")
                console.print("  [cyan]python cli.py --headless[/cyan]\n")

                console.print("[yellow]For use on other machines:[/yellow]")
                console.print("• Set environment variable:")
                console.print(f'  [dim]export ANTHROPIC_OAUTH_TOKEN="{access_token}"[/dim]')
                console.print("• Or pass directly:")
                console.print(f'  [dim]python cli.py --headless --token "{access_token}"[/dim]\n')

                console.print("[yellow]Important:[/yellow]")
                console.print("• This token will NOT auto-refresh (valid for 1 year)")
                console.print("• After 1 year, run this command again to generate a new token")
                console.print("• Store this token securely if using on other machines\n")

                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Long-term token setup successful")
            else:
                console.print("[red]Failed to generate long-term token[/red]")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Long-term token setup failed")

        except Exception as e:
            console.print(f"[red]ERROR:[/red] {e}")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Long-term token setup error: {e}")

        console.print("\nPress Enter to continue...")
        input()

    def run(self):
        """Main CLI loop"""
        while True:
            self.clear_screen()
            self.display_header()
            self.display_menu()

            choice = Prompt.ask("Select option [1-7]", choices=["1", "2", "3", "4", "5", "6", "7"])

            # Log user menu choice for debugging
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] User selected menu option: {choice}")

            if choice == "1":
                if self.server_running:
                    self.stop_proxy_server()
                else:
                    self.start_proxy_server()
            elif choice == "2":
                self.login()
            elif choice == "3":
                self.refresh_token()
            elif choice == "4":
                self.show_token_status()
            elif choice == "5":
                self.logout()
            elif choice == "6":
                self.setup_long_term_token()
            elif choice == "7":
                if self.server_running:
                    console.print("Stopping server before exit...")
                    self.stop_proxy_server()
                # Log session end for debugging
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] ===== CLI SESSION ENDED =====")
                # Clean up the event loop
                self.loop.close()
                console.print("Goodbye!")
                break

    def run_headless(self, auto_start: bool = True):
        """Run in headless mode (non-interactive)"""
        console.print("[bold]Anthropic Claude Max Proxy - Headless Mode[/bold]\n")

        if self.debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Starting headless mode")

        # Check authentication
        auth_ok, auth_status, message = self.check_and_refresh_auth()

        if not auth_ok:
            console.print(f"[red]Authentication Error:[/red] {message}")
            console.print("\n[yellow]To authenticate:[/yellow]")
            console.print("1. Run: python cli.py")
            console.print("2. Select option 2 to login")
            console.print("3. Or set ANTHROPIC_OAUTH_TOKEN environment variable")
            console.print("4. Or use: python cli.py --headless --token \"<your-token>\"")
            sys.exit(1)

        # Show auth status
        status = self.storage.get_status()
        token_type = status.get("token_type", "oauth_flow")
        token_type_display = "Long-term" if token_type == "long_term" else "OAuth Flow"

        console.print(f"[green]✓ Authenticated[/green] ({token_type_display})")
        console.print(f"  Token expires: {status.get('time_until_expiry', 'unknown')}\n")

        if auto_start:
            # Start the server
            console.print(f"Starting proxy server at http://{self.bind_address}:8081...")

            try:
                # Setup signal handlers for graceful shutdown
                def signal_handler(sig, frame):
                    console.print("\n[yellow]Shutting down...[/yellow]")
                    if self.server_running:
                        self.proxy_server.stop()
                    sys.exit(0)

                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)

                # Start server in main thread (blocking)
                self.server_thread = threading.Thread(target=self.proxy_server.run, daemon=True)
                self.server_thread.start()
                self.server_running = True

                # Wait a moment for server to start
                time.sleep(1)

                console.print(f"[green]✓ Proxy server running[/green]\n")
                console.print(f"[bold cyan]Native Anthropic API:[/bold cyan]")
                console.print(f"  Base URL: http://{self.bind_address}:8081")
                console.print(f"  Endpoint: /v1/messages")
                console.print(f"\n[bold cyan]OpenAI-Compatible API:[/bold cyan]")
                console.print(f"  Base URL: http://{self.bind_address}:8081/v1")
                console.print(f"  Endpoint: /v1/chat/completions")
                console.print(f"\n[dim]Press Ctrl+C to stop[/dim]\n")

                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CLI] Headless server started at {self.bind_address}:8081")

                # Keep the main thread alive
                while self.server_running:
                    time.sleep(1)

            except Exception as e:
                console.print(f"[red]ERROR:[/red] Failed to start server: {e}")
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug(f"[CLI] Headless server start failed: {e}")
                sys.exit(1)
        else:
            console.print("[yellow]Auto-start disabled. Server not started.[/yellow]")
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Headless mode with auto-start disabled")

def main():
    """Entry point for the CLI"""
    parser = argparse.ArgumentParser(description="Anthropic Claude Max Proxy CLI")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    parser.add_argument("--debug-sse", action="store_true", help="Enable detailed SSE event logging")
    parser.add_argument("--bind", "-b", default=None, help="Override bind address (default: from config)")
    parser.add_argument(
        "--stream-trace",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable raw stream tracing log capture (implies --stream-trace for --debug unless explicitly disabled)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (non-interactive, requires authentication)"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Provide long-term OAuth token for headless mode (format: sk-ant-oat01-...)"
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Don't automatically start server in headless mode"
    )
    parser.add_argument(
        "--setup-token",
        action="store_true",
        help="Setup a long-term OAuth token and exit"
    )

    args = parser.parse_args()

    # Determine stream tracing preference (config default -> CLI overrides)
    stream_trace_setting = settings.STREAM_TRACE_ENABLED
    if args.stream_trace is None:
        if args.debug or args.debug_sse:
            stream_trace_setting = True
    else:
        stream_trace_setting = args.stream_trace

    # Apply overrides to runtime modules
    settings.STREAM_TRACE_ENABLED = stream_trace_setting
    proxy.STREAM_TRACE_ENABLED = stream_trace_setting

    try:
        cli = AnthropicProxyCLI(
            debug=args.debug,
            debug_sse=args.debug_sse,
            bind_address=args.bind,
            stream_trace_enabled=stream_trace_setting
        )

        # Handle token from CLI argument or environment variable
        token_to_use = args.token or settings.ANTHROPIC_OAUTH_TOKEN
        if token_to_use:
            # Validate token format
            if OAuthManager.validate_token_format(token_to_use):
                console.print("[green]✓ Valid OAuth token provided, saving...[/green]")
                cli.storage.save_long_term_token(token_to_use)
                if args.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] Long-term token saved from CLI/env")
            else:
                console.print("[red]ERROR:[/red] Invalid token format. Expected format: sk-ant-oat01-...")
                sys.exit(1)

        # Handle setup-token command
        if args.setup_token:
            cli.setup_long_term_token()
            sys.exit(0)

        # Run in headless or interactive mode
        if args.headless:
            cli.run_headless(auto_start=not args.no_auto_start)
        else:
            cli.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        console.print("Goodbye!")
    except Exception as e:
        console.print(f"\n[red]Fatal error:[/red] {e}")
        if args.debug:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
