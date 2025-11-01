"""Tests for Anthropic to OpenAI stream conversion"""
import json
import pytest
from unittest.mock import Mock, patch

from openai_compat.stream_converter import convert_anthropic_stream_to_openai


async def async_iter(items):
    """Helper to create async iterator from list"""
    for item in items:
        yield item


@pytest.mark.unit
class TestConvertAnthropicStreamToOpenAI:
    """Test suite for stream conversion"""

    @pytest.mark.asyncio
    async def test_convert_simple_text_stream(self):
        """Test converting simple text streaming response"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_01","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Should have: initial, "Hello", " world", finish_reason, [DONE]
        assert len(chunks) >= 4

        # Parse chunks to verify structure
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                data = json.loads(chunk.replace("data: ", "").strip())
                openai_chunks.append(data)

        # Verify initial chunk with role
        assert openai_chunks[0]["choices"][0]["delta"]["role"] == "assistant"

        # Verify text deltas
        text_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("content")]
        assert len(text_chunks) == 2
        assert text_chunks[0]["choices"][0]["delta"]["content"] == "Hello"
        assert text_chunks[1]["choices"][0]["delta"]["content"] == " world"

        # Verify finish_reason
        finish_chunks = [c for c in openai_chunks if c["choices"][0]["finish_reason"]]
        assert len(finish_chunks) == 1
        assert finish_chunks[0]["choices"][0]["finish_reason"] == "stop"

        # Verify [DONE] marker
        assert chunks[-1] == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_convert_stream_with_tool_calls(self):
        """Test converting stream with tool calls"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_02","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_1","name":"get_weather"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"location\\""}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":":\\"NYC\\"}"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse OpenAI chunks
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                data = json.loads(chunk.replace("data: ", "").strip())
                openai_chunks.append(data)

        # Verify tool call chunks exist
        tool_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("tool_calls")]
        assert len(tool_chunks) >= 1

        # Verify first tool chunk has id and name
        first_tool = tool_chunks[0]["choices"][0]["delta"]["tool_calls"][0]
        assert first_tool["id"] == "tool_1"
        assert first_tool["function"]["name"] == "get_weather"
        assert first_tool["type"] == "function"

        # Verify finish reason is tool_calls
        finish_chunks = [c for c in openai_chunks if c["choices"][0]["finish_reason"]]
        assert finish_chunks[0]["choices"][0]["finish_reason"] == "tool_calls"

    @pytest.mark.asyncio
    async def test_convert_stream_with_thinking(self):
        """Test converting stream with thinking/reasoning content"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_03","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"thinking"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"Let me think"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"..."}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":1,"content_block":{"type":"text","text":""}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"Answer"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":1}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse OpenAI chunks
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                data = json.loads(chunk.replace("data: ", "").strip())
                openai_chunks.append(data)

        # Verify reasoning content chunks
        reasoning_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("reasoning_content")]
        assert len(reasoning_chunks) >= 1

        # Verify thinking text is present
        reasoning_text = "".join([c["choices"][0]["delta"]["reasoning_content"] for c in reasoning_chunks])
        assert "Let me think" in reasoning_text

        # Verify regular content is also present
        content_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("content")]
        assert len(content_chunks) >= 1

    @pytest.mark.asyncio
    async def test_convert_stream_ping_events(self):
        """Test that ping events are filtered out"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_04","role":"assistant","content":[]}}\n\n',
            'event: ping\ndata: {"type":"ping"}\n\n',  # Should be ignored
            'data: {"type":"ping"}\n\n',  # Should be ignored
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            'event: ping\ndata: {}\n\n',  # Should be ignored
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse OpenAI chunks
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                data = json.loads(chunk.replace("data: ", "").strip())
                openai_chunks.append(data)

        # Verify content was processed correctly (pings didn't interfere)
        content_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("content")]
        assert len(content_chunks) == 1
        assert content_chunks[0]["choices"][0]["delta"]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_convert_stream_error_event(self):
        """Test handling of error events in stream"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_05","role":"assistant","content":[]}}\n\n',
            'event: error\ndata: {"type":"error","error":{"type":"api_error","message":"Rate limit exceeded"}}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse error chunk
        error_chunks = [c for c in chunks if c.startswith("data: ") and "error" in c]
        assert len(error_chunks) >= 1

        error_data = json.loads(error_chunks[0].replace("data: ", "").strip())
        assert "error" in error_data
        assert "message" in error_data["error"]
        assert "Rate limit exceeded" in error_data["error"]["message"]

    @pytest.mark.asyncio
    async def test_convert_stream_error_string_format(self):
        """Test handling of error in string format"""
        anthropic_chunks = [
            'event: error\ndata: {"type":"error","error":"Simple error message"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse error chunk
        error_chunks = [c for c in chunks if c.startswith("data: ") and "error" in c]
        assert len(error_chunks) >= 1

        error_data = json.loads(error_chunks[0].replace("data: ", "").strip())
        assert "error" in error_data

    @pytest.mark.asyncio
    async def test_convert_stream_multiple_tool_calls(self):
        """Test converting stream with multiple tool calls"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_06","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"tool_1","name":"search"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"q\\":\\"test\\"}"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"tool_2","name":"calculate"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\\"expr\\":\\"2+2\\"}"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":1}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse OpenAI chunks
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                data = json.loads(chunk.replace("data: ", "").strip())
                openai_chunks.append(data)

        # Collect all tool calls
        all_tool_calls = []
        for chunk in openai_chunks:
            if chunk["choices"][0]["delta"].get("tool_calls"):
                all_tool_calls.extend(chunk["choices"][0]["delta"]["tool_calls"])

        # Verify we have both tools with different indices
        tool_indices = {tc["index"] for tc in all_tool_calls}
        assert 0 in tool_indices
        assert 1 in tool_indices

        # Verify tool names
        tool_names = {tc["function"]["name"] for tc in all_tool_calls if tc.get("function", {}).get("name")}
        assert "search" in tool_names
        assert "calculate" in tool_names

    @pytest.mark.asyncio
    async def test_convert_stream_with_tracer(self):
        """Test stream conversion with tracer enabled"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_07","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Test"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        mock_tracer = Mock()
        mock_tracer.log_note = Mock()
        mock_tracer.log_converted_chunk = Mock()

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123",
            tracer=mock_tracer
        ):
            chunks.append(chunk)

        # Verify tracer was called
        assert mock_tracer.log_note.call_count > 0
        assert mock_tracer.log_converted_chunk.call_count > 0

    @pytest.mark.asyncio
    async def test_convert_stream_invalid_json(self):
        """Test handling of invalid JSON in stream"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_08","role":"assistant","content":[]}}\n\n',
            'event: content_block_delta\ndata: {invalid json}\n\n',  # Invalid JSON
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Valid"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Should still process valid chunks
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                try:
                    data = json.loads(chunk.replace("data: ", "").strip())
                    openai_chunks.append(data)
                except json.JSONDecodeError:
                    pass

        # Verify valid content was processed
        content_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("content")]
        assert len(content_chunks) >= 1

    @pytest.mark.asyncio
    async def test_convert_stream_completion_id_format(self):
        """Test that completion IDs are properly formatted"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_09","role":"assistant","content":[]}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse first chunk
        first_data = json.loads(chunks[0].replace("data: ", "").strip())

        # Verify completion ID format
        assert first_data["id"].startswith("chatcmpl-")
        assert first_data["object"] == "chat.completion.chunk"
        assert first_data["model"] == "claude-3-opus-20240229"

    @pytest.mark.asyncio
    async def test_convert_stream_exception_handling(self):
        """Test exception handling in stream conversion"""
        async def failing_stream():
            yield 'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_10","role":"assistant","content":[]}}\n\n'
            raise ValueError("Stream error")

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=failing_stream(),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Should yield error chunk
        error_chunks = [c for c in chunks if "error" in c and c.startswith("data: ")]
        assert len(error_chunks) >= 1

        # Verify error structure
        error_data = json.loads(error_chunks[0].replace("data: ", "").strip())
        assert "error" in error_data
        assert error_data["error"]["type"] == "conversion_error"

    @pytest.mark.asyncio
    async def test_convert_stream_redacted_thinking(self):
        """Test conversion of redacted_thinking blocks"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_11","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"redacted_thinking"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"redacted_thinking_delta","text":"[redacted]"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Parse OpenAI chunks
        openai_chunks = []
        for chunk in chunks:
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                data = json.loads(chunk.replace("data: ", "").strip())
                openai_chunks.append(data)

        # Verify reasoning content was emitted
        reasoning_chunks = [c for c in openai_chunks if c["choices"][0]["delta"].get("reasoning_content")]
        assert len(reasoning_chunks) >= 1

    @pytest.mark.asyncio
    async def test_convert_stream_signed_thinking_cache(self):
        """Test that signed thinking blocks are cached with tool_use IDs"""
        anthropic_chunks = [
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_12","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","signature":"sig123"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"Analysis"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"tool_abc","name":"test"}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{}"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":1}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"tool_use"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        with patch('openai_compat.stream_converter.THINKING_CACHE') as mock_cache:
            mock_cache.put = Mock()

            chunks = []
            async for chunk in convert_anthropic_stream_to_openai(
                anthropic_stream=async_iter(anthropic_chunks),
                model="claude-3-opus-20240229",
                request_id="req_123"
            ):
                chunks.append(chunk)

            # Verify cache was called with tool_use ID
            assert mock_cache.put.called
            call_args = mock_cache.put.call_args_list
            # Should have been called with tool_abc
            tool_ids = [args[0][0] for args in call_args]
            assert "tool_abc" in tool_ids

    @pytest.mark.asyncio
    async def test_convert_stream_empty_data(self):
        """Test handling of events with empty data"""
        anthropic_chunks = [
            'event: message_start\ndata: \n\n',  # Empty data
            'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_13","role":"assistant","content":[]}}\n\n',
            'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Test"}}\n\n',
            'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

        chunks = []
        async for chunk in convert_anthropic_stream_to_openai(
            anthropic_stream=async_iter(anthropic_chunks),
            model="claude-3-opus-20240229",
            request_id="req_123"
        ):
            chunks.append(chunk)

        # Should still process successfully
        assert len(chunks) > 0
        assert chunks[-1] == "data: [DONE]\n\n"
