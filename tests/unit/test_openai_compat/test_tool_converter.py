"""Tests for tool/function call conversion"""
import pytest

from openai_compat.tool_converter import (
    convert_openai_tool_calls_to_anthropic,
    convert_openai_tools_to_anthropic,
    convert_openai_functions_to_anthropic,
    convert_openai_function_call_to_anthropic
)


@pytest.mark.unit
class TestConvertOpenAIToolCallsToAnthropic:
    """Test suite for tool_calls conversion"""

    def test_convert_single_tool_call(self):
        """Test converting single tool call"""
        tool_calls = [
            {
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "San Francisco"}'
                }
            }
        ]

        result = convert_openai_tool_calls_to_anthropic(tool_calls)

        assert len(result) == 1
        assert result[0]["type"] == "tool_use"
        assert result[0]["id"] == "call_123"
        assert result[0]["name"] == "get_weather"
        assert result[0]["input"] == {"location": "San Francisco"}

    def test_convert_multiple_tool_calls(self):
        """Test converting multiple tool calls"""
        tool_calls = [
            {
                "id": "call_1",
                "function": {"name": "func1", "arguments": '{"a": 1}'}
            },
            {
                "id": "call_2",
                "function": {"name": "func2", "arguments": '{"b": 2}'}
            }
        ]

        result = convert_openai_tool_calls_to_anthropic(tool_calls)

        assert len(result) == 2
        assert result[0]["name"] == "func1"
        assert result[1]["name"] == "func2"

    def test_handle_invalid_json_arguments(self):
        """Test handling of invalid JSON in arguments"""
        tool_calls = [
            {
                "id": "call_123",
                "function": {
                    "name": "test_func",
                    "arguments": "invalid json {{"
                }
            }
        ]

        result = convert_openai_tool_calls_to_anthropic(tool_calls)

        # Should handle gracefully with empty input
        assert len(result) == 1
        assert result[0]["input"] == {}


@pytest.mark.unit
class TestConvertOpenAIToolsToAnthropic:
    """Test suite for tools definition conversion"""

    def test_convert_single_tool(self):
        """Test converting single tool definition"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                        "required": ["location"]
                    }
                }
            }
        ]

        result = convert_openai_tools_to_anthropic(tools)

        assert len(result) == 1
        assert result[0]["name"] == "get_weather"
        assert result[0]["description"] == "Get weather for a location"
        assert "input_schema" in result[0]

    def test_convert_none_returns_none(self):
        """Test that None input returns None"""
        result = convert_openai_tools_to_anthropic(None)
        assert result is None

    def test_convert_empty_list_returns_none(self):
        """Test that empty list returns None"""
        result = convert_openai_tools_to_anthropic([])
        assert result is None

    def test_convert_multiple_tools(self):
        """Test converting multiple tool definitions"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool1",
                    "description": "First tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool2",
                    "description": "Second tool",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]

        result = convert_openai_tools_to_anthropic(tools)

        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"


@pytest.mark.unit
class TestConvertOpenAIFunctionsToAnthropic:
    """Test suite for legacy functions conversion"""

    def test_convert_single_function(self):
        """Test converting single function definition"""
        functions = [
            {
                "name": "calculate",
                "description": "Calculate something",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"}
                    }
                }
            }
        ]

        result = convert_openai_functions_to_anthropic(functions)

        assert len(result) == 1
        assert result[0]["name"] == "calculate"
        assert result[0]["description"] == "Calculate something"

    def test_convert_none_returns_none(self):
        """Test that None input returns None"""
        result = convert_openai_functions_to_anthropic(None)
        assert result is None

    def test_convert_empty_list_returns_none(self):
        """Test that empty list returns None"""
        result = convert_openai_functions_to_anthropic([])
        assert result is None


@pytest.mark.unit
class TestConvertOpenAIFunctionCallToAnthropic:
    """Test suite for function_call conversion"""

    def test_convert_function_call(self):
        """Test converting function_call to tool_use"""
        function_call = {
            "name": "get_weather",
            "arguments": '{"location": "NYC"}'
        }

        result = convert_openai_function_call_to_anthropic(function_call)

        assert len(result) == 1
        assert result[0]["type"] == "tool_use"
        assert result[0]["name"] == "get_weather"
        assert result[0]["input"] == {"location": "NYC"}
