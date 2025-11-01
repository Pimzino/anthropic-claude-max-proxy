"""Tests for content conversion"""
import pytest

from openai_compat.content_converter import (
    convert_openai_content_to_anthropic,
    convert_anthropic_content_to_openai
)


@pytest.mark.unit
class TestConvertOpenAIContentToAnthropic:
    """Test suite for OpenAI to Anthropic content conversion"""

    def test_convert_text_content(self):
        """Test converting simple text content"""
        content = [{"type": "text", "text": "Hello world"}]

        result = convert_openai_content_to_anthropic(content)

        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello world"

    def test_convert_image_url(self):
        """Test converting image URL content"""
        content = [
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]

        result = convert_openai_content_to_anthropic(content)

        assert len(result) == 1
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "url"
        assert result[0]["source"]["url"] == "https://example.com/image.jpg"

    def test_convert_image_base64(self):
        """Test converting base64 image content"""
        content = [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,iVBORw0KG"}
            }
        ]

        result = convert_openai_content_to_anthropic(content)

        assert len(result) == 1
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "base64"
        assert result[0]["source"]["media_type"] == "image/png"

    def test_convert_mixed_content(self):
        """Test converting mixed text and image content"""
        content = [
            {"type": "text", "text": "Check this out:"},
            {"type": "image_url", "image_url": {"url": "https://example.com/pic.jpg"}}
        ]

        result = convert_openai_content_to_anthropic(content)

        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "image"


@pytest.mark.unit
class TestConvertAnthropicContentToOpenAI:
    """Test suite for Anthropic to OpenAI content conversion"""

    def test_convert_text_content(self):
        """Test converting text content"""
        content = [{"type": "text", "text": "Hello"}]

        result = convert_anthropic_content_to_openai(content)

        # Returns tuple: (text, tool_calls, reasoning_content, thinking_blocks)
        text, tool_calls, reasoning, thinking = result
        assert text == "Hello"
        assert tool_calls == []
        assert reasoning is None or reasoning == ""
        assert thinking == []

    def test_convert_with_thinking_block(self):
        """Test converting content with thinking block"""
        content = [
            {"type": "thinking", "thinking": "Let me think...", "signature": "sig123"},
            {"type": "text", "text": "Answer"}
        ]

        text, tool_calls, reasoning, thinking = convert_anthropic_content_to_openai(content)

        assert "Answer" in text
        assert "Let me think..." in reasoning
        assert len(thinking) == 1

    def test_convert_tool_use(self):
        """Test converting tool_use blocks"""
        content = [
            {
                "type": "tool_use",
                "id": "tool_123",
                "name": "get_weather",
                "input": {"location": "SF"}
            }
        ]

        text, tool_calls, reasoning, thinking = convert_anthropic_content_to_openai(content)

        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "tool_123"
        assert tool_calls[0]["function"]["name"] == "get_weather"

    def test_convert_multiple_text_blocks(self):
        """Test converting multiple text blocks"""
        content = [
            {"type": "text", "text": "First"},
            {"type": "text", "text": "Second"}
        ]

        text, tool_calls, reasoning, thinking = convert_anthropic_content_to_openai(content)

        assert "First" in text
        assert "Second" in text

    def test_convert_empty_content(self):
        """Test converting empty content"""
        content = []

        result = convert_anthropic_content_to_openai(content)

        text, tool_calls, reasoning, thinking = result
        assert text == "" or text is None
        assert tool_calls == []
