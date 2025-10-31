"""CLI entry point - wrapper for backward compatibility

This file maintains backward compatibility by importing and running
the main CLI from the modular cli package.
"""

from cli.main import main

if __name__ == "__main__":
    main()
