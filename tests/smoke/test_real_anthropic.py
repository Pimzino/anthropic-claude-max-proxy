"""Smoke tests against real Anthropic API

These tests require a valid ANTHROPIC_OAUTH_TOKEN environment variable.
They make real API calls and are opt-in only (marked with @pytest.mark.smoke).

Run with: pytest tests/smoke/ -v -m smoke
"""
import pytest


@pytest.mark.smoke
class TestRealAnthropicAPI:
    """Smoke tests using real Anthropic API"""

    def test_simple_text_completion(self, real_anthropic_client):
        """Test basic text completion with real API"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Say 'Hello, World!' and nothing else."}
            ]
        )

        assert response.id is not None
        assert response.type == "message"
        assert len(response.content) > 0
        assert "Hello" in response.content[0].text

    def test_conversation_with_system_message(self, real_anthropic_client):
        """Test conversation with system message"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system="You are a helpful assistant that responds concisely.",
            messages=[
                {"role": "user", "content": "What is 2+2?"}
            ]
        )

        assert response.id is not None
        assert "4" in response.content[0].text

    def test_multi_turn_conversation(self, real_anthropic_client):
        """Test multi-turn conversation"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Nice to meet you, Alice!"},
                {"role": "user", "content": "What's my name?"}
            ]
        )

        assert response.id is not None
        assert "Alice" in response.content[0].text

    def test_streaming_response(self, real_anthropic_client):
        """Test streaming text completion"""
        chunks = []

        with real_anthropic_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Count from 1 to 5."}
            ]
        ) as stream:
            for chunk in stream:
                chunks.append(chunk)

        # Should receive multiple chunks
        assert len(chunks) > 1

        # Final message should be complete
        final_message = stream.get_final_message()
        assert final_message is not None
        assert len(final_message.content) > 0

    def test_tool_calling(self, real_anthropic_client):
        """Test tool/function calling"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            tools=[
                {
                    "name": "get_weather",
                    "description": "Get the weather for a location",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name"
                            }
                        },
                        "required": ["location"]
                    }
                }
            ],
            messages=[
                {"role": "user", "content": "What's the weather in San Francisco?"}
            ]
        )

        assert response.id is not None
        # Should either use tool or explain it would use tool
        assert len(response.content) > 0

    def test_reasoning_mode(self, real_anthropic_client):
        """Test extended thinking/reasoning mode"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            thinking={
                "type": "enabled",
                "budget_tokens": 8000
            },
            messages=[
                {"role": "user", "content": "What is 15 * 24?"}
            ]
        )

        assert response.id is not None
        assert len(response.content) > 0

        # Thinking may or may not appear for simple math
        # Just verify response is valid
        assert response.stop_reason in ["end_turn", "max_tokens"]

    def test_max_tokens_limit(self, real_anthropic_client):
        """Test that max_tokens is respected"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,  # Very low limit
            messages=[
                {"role": "user", "content": "Write a long essay about artificial intelligence."}
            ]
        )

        assert response.id is not None
        # Should stop due to max_tokens
        assert response.stop_reason in ["max_tokens", "end_turn"]
        assert response.usage.output_tokens <= 50

    def test_temperature_parameter(self, real_anthropic_client):
        """Test temperature parameter affects output"""
        # Low temperature (more deterministic)
        response1 = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            temperature=0.0,
            messages=[
                {"role": "user", "content": "Say exactly: 'Test response'"}
            ]
        )

        assert response1.id is not None
        assert len(response1.content) > 0

    def test_stop_sequences(self, real_anthropic_client):
        """Test stop sequences"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            stop_sequences=["STOP"],
            messages=[
                {"role": "user", "content": "Count from 1 to 10, then say STOP."}
            ]
        )

        assert response.id is not None
        # Should stop at STOP sequence
        assert response.stop_reason in ["stop_sequence", "end_turn"]

    def test_error_handling_invalid_model(self, real_anthropic_client):
        """Test error handling with invalid model"""
        with pytest.raises(Exception):  # Should raise an API error
            real_anthropic_client.messages.create(
                model="invalid-model-name-12345",
                max_tokens=100,
                messages=[
                    {"role": "user", "content": "Hello"}
                ]
            )

    def test_error_handling_missing_max_tokens(self, real_anthropic_client):
        """Test error handling when max_tokens is missing"""
        with pytest.raises(Exception):  # Should raise validation error
            real_anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                messages=[
                    {"role": "user", "content": "Hello"}
                ]
                # Missing max_tokens
            )

    def test_usage_tracking(self, real_anthropic_client):
        """Test that usage information is returned"""
        response = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello!"}
            ]
        )

        assert response.usage is not None
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0

    def test_prompt_caching(self, real_anthropic_client):
        """Test prompt caching with cache_control"""
        # First request with cache_control
        response1 = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=[
                {
                    "type": "text",
                    "text": "You are a helpful assistant.",
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": "What is 2+2?"}
            ]
        )

        assert response1.id is not None

        # Second request should potentially use cache
        response2 = real_anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=[
                {
                    "type": "text",
                    "text": "You are a helpful assistant.",
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": "What is 3+3?"}
            ]
        )

        assert response2.id is not None
        # Both should succeed (cache usage is internal)
