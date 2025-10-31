"""Menu display functionality for CLI"""

from cli.status_display import get_auth_status


def clear_screen(console):
    """Clear the terminal screen"""
    console.clear()


def display_header(console):
    """Display the application header"""
    console.print("=" * 50)
    console.print("    Anthropic Claude Max Proxy", style="bold")
    console.print("=" * 50)


def display_menu(storage, server_running: bool, bind_address: str, console):
    """
    Display the main menu

    Args:
        storage: TokenStorage instance
        server_running: Whether the server is currently running
        bind_address: The bind address for the server
        console: Rich console for output
    """
    auth_status, auth_detail = get_auth_status(storage)

    # Status color based on state
    if auth_status == "VALID":
        status_style = "green"
    elif auth_status == "EXPIRED":
        status_style = "yellow"
    else:
        status_style = "red"

    console.print(f" Auth Status: [{status_style}]{auth_status}[/{status_style}] ({auth_detail})")

    if server_running:
        console.print(f" Server Status: [green]RUNNING[/green] at http://{bind_address}:8081")
    else:
        console.print(" Server Status: [dim]STOPPED[/dim]")

    console.print("-" * 50)

    # Menu options
    if server_running:
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
