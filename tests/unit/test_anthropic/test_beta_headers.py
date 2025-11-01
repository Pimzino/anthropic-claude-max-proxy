"""Tests for beta header management"""
import pytest

from anthropic.beta_headers import build_beta_headers


@pytest.mark.unit
class TestBuildBetaHeaders:
    """Test suite for beta header construction"""

    def test_always_includes_oauth_beta(self):
        """Test that oauth beta is always included"""
        request = {}
        result = build_beta_headers(request)

        assert "oauth-2025-04-20" in result

    def test_includes_thinking_beta_when_enabled(self):
        """Test thinking beta is included when thinking is enabled"""
        request = {
            "thinking": {"type": "enabled", "budget_tokens": 16000}
        }
        result = build_beta_headers(request)

        assert "oauth-2025-04-20" in result
        assert "interleaved-thinking-2025-05-14" in result

    def test_includes_1m_context_for_streaming(self):
        """Test 1M context beta for streaming requests"""
        request = {"_use_1m_context": True}
        result = build_beta_headers(request, for_streaming=True)

        assert "context-1m-2025-08-07" in result

    def test_no_1m_context_for_non_streaming(self):
        """Test 1M context not added for non-streaming"""
        request = {"_use_1m_context": True}
        result = build_beta_headers(request, for_streaming=False)

        assert "context-1m-2025-08-07" not in result

    def test_includes_tools_beta_for_non_streaming(self):
        """Test tools beta for non-streaming with tools"""
        request = {
            "tools": [{"name": "get_weather", "description": "Get weather"}]
        }
        result = build_beta_headers(request, for_streaming=False)

        assert "fine-grained-tool-streaming-2025-05-14" in result

    def test_no_tools_beta_for_streaming(self):
        """Test tools beta not added for streaming"""
        request = {
            "tools": [{"name": "get_weather"}]
        }
        result = build_beta_headers(request, for_streaming=True)

        assert "fine-grained-tool-streaming-2025-05-14" not in result

    def test_multiple_betas_combined(self):
        """Test multiple beta features combined"""
        request = {
            "thinking": {"type": "enabled"},
            "_use_1m_context": True
        }
        result = build_beta_headers(request, for_streaming=True)

        assert "oauth-2025-04-20" in result
        assert "interleaved-thinking-2025-05-14" in result
        assert "context-1m-2025-08-07" in result
