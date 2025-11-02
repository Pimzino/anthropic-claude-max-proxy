"""CLI entry point and argument parsing"""

import sys
import argparse
import __main__
from rich.console import Console
import settings
from oauth import OAuthManager
from cli.cli_app import AnthropicProxyCLI


console = Console()


def main():
    """Entry point for the CLI"""
    parser = argparse.ArgumentParser(description="LLMux CLI")
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
            from cli.auth_handlers import setup_long_term_token
            setup_long_term_token(cli.storage, cli.auth_flow, cli.loop, cli.console, cli.debug)
            sys.exit(0)

        # Run in headless or interactive mode
        if args.headless:
            cli.run_headless_mode(auto_start=not args.no_auto_start)
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
