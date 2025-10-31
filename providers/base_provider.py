"""
Base provider interface for custom model providers.
Defines the contract that all provider implementations must follow.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncIterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from stream_debug import StreamTracer


class BaseProvider(ABC):
    """Abstract base class for custom model providers"""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize provider with endpoint and credentials

        Args:
            base_url: The provider's base URL
            api_key: The API key for authentication
        """
        self.base_url = base_url
        self.api_key = api_key

    @abstractmethod
    async def make_request(
        self,
        request_data: Dict[str, Any],
        request_id: str
    ):
        """Make a non-streaming request to the provider

        Args:
            request_data: The request body in provider's format
            request_id: Request ID for logging

        Returns:
            The HTTP response from the provider
        """
        pass

    @abstractmethod
    async def stream_response(
        self,
        request_data: Dict[str, Any],
        request_id: str,
        tracer: Optional["StreamTracer"] = None,
    ) -> AsyncIterator[str]:
        """Stream response from the provider

        Args:
            request_data: The request body in provider's format
            request_id: Request ID for logging
            tracer: Optional stream tracer for debugging

        Yields:
            SSE chunks from the provider
        """
        pass
