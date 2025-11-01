"""Tests for thinking cache"""
import pytest
import time

from utils.thinking_cache import _ThinkingCache, THINKING_CACHE


@pytest.mark.unit
class TestThinkingCache:
    """Test suite for ThinkingCache"""

    def test_put_and_get(self):
        """Test storing and retrieving thinking blocks"""
        cache = _ThinkingCache()
        thinking_block = {"type": "thinking", "thinking": "Let me think...", "signature": "sig123"}

        cache.put("tool_1", thinking_block)
        result = cache.get("tool_1")

        assert result == thinking_block

    def test_get_nonexistent_returns_none(self):
        """Test that getting non-existent key returns None"""
        cache = _ThinkingCache()

        result = cache.get("nonexistent")

        assert result is None

    def test_put_requires_signature(self):
        """Test that put requires signature field"""
        cache = _ThinkingCache()

        # Missing signature
        cache.put("tool_1", {"thinking": "Test"})
        assert cache.get("tool_1") is None

        # Empty signature
        cache.put("tool_2", {"thinking": "Test", "signature": ""})
        assert cache.get("tool_2") is None

        # Valid signature
        cache.put("tool_3", {"thinking": "Test", "signature": "sig123"})
        assert cache.get("tool_3") is not None

    def test_overwrite_existing(self):
        """Test that putting with same key overwrites"""
        cache = _ThinkingCache()

        cache.put("tool_1", {"thinking": "First", "signature": "sig1"})
        cache.put("tool_1", {"thinking": "Second", "signature": "sig2"})

        result = cache.get("tool_1")
        assert result["thinking"] == "Second"

    def test_multiple_keys(self):
        """Test storing multiple thinking blocks"""
        cache = _ThinkingCache()

        cache.put("tool_1", {"thinking": "First", "signature": "sig1"})
        cache.put("tool_2", {"thinking": "Second", "signature": "sig2"})
        cache.put("tool_3", {"thinking": "Third", "signature": "sig3"})

        assert cache.get("tool_1")["thinking"] == "First"
        assert cache.get("tool_2")["thinking"] == "Second"
        assert cache.get("tool_3")["thinking"] == "Third"

    def test_ttl_expiration(self):
        """Test that entries expire after TTL"""
        cache = _ThinkingCache(ttl_seconds=1)

        cache.put("tool_1", {"thinking": "Test", "signature": "sig"})
        assert cache.get("tool_1") is not None

        # Wait for expiration
        time.sleep(1.5)

        assert cache.get("tool_1") is None

    def test_max_entries_eviction(self):
        """Test that oldest entries are evicted when max is reached"""
        cache = _ThinkingCache(max_entries=3)

        cache.put("tool_1", {"thinking": "First", "signature": "sig1"})
        cache.put("tool_2", {"thinking": "Second", "signature": "sig2"})
        cache.put("tool_3", {"thinking": "Third", "signature": "sig3"})
        cache.put("tool_4", {"thinking": "Fourth", "signature": "sig4"})

        # tool_1 should be evicted
        assert cache.get("tool_1") is None
        assert cache.get("tool_2") is not None
        assert cache.get("tool_3") is not None
        assert cache.get("tool_4") is not None

    def test_global_cache_instance(self):
        """Test that THINKING_CACHE is a global instance"""
        # Should be a _ThinkingCache instance
        assert isinstance(THINKING_CACHE, _ThinkingCache)

        # Test it works
        THINKING_CACHE.put("test", {"thinking": "value", "signature": "sig"})
        assert THINKING_CACHE.get("test")["thinking"] == "value"

        # Clean up by letting it expire naturally or just test it exists
        THINKING_CACHE._data.clear()
