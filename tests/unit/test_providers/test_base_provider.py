"""Tests for BaseProvider abstract class"""
import pytest
from unittest.mock import AsyncMock, Mock

from providers.base_provider import BaseProvider


class ConcreteProvider(BaseProvider):
    """Concrete implementation for testing the base class"""

    async def make_request(self, request_data, request_id):
        """Mock implementation"""
        return Mock(status_code=200)

    async def stream_response(self, request_data, request_id, tracer=None):
        """Mock implementation"""
        yield "data: test\n\n"


@pytest.mark.unit
class TestBaseProvider:
    """Test suite for BaseProvider base class"""

    def test_initialization(self):
        """Test provider initialization with base_url and api_key"""
        base_url = "https://api.example.com"
        api_key = "test-key-123"

        provider = ConcreteProvider(base_url=base_url, api_key=api_key)

        assert provider.base_url == base_url
        assert provider.api_key == api_key

    def test_abstract_methods_must_be_implemented(self):
        """Test that BaseProvider cannot be instantiated directly"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseProvider(base_url="test", api_key="test")

    @pytest.mark.asyncio
    async def test_concrete_make_request(self):
        """Test concrete implementation of make_request"""
        provider = ConcreteProvider(base_url="https://api.test.com", api_key="key123")

        response = await provider.make_request(
            request_data={"model": "test-model"},
            request_id="req_123"
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concrete_stream_response(self):
        """Test concrete implementation of stream_response"""
        provider = ConcreteProvider(base_url="https://api.test.com", api_key="key123")

        chunks = []
        async for chunk in provider.stream_response(
            request_data={"model": "test-model"},
            request_id="req_123"
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == "data: test\n\n"

    def test_provider_stores_credentials(self):
        """Test that provider properly stores credentials"""
        provider = ConcreteProvider(
            base_url="https://custom.api.com/v1",
            api_key="sk-test-key-abc123"
        )

        assert provider.base_url == "https://custom.api.com/v1"
        assert provider.api_key == "sk-test-key-abc123"
