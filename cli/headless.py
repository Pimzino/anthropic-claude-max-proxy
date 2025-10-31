"""Headless mode functionality for CLI"""

import __main__
import sys
import time
import signal
import threading
from typing import Optional
from proxy import ProxyServer
from utils.storage import TokenStorage
from cli.auth_handlers import check_and_refresh_auth


def run_headless(
    proxy_server: ProxyServer,
    storage: TokenStorage,
    oauth,
    loop,
    console,
    bind_address: str,
    debug: bool = False,
    auto_start: bool = True
):
    """
    Run in headless mode (non-interactive)

    Args:
        proxy_server: ProxyServer instance
        storage: TokenStorage instance
        oauth: OAuthManager instance
        loop: Event loop for async operations
        console: Rich console for output
        bind_address: The bind address for the server
        debug: Whether debug mode is enabled
        auto_start: Whether to automatically start the server
    """
    console.print("[bold]Anthropic Claude Max Proxy - Headless Mode[/bold]\n")

    if debug and hasattr(__main__, '_proxy_debug_logger'):
        __main__._proxy_debug_logger.debug("[CLI] Starting headless mode")

    # Check authentication
    auth_ok, auth_status, message = check_and_refresh_auth(storage, oauth, loop, console, debug)

    if not auth_ok:
        console.print(f"[red]Authentication Error:[/red] {message}")
        console.print("\n[yellow]To authenticate:[/yellow]")
        console.print("1. Run: python cli.py")
        console.print("2. Select option 2 to login")
        console.print("3. Or set ANTHROPIC_OAUTH_TOKEN environment variable")
        console.print("4. Or use: python cli.py --headless --token \"<your-token>\"")
        sys.exit(1)

    # Show auth status
    status = storage.get_status()
    token_type = status.get("token_type", "oauth_flow")
    token_type_display = "Long-term" if token_type == "long_term" else "OAuth Flow"

    console.print(f"[green]✓ Authenticated[/green] ({token_type_display})")
    console.print(f"  Token expires: {status.get('time_until_expiry', 'unknown')}\n")

    if auto_start:
        # Start the server
        console.print(f"Starting proxy server at http://{bind_address}:8081...")

        try:
            server_running = False

            # Setup signal handlers for graceful shutdown
            def signal_handler(sig, frame):
                console.print("\n[yellow]Shutting down...[/yellow]")
                if server_running:
                    proxy_server.stop()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Start server in main thread (blocking)
            server_thread = threading.Thread(target=proxy_server.run, daemon=True)
            server_thread.start()
            server_running = True

            # Wait a moment for server to start
            time.sleep(1)

            console.print(f"[green]✓ Proxy server running[/green]\n")
            console.print(f"[bold cyan]Native Anthropic API:[/bold cyan]")
            console.print(f"  Base URL: http://{bind_address}:8081")
            console.print(f"  Endpoint: /v1/messages")
            console.print(f"\n[bold cyan]OpenAI-Compatible API:[/bold cyan]")
            console.print(f"  Base URL: http://{bind_address}:8081/v1")
            console.print(f"  Endpoint: /v1/chat/completions")
            console.print(f"\n[dim]Press Ctrl+C to stop[/dim]\n")

            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Headless server started at {bind_address}:8081")

            # Keep the main thread alive
            while server_running:
                time.sleep(1)

        except Exception as e:
            console.print(f"[red]ERROR:[/red] Failed to start server: {e}")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Headless server start failed: {e}")
            sys.exit(1)
    else:
        console.print("[yellow]Auto-start disabled. Server not started.[/yellow]")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Headless mode with auto-start disabled")
