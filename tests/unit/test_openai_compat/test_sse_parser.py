"""Tests for SSE (Server-Sent Events) parser"""
import pytest

from openai_compat.sse_parser import SSEParser


@pytest.mark.unit
class TestSSEParser:
    """Test suite for SSE parser"""

    def test_parse_simple_event(self):
        """Test parsing a simple SSE event"""
        parser = SSEParser()
        events = parser.feed("data: hello\n\n")

        assert len(events) == 1
        assert events[0].event is None
        assert events[0].data == "hello"

    def test_parse_event_with_type(self):
        """Test parsing event with event type"""
        parser = SSEParser()
        events = parser.feed("event: message\ndata: test\n\n")

        assert len(events) == 1
        assert events[0].event == "message"
        assert events[0].data == "test"

    def test_parse_multiline_data(self):
        """Test parsing event with multiple data lines"""
        parser = SSEParser()
        events = parser.feed("data: line1\ndata: line2\ndata: line3\n\n")

        assert len(events) == 1
        assert events[0].data == "line1\nline2\nline3"

    def test_parse_multiple_events(self):
        """Test parsing multiple events in one feed"""
        parser = SSEParser()
        events = parser.feed("data: first\n\ndata: second\n\n")

        assert len(events) == 2
        assert events[0].data == "first"
        assert events[1].data == "second"

    def test_parse_incremental_chunks(self):
        """Test parsing events across multiple feed calls"""
        parser = SSEParser()

        events1 = parser.feed("data: hel")
        assert len(events1) == 0  # Incomplete

        events2 = parser.feed("lo\n\n")
        assert len(events2) == 1
        assert events2[0].data == "hello"

    def test_parse_comment_lines(self):
        """Test that comment lines are ignored"""
        parser = SSEParser()
        events = parser.feed(": this is a comment\ndata: actual data\n\n")

        assert len(events) == 1
        assert events[0].data == "actual data"

    def test_parse_windows_line_endings(self):
        """Test parsing with Windows-style CRLF line endings"""
        parser = SSEParser()
        events = parser.feed("data: test\r\n\r\n")

        assert len(events) == 1
        assert events[0].data == "test"

    def test_parse_data_with_leading_space(self):
        """Test that leading space after colon is trimmed"""
        parser = SSEParser()
        events = parser.feed("data:  spaced\n\n")

        assert len(events) == 1
        assert events[0].data == " spaced"  # Only first space trimmed

    def test_parse_empty_data(self):
        """Test parsing event with empty data"""
        parser = SSEParser()
        events = parser.feed("data:\n\n")

        assert len(events) == 1
        assert events[0].data == ""

    def test_flush_incomplete_event(self):
        """Test flushing incomplete buffered event"""
        parser = SSEParser()
        parser.feed("event: test\ndata: incomplete")

        events = parser.flush()
        # Flush returns accumulated data
        assert len(events) >= 1
        # Check that data was flushed
        assert any("incomplete" in e.data for e in events)

    def test_flush_with_event_type(self):
        """Test flushing event with type"""
        parser = SSEParser()
        parser.feed("event: error\ndata: failed")

        events = parser.flush()
        # Flush returns accumulated data
        assert len(events) >= 1
        # Check that data was flushed
        assert any("failed" in e.data for e in events)

    def test_flush_clears_buffer(self):
        """Test that flush clears internal state"""
        parser = SSEParser()
        parser.feed("data: test")
        parser.flush()

        # Feed new data - should not include previous
        events = parser.feed("data: new\n\n")
        assert len(events) == 1
        assert events[0].data == "new"

    def test_empty_feed(self):
        """Test feeding empty string"""
        parser = SSEParser()
        events = parser.feed("")

        assert len(events) == 0

    def test_multiple_blank_lines(self):
        """Test multiple blank lines between events"""
        parser = SSEParser()
        events = parser.feed("data: first\n\n\n\ndata: second\n\n")

        # Multiple blank lines should not create extra events
        assert len(events) == 2
        assert events[0].data == "first"
        assert events[1].data == "second"

    def test_event_without_data(self):
        """Test event type without data"""
        parser = SSEParser()
        events = parser.feed("event: ping\n\n")

        assert len(events) == 1
        assert events[0].event == "ping"
        assert events[0].data == ""

    def test_complex_sse_stream(self):
        """Test parsing complex SSE stream"""
        parser = SSEParser()
        stream = """event: start
data: {"type":"start"}

data: {"delta":"Hello"}
data: {"delta":" World"}

event: end
data: {"type":"end"}

"""
        events = parser.feed(stream)

        assert len(events) == 3
        assert events[0].event == "start"
        assert events[1].event is None
        assert events[1].data == '{"delta":"Hello"}\n{"delta":" World"}'
        assert events[2].event == "end"
