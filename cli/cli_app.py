"""Main CLI application class"""

import asyncio
import threading
from typing import Optional
from rich.prompt import Prompt
from utils.storage import TokenStorage
from oauth import OAuthManager
from auth_cli import CLIAuthFlow
from chatgpt_oauth import ChatGPTOAuthManager, ChatGPTTokenStorage
from chatgpt_auth_cli import ChatGPTCLIAuthFlow
from proxy import ProxyServer
from cli.debug_setup import setup_debug_console
from cli.menu import (
    clear_screen,
    display_header,
    display_menu,
    display_auth_menu,
    display_provider_auth_menu
)
from cli.status_display import show_token_status
from cli.auth_handlers import (
    login,
    refresh_token,
    logout,
    setup_long_term_token,
    login_chatgpt,
    refresh_chatgpt_token,
    logout_chatgpt,
)
from cli.server_handlers import start_proxy_server, stop_proxy_server
from cli.headless import run_headless


class AnthropicProxyCLI:
    """Main CLI interface for LLM Subscription Proxy"""

    MAX_RETRIES = 3  # Maximum number of retry attempts for network errors

    def __init__(
        self,
        debug: bool = False,
        debug_sse: bool = False,
        bind_address: str = None,
        stream_trace_enabled: bool = False
    ):
        # Anthropic/Claude
        self.storage = TokenStorage()
        self.oauth = OAuthManager()
        self.auth_flow = CLIAuthFlow()

        # ChatGPT
        self.chatgpt_storage = ChatGPTTokenStorage()
        self.chatgpt_oauth = ChatGPTOAuthManager()
        self.chatgpt_auth_flow = ChatGPTCLIAuthFlow()

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
        self.console = setup_debug_console(debug, debug_sse, self.bind_address)

        # Debug mode notification
        if debug:
            self.console.print("[yellow]Debug mode enabled - verbose logging will be written to proxy_debug.log[/yellow]")
        if debug_sse:
            self.console.print("[yellow]SSE debug mode enabled - detailed streaming events will be logged[/yellow]")
        if stream_trace_enabled:
            self.console.print("[yellow]Stream tracing enabled - raw SSE chunks will be logged to disk (may include sensitive data).[/yellow]")

        # Create a single event loop for the CLI session
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def run(self):
        """Main CLI loop"""
        import __main__

        while True:
            clear_screen(self.console)
            display_header(self.console)
            display_menu(self.storage, self.server_running, self.bind_address, self.console)

            choice = Prompt.ask("Select option [1-4]", choices=["1", "2", "3", "4"])

            # Log user menu choice for debugging
            if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] User selected menu option: {choice}")

            if choice == "1":
                if self.server_running:
                    self.server_running = stop_proxy_server(
                        self.proxy_server, self.server_running, self.console, self.debug
                    )
                else:
                    self.server_running, self.server_thread = start_proxy_server(
                        self.proxy_server, self.storage, self.oauth, self.loop,
                        self.console, self.bind_address, self.server_running,
                        self.server_thread, self.debug, self.MAX_RETRIES
                    )
            elif choice == "2":
                self._handle_auth_menu()
            elif choice == "3":
                self._show_all_token_status()
            elif choice == "4":
                if self.server_running:
                    self.console.print("Stopping server before exit...")
                    self.server_running = stop_proxy_server(
                        self.proxy_server, self.server_running, self.console, self.debug
                    )
                # Log session end for debugging
                if self.debug and hasattr(__main__, '_proxy_debug_logger'):
                    __main__._proxy_debug_logger.debug("[CLI] ===== CLI SESSION ENDED =====")
                # Clean up the event loop
                self.loop.close()
                self.console.print("Goodbye!")
                break

    def _handle_auth_menu(self):
        """Handle authentication submenu"""
        while True:
            clear_screen(self.console)
            display_header(self.console)
            display_auth_menu(self.console)

            choice = Prompt.ask("Select provider [1-3]", choices=["1", "2", "3"])

            if choice == "1":
                self._handle_claude_auth_menu()
            elif choice == "2":
                self._handle_chatgpt_auth_menu()
            elif choice == "3":
                break  # Back to main menu

    def _handle_claude_auth_menu(self):
        """Handle Claude authentication menu"""
        while True:
            clear_screen(self.console)
            display_header(self.console)
            display_provider_auth_menu("Claude", self.console)

            choice = Prompt.ask("Select option [1-6]", choices=["1", "2", "3", "4", "5", "6"])

            if choice == "1":
                login(self.auth_flow, self.loop, self.console, self.debug)
            elif choice == "2":
                refresh_token(self.storage, self.oauth, self.loop, self.console, self.debug)
            elif choice == "3":
                show_token_status(self.storage, self.console)
            elif choice == "4":
                logout(self.storage, self.console, self.debug)
            elif choice == "5":
                setup_long_term_token(self.storage, self.auth_flow, self.loop, self.console, self.debug)
            elif choice == "6":
                break  # Back to auth menu

    def _handle_chatgpt_auth_menu(self):
        """Handle ChatGPT authentication menu"""
        while True:
            clear_screen(self.console)
            display_header(self.console)
            display_provider_auth_menu("ChatGPT", self.console)

            choice = Prompt.ask("Select option [1-5]", choices=["1", "2", "3", "4", "5"])

            if choice == "1":
                login_chatgpt(self.chatgpt_auth_flow, self.loop, self.console, self.debug)
            elif choice == "2":
                refresh_chatgpt_token(self.chatgpt_storage, self.chatgpt_oauth, self.loop, self.console, self.debug)
            elif choice == "3":
                self._show_chatgpt_token_status()
            elif choice == "4":
                logout_chatgpt(self.chatgpt_storage, self.console, self.debug)
            elif choice == "5":
                break  # Back to auth menu

    def _show_all_token_status(self):
        """Show token status for all providers"""
        self.console.print("\n[bold]Claude Token Status:[/bold]")
        show_token_status(self.storage, self.console)

        self.console.print("\n[bold]ChatGPT Token Status:[/bold]")
        self._show_chatgpt_token_status()

    def _show_chatgpt_token_status(self):
        """Show ChatGPT token status"""
        status = self.chatgpt_storage.get_status()

        if not status["has_tokens"]:
            self.console.print("[red]No ChatGPT tokens found[/red]")
            self.console.print("Please login first (Authentication → ChatGPT → Login)")
        else:
            if status["is_expired"]:
                self.console.print("[yellow]ChatGPT Token Status: EXPIRED[/yellow]")
            else:
                self.console.print("[green]ChatGPT Token Status: VALID[/green]")

            if status["account_id"]:
                self.console.print(f"Account ID: {status['account_id']}")

            if status["expires_at"]:
                self.console.print(f"Expires at: {status['expires_at']}")

            if status["time_until_expiry"]:
                self.console.print(f"Time until expiry: {status['time_until_expiry']}")

        self.console.print("\nPress Enter to continue...")
        input()

    def run_headless_mode(self, auto_start: bool = True):
        """Run in headless mode (non-interactive)"""
        run_headless(
            self.proxy_server,
            self.storage,
            self.oauth,
            self.loop,
            self.console,
            self.bind_address,
            self.debug,
            auto_start
        )
