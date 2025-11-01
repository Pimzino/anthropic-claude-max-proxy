"""Menu display functionality for CLI"""

from cli.status_display import get_auth_status


def clear_screen(console):
    """Clear the terminal screen"""
    console.clear()


def display_header(console):
    """Display the application header"""
    console.print("=" * 50)
    console.print("    LLM Subscription Proxy", style="bold")
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

    console.print(f" Claude Auth: [{status_style}]{auth_status}[/{status_style}] ({auth_detail})")

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

    console.print(" 2. Authentication (Claude / ChatGPT)")
    console.print(" 3. Show Token Status")
    console.print(" 4. Exit")
    console.print("=" * 50)


def display_auth_menu(console):
    """Display authentication submenu"""
    console.print("\n" + "=" * 50)
    console.print("    Authentication", style="bold")
    console.print("=" * 50)
    console.print(" 1. Anthropic Claude")
    console.print(" 2. ChatGPT (OpenAI)")
    console.print(" 3. Back to Main Menu")
    console.print("=" * 50)


def display_provider_auth_menu(provider: str, console):
    """Display provider-specific authentication menu

    Args:
        provider: Provider name (e.g., "Claude", "ChatGPT")
        console: Rich console for output
    """
    console.print("\n" + "=" * 50)
    console.print(f"    {provider} Authentication", style="bold")
    console.print("=" * 50)
    console.print(" 1. Login / Re-authenticate")
    console.print(" 2. Refresh Token")
    console.print(" 3. Show Token Status")
    console.print(" 4. Logout (Clear Tokens)")
    if provider == "Claude":
        console.print(" 5. Setup Long-Term Token")
        console.print(" 6. Back to Authentication Menu")
    else:
        console.print(" 5. Back to Authentication Menu")
    console.print("=" * 50)
