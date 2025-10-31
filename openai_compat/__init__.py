"""
OpenAI to Anthropic API compatibility layer.
Converts between OpenAI chat completion format and Anthropic messages format.
"""

# Public API exports
from .message_converter import convert_openai_messages_to_anthropic
from .content_converter import (
    convert_openai_content_to_anthropic,
    convert_anthropic_content_to_openai
)
from .tool_converter import (
    convert_openai_tool_calls_to_anthropic,
    convert_openai_tools_to_anthropic,
    convert_openai_functions_to_anthropic
)
from .request_converter import convert_openai_request_to_anthropic
from .response_converter import (
    convert_anthropic_response_to_openai,
    map_stop_reason_to_finish_reason
)
from .stream_converter import convert_anthropic_stream_to_openai

__all__ = [
    # Message conversion
    "convert_openai_messages_to_anthropic",

    # Content conversion
    "convert_openai_content_to_anthropic",
    "convert_anthropic_content_to_openai",

    # Tool conversion
    "convert_openai_tool_calls_to_anthropic",
    "convert_openai_tools_to_anthropic",
    "convert_openai_functions_to_anthropic",

    # Request/Response conversion
    "convert_openai_request_to_anthropic",
    "convert_anthropic_response_to_openai",
    "map_stop_reason_to_finish_reason",

    # Stream conversion
    "convert_anthropic_stream_to_openai",
]
