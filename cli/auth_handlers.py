"""Authentication handlers for CLI"""

import __main__
import httpx
from rich.prompt import Confirm
from utils.storage import TokenStorage
from oauth import OAuthManager
from auth_cli import CLIAuthFlow


def check_and_refresh_auth(
    storage: TokenStorage,
    oauth: OAuthManager,
    loop,
    console,
    debug: bool = False
) -> tuple[bool, str, str]:
    """
    Check authentication status and attempt refresh if needed

    Args:
        storage: TokenStorage instance
        oauth: OAuthManager instance
        loop: Event loop for async operations
        console: Rich console for output
        debug: Whether debug mode is enabled

    Returns:
        Tuple of (success: bool, status: str, message: str)
    """
    # Get the current token status
    status = storage.get_status()

    # No tokens at all
    if not status["has_tokens"]:
        return False, "NO_AUTH", "No authentication tokens found. Please login first (option 2)"

    # Token is still valid
    if not status["is_expired"]:
        return True, "VALID", f"Token valid for: {status['time_until_expiry']}"

    # Token is expired - check for refresh token
    refresh_token = storage.get_refresh_token()
    if not refresh_token:
        return False, "NO_REFRESH", "Token expired and no refresh token available. Please login again (option 2)"

    # Attempt to refresh the token
    console.print("[yellow]Token expired, attempting automatic refresh...[/yellow]")

    try:
        # Run the async refresh_tokens method using the event loop
        success = loop.run_until_complete(oauth.refresh_tokens())

        if success:
            # Get updated status after refresh
            new_status = storage.get_status()
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


def login(auth_flow: CLIAuthFlow, loop, console, debug: bool = False):
    """
    Handle the login flow

    Args:
        auth_flow: CLIAuthFlow instance
        loop: Event loop for async operations
        console: Rich console for output
        debug: Whether debug mode is enabled
    """
    console.print("Starting OAuth login flow...")

    try:
        # Log authentication attempt
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] Starting authentication flow")

        # Use the event loop to run the async authenticate method
        success = loop.run_until_complete(auth_flow.authenticate())

        if success:
            console.print("[green]Authentication successful![/green]")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Authentication successful")
        else:
            console.print("[red]Authentication failed[/red]")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Authentication failed")

    except Exception as e:
        console.print(f"[red]ERROR:[/red] {e}")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Authentication error: {e}")

    console.print("\nPress Enter to continue...")
    input()


def refresh_token(
    storage: TokenStorage,
    oauth: OAuthManager,
    loop,
    console,
    debug: bool = False
):
    """
    Attempt to refresh the access token

    Args:
        storage: TokenStorage instance
        oauth: OAuthManager instance
        loop: Event loop for async operations
        console: Rich console for output
        debug: Whether debug mode is enabled
    """
    from cli.status_display import get_auth_status

    console.print("Attempting to refresh token...")

    if debug and hasattr(__main__, '_proxy_debug_logger'):
        __main__._proxy_debug_logger.debug("[CLI] Manual token refresh requested")

    # Check if we have a refresh token first
    if not storage.get_refresh_token():
        console.print("[red]No refresh token available - please login first[/red]")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] No refresh token available for manual refresh")
        console.print("\nPress Enter to continue...")
        input()
        return

    try:
        success = loop.run_until_complete(oauth.refresh_tokens())

        if success:
            console.print("[green]Token refreshed successfully![/green]")
            # Show updated token status
            auth_status, auth_detail = get_auth_status(storage)
            console.print(f"Status: [{('green' if auth_status == 'VALID' else 'yellow')}]{auth_status}[/] ({auth_detail})")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Manual token refresh successful - {auth_status}: {auth_detail}")
        else:
            console.print("[red]Token refresh failed - please login again[/red]")
            console.print("This usually happens when the refresh token has expired.")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Manual token refresh failed")

    except Exception as e:
        console.print(f"[red]ERROR:[/red] Token refresh failed: {e}")
        console.print("Please try logging in again (option 2)")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Manual token refresh error: {e}")

    console.print("\nPress Enter to continue...")
    input()


def logout(storage: TokenStorage, console, debug: bool = False):
    """
    Clear stored tokens

    Args:
        storage: TokenStorage instance
        console: Rich console for output
        debug: Whether debug mode is enabled
    """
    if debug and hasattr(__main__, '_proxy_debug_logger'):
        __main__._proxy_debug_logger.debug("[CLI] Logout confirmation requested")

    if Confirm.ask("Are you sure you want to clear all tokens?"):
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] User confirmed logout")
        try:
            storage.clear_tokens()
            console.print("[green]Tokens cleared successfully[/green]")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Tokens cleared successfully")
        except Exception as e:
            console.print(f"[red]ERROR:[/red] {e}")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug(f"[CLI] Logout error: {e}")
    else:
        console.print("Logout cancelled")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug("[CLI] User cancelled logout")

    console.print("\nPress Enter to continue...")
    input()


def setup_long_term_token(
    storage: TokenStorage,
    auth_flow: CLIAuthFlow,
    loop,
    console,
    debug: bool = False
):
    """
    Setup a long-term OAuth token (similar to claude setup-token)

    Args:
        storage: TokenStorage instance
        auth_flow: CLIAuthFlow instance
        loop: Event loop for async operations
        console: Rich console for output
        debug: Whether debug mode is enabled
    """
    console.print("\n[bold]Setup Long-Term OAuth Token[/bold]")
    console.print("This will generate a long-term token valid for 1 year (365 days).\n")

    if debug and hasattr(__main__, '_proxy_debug_logger'):
        __main__._proxy_debug_logger.debug("[CLI] Starting long-term token setup")

    try:
        # Run the long-term token OAuth flow
        access_token = loop.run_until_complete(auth_flow.setup_long_term_token())

        if access_token:
            # Verify token was saved
            status = storage.get_status()

            console.print("\n[green]✓ Long-term token generated and saved successfully![/green]\n")
            console.print("[bold]Your OAuth Token:[/bold]")
            console.print(f"[cyan]{access_token}[/cyan]\n")

            console.print("[bold]Token Details:[/bold]")
            console.print(f"• Type: Long-term (1 year)")
            console.print(f"• Expires: {status.get('expires_at', 'unknown')}")
            console.print(f"• Time remaining: {status.get('time_until_expiry', 'unknown')}")
            console.print(f"• Saved to: {storage.token_file}\n")

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

            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Long-term token setup successful")
        else:
            console.print("[red]Failed to generate long-term token[/red]")
            if debug and hasattr(__main__, '_proxy_debug_logger'):
                __main__._proxy_debug_logger.debug("[CLI] Long-term token setup failed")

    except Exception as e:
        console.print(f"[red]ERROR:[/red] {e}")
        if debug and hasattr(__main__, '_proxy_debug_logger'):
            __main__._proxy_debug_logger.debug(f"[CLI] Long-term token setup error: {e}")

    console.print("\nPress Enter to continue...")
    input()
