"""Debug console setup for CLI"""

import __main__
from rich.console import Console
from utils.debug_console import create_debug_console


def setup_debug_console(debug: bool, debug_sse: bool, bind_address: str) -> Console:
    """
    Setup debug console based on debug mode

    Args:
        debug: Whether debug mode is enabled
        debug_sse: Whether SSE debug mode is enabled
        bind_address: The bind address for the server

    Returns:
        Console instance (either regular or debug-enabled)
    """
    console = Console()

    if debug:
        # Check if proxy has set up debug logging
        debug_logger = getattr(__main__, '_proxy_debug_logger', None) if hasattr(__main__, '_proxy_debug_logger') else None

        if debug_logger:
            # Replace global console with debug capturing console
            console = create_debug_console(debug_enabled=True, debug_logger=debug_logger)
            # Log CLI session start
            debug_logger.debug("[CLI] ===== CLI SESSION STARTED =====")
            debug_logger.debug(f"[CLI] Debug mode: {debug}, SSE debug: {debug_sse}")
            debug_logger.debug(f"[CLI] Bind address: {bind_address}")

    return console
