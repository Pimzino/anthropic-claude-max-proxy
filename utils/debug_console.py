"""Debug console module for capturing Rich console output to log files.

This module provides a custom Rich Console implementation that transparently
captures all console output to a debug log file when debug mode is enabled.
"""

import logging
import io
import re
from typing import Optional
from rich.console import Console as RichConsole


class DebugCapturingConsole(RichConsole):
    """
    Custom Rich Console that captures all output to a debug log file.

    This console acts as a transparent wrapper around Rich Console,
    maintaining all visual formatting in the terminal while simultaneously
    logging plain text versions to the debug log file.
    """

    def __init__(self, debug_logger: Optional[logging.Logger] = None, *args, **kwargs):
        """
        Initialize the debug capturing console.

        Args:
            debug_logger: Logger instance to write captured output to
            *args, **kwargs: Arguments passed to Rich Console
        """
        super().__init__(*args, **kwargs)
        self.debug_logger = debug_logger
        self._log_prefix = "[CONSOLE] "

    def print(self, *objects, **kwargs):
        """
        Override print method to capture output for debug logging.

        This method calls the original Rich print method for visual output,
        then captures and logs a plain text version to the debug log.
        """
        # Call original print method for visual output
        super().print(*objects, **kwargs)

        # If debug logging is enabled, capture the output
        if self.debug_logger and self.debug_logger.isEnabledFor(logging.DEBUG):
            # Capture the plain text version
            plain_text = self._render_to_plain_text(*objects, **kwargs)
            if plain_text.strip():  # Only log non-empty output
                self.debug_logger.debug(f"{self._log_prefix}{plain_text}")

    def _render_to_plain_text(self, *objects, **kwargs) -> str:
        """
        Render the objects to plain text without Rich markup.

        Args:
            *objects: Objects to render
            **kwargs: Keyword arguments from print call

        Returns:
            Plain text string without Rich formatting
        """
        # Create a string buffer to capture output
        string_buffer = io.StringIO()

        # Create a temporary console that writes to the string buffer
        temp_console = RichConsole(
            file=string_buffer,
            force_terminal=False,  # Disable terminal features
            width=self.width,
            legacy_windows=False
        )

        # Render to the temporary console
        temp_console.print(*objects, **kwargs)

        # Get the plain text content
        content = string_buffer.getvalue()

        # Strip ANSI escape codes if any remain
        content = self._strip_ansi_codes(content)

        # Clean up trailing whitespace but preserve structure
        content = content.rstrip()

        return content

    def _strip_ansi_codes(self, text: str) -> str:
        """
        Remove ANSI escape codes from text.

        Args:
            text: Text that may contain ANSI codes

        Returns:
            Text with ANSI codes removed
        """
        # ANSI escape sequence pattern
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)


def create_debug_console(debug_enabled: bool = False,
                        debug_logger: Optional[logging.Logger] = None) -> RichConsole:
    """
    Create appropriate console instance based on debug mode.

    Args:
        debug_enabled: Whether debug mode is enabled
        debug_logger: Logger instance for debug output

    Returns:
        DebugCapturingConsole if debug enabled, regular Console otherwise
    """
    if debug_enabled and debug_logger:
        return DebugCapturingConsole(debug_logger=debug_logger)
    else:
        return RichConsole()


def setup_debug_logger(log_file: str = "proxy_debug.log") -> logging.Logger:
    """
    Set up a dedicated logger for debug console output.

    Args:
        log_file: Path to debug log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("debug_console")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create file handler with append mode
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Create formatter for console output
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger
