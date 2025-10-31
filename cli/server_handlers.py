"""Server start/stop handlers for CLI"""

import __main__
import time
import threading
from typing import Optional
from rich.prompt import Prompt
from proxy import ProxyServer
from utils.storage import TokenStorage
from cli.auth_handlers import check_and_refresh_auth


def start_proxy_server(
    proxy_server: ProxyServer,
    storage: TokenStorage,
    oauth,
    loop,
    console,
    bind_address: str,
    server_running: bool,
    server_thread: Optional[threading.Thread],
    debug: bool = False,
    max_retries: int = 3,
    retry_count: int = 0
) -> tuple[bool, Optional[threading.Thread]]:
    """
    Start the proxy server in a background thread

    Args:
        proxy_server: ProxyServer instance
        storage: TokenStorage instance
        oauth: OAuthManager instance
        loop: Event loop for async operations
        console: Rich console for output
        bind_address: The bind address for the server
        server_running: Whether the server is currently running
        server_thread: The server thread (if any)
        debug: Whether debug mode is enabled
        max_retries: Maximum number of retry attempts
        retry_count: Number of retry attempts made so far

    Returns:
        Tuple of (server_running: bool, server_thread: Optional[threading.Thread])
    """
    if debug and hasattr(__main__, '_proxy_debug_logger'):
        __main__._proxy_debug_logger.debug(f"[CLI] Starting proxy server (retry_count: {retry_count})")

    if server_running:
        console.print("[yellow]Server is already running[/yellow]")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Server already running, skipping start")
        return server_running, server_thread

    # Check authentication with automatic refresh
    auth_ok, auth_status, message = check_and_refresh_auth(storage, oauth, loop, console, debug)

    if not auth_ok:
        console.print(f"[red]ERROR:[/red] {message}")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Server start failed - auth issue: {auth_status} - {message}")

        # For network errors, offer retry option
        if auth_status == "NETWORK_ERROR":
            if retry_count < max_retries:
                console.print(f"\n[yellow]Retry attempt {retry_count + 1} of {max_retries}[/yellow]")
                console.print("\nWould you like to:")
                console.print("1. Retry token refresh")
                console.print("2. Return to main menu")
                choice = Prompt.ask("Select option", choices=["1", "2"])

                if choice == "1":
                    # Retry the refresh with incremented counter
                    return start_proxy_server(
                        proxy_server, storage, oauth, loop, console,
                        bind_address, server_running, server_thread,
                        debug, max_retries, retry_count + 1
                    )
            else:
                # Max retries reached
                console.print(f"\n[red]Maximum retry attempts ({max_retries}) reached.[/red]")
                console.print("Please check your network connection and try again later.")

        console.print("\nPress Enter to continue...")
        input()
        return server_running, server_thread

    # Show success message if token was refreshed
    if auth_status == "REFRESHED":
        console.print(f"[green]{message}[/green]")

    console.print("Starting proxy server...")

    try:
        # Start server in background thread
        server_thread = threading.Thread(target=proxy_server.run, daemon=True)
        server_thread.start()
        server_running = True

        # Wait a moment for server to start
        time.sleep(1)

        console.print(f"[green][OK][/green] Proxy running at http://{bind_address}:8081")
        console.print(f"\n[bold cyan]Native Anthropic API:[/bold cyan]")
        console.print(f"  Base URL: http://{bind_address}:8081")
        console.print(f"  Endpoint: /v1/messages")
        console.print(f"\n[bold cyan]OpenAI-Compatible API:[/bold cyan]")
        console.print(f"  Base URL: http://{bind_address}:8081/v1")
        console.print(f"  Endpoint: /v1/chat/completions")
        console.print(f"\n[dim]API Key: any-placeholder-string[/dim]")

        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Proxy server started successfully at {bind_address}:8081")

        console.print("\nPress Enter to continue...")
        input()

    except Exception as e:
        console.print(f"[red]ERROR:[/red] Failed to start server: {e}")
        server_running = False
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Failed to start server: {e}")
        console.print("\nPress Enter to continue...")
        input()

    return server_running, server_thread


def stop_proxy_server(
    proxy_server: ProxyServer,
    server_running: bool,
    console,
    debug: bool = False
) -> bool:
    """
    Stop the proxy server

    Args:
        proxy_server: ProxyServer instance
        server_running: Whether the server is currently running
        console: Rich console for output
        debug: Whether debug mode is enabled

    Returns:
        Updated server_running state (False)
    """
    if debug and hasattr(__main__, '_proxy_debug_logger'):
        __main__._proxy_debug_logger.debug("[CLI] Stopping proxy server")

    if not server_running:
        console.print("[yellow]Server is not running[/yellow]")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Server not running, skipping stop")
        return server_running

    console.print("Stopping proxy server...")

    try:
        proxy_server.stop()
        server_running = False
        console.print("[green][OK][/green] Server stopped")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Proxy server stopped successfully")

    except Exception as e:
        console.print(f"[red]ERROR:[/red] Failed to stop server: {e}")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Failed to stop server: {e}")

    console.print("\nPress Enter to continue...")
    input()

    return server_running
