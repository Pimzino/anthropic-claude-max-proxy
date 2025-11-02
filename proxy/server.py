"""
ProxyServer class for CLI control of the FastAPI application.
"""
import logging
import uvicorn

from settings import PORT, LOG_LEVEL, BIND_ADDRESS, STREAM_TRACE_ENABLED, STREAM_TRACE_DIR
from .app import app

logger = logging.getLogger(__name__)


class ProxyServer:
    """Proxy server wrapper for CLI control"""

    def __init__(self, debug: bool = False, debug_sse: bool = False, bind_address: str = None):
        self.server = None
        self.config = None
        self.debug = debug
        self.debug_sse = debug_sse
        self.bind_address = bind_address or BIND_ADDRESS

        # Configure debug logging if enabled
        if debug:
            self._setup_debug_logging()

    def _setup_debug_logging(self):
        """Setup debug logging for the proxy server"""
        import os
        from utils.debug_console import setup_debug_logger

        # Get root logger and configure it for debug
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create file handler for debug log with append mode
        log_file = os.path.abspath('proxy_debug.log')
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')  # 'a' to append
        file_handler.setLevel(logging.DEBUG)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Set up debug console logger for Rich console output capture
        self.debug_console_logger = setup_debug_logger(log_file)

        # Store debug info globally for CLI access
        import __main__
        __main__._proxy_debug_enabled = True
        __main__._proxy_debug_logger = self.debug_console_logger

        logger.info(f"Debug logging enabled - appending to {log_file}")
        logger.info("Rich console output will be captured to debug log")

    def run(self):
        """Run the proxy server (blocking)"""
        logger.info(f"Starting LLMux on http://{self.bind_address}:{PORT}")
        logger.info("Available endpoints: /v1/messages (Anthropic), /v1/chat/completions (OpenAI)")
        if STREAM_TRACE_ENABLED:
            logger.warning(
                "Stream tracing is ENABLED - raw SSE chunks will be written inside '%s'",
                STREAM_TRACE_DIR,
            )
        self.config = uvicorn.Config(
            app,
            host=self.bind_address,
            port=PORT,
            log_level=LOG_LEVEL,
            access_log=False  # Reduce noise in CLI
        )
        self.server = uvicorn.Server(self.config)
        self.server.run()

    def stop(self):
        """Stop the proxy server"""
        if self.server:
            self.server.should_exit = True



