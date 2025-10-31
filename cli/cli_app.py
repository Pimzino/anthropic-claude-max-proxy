"""Main CLI application class"""

import asyncio
import threading
from typing import Optional
from rich.prompt import Prompt
from utils.storage import TokenStorage
from oauth import OAuthManager
from auth_cli import CLIAuthFlow
from proxy import ProxyServer
from cli.debug_setup import setup_debug_console
from cli.menu import clear_screen, display_header, display_menu
from cli.status_display import show_token_status
from cli.auth_handlers import login, refresh_token, logout, setup_long_term_token
from cli.server_handlers import start_proxy_server, stop_proxy_server
from cli.headless import run_headless


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

            choice = Prompt.ask("Select option [1-7]", choices=["1", "2", "3", "4", "5", "6", "7"])

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
                login(self.auth_flow, self.loop, self.console, self.debug)
            elif choice == "3":
                refresh_token(self.storage, self.oauth, self.loop, self.console, self.debug)
            elif choice == "4":
                show_token_status(self.storage, self.console)
            elif choice == "5":
                logout(self.storage, self.console, self.debug)
            elif choice == "6":
                setup_long_term_token(self.storage, self.auth_flow, self.loop, self.console, self.debug)
            elif choice == "7":
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
