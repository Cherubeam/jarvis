"""
Unit tests for llm_client module.

Tests LLMClient, TokenUsage, and StreamingResponse functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Try new import path first, fall back to old for backward compatibility
try:
    from packages.core.llm_client import TokenUsage, StreamingResponse, LLMClient
except ImportError:
    from llm_client import TokenUsage, StreamingResponse, LLMClient


@pytest.mark.unit
class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_token_usage_init_defaults(self):
        """Test that TokenUsage initializes with default zero values."""
        usage = TokenUsage()

        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_token_usage_with_values(self):
        """Test TokenUsage with specific values."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )

        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


@pytest.mark.unit
class TestLLMClient:
    """Tests for LLMClient class."""

    def test_llm_client_init_openrouter(self):
        """Test that OpenRouter model names get proper prefix."""
        client = LLMClient(
            api_key="test-key",
            default_model="anthropic/claude-sonnet-4.5",
            provider="openrouter"
        )

        assert client.api_key == "test-key"
        assert client.provider == "openrouter"
        assert client.default_model == "openrouter/anthropic/claude-sonnet-4.5"

    def test_llm_client_init_openrouter_already_prefixed(self):
        """Test that OpenRouter prefix is not duplicated."""
        client = LLMClient(
            api_key="test-key",
            default_model="openrouter/anthropic/claude-sonnet-4.5",
            provider="openrouter"
        )

        # Should not have double prefix
        assert client.default_model == "openrouter/anthropic/claude-sonnet-4.5"
        assert client.default_model.count("openrouter/") == 1

    def test_llm_client_init_other_provider(self):
        """Test that other providers don't get openrouter prefix."""
        client = LLMClient(
            api_key="test-key",
            default_model="claude-sonnet-4.5",
            provider="anthropic"
        )

        assert client.provider == "anthropic"
        assert client.default_model == "claude-sonnet-4.5"
        assert not client.default_model.startswith("openrouter/")

    def test_chat_stream_returns_streaming_response(self):
        """Test that chat_stream returns a StreamingResponse object."""
        client = LLMClient(
            api_key="test-key",
            default_model="test-model",
            provider="test"
        )

        messages = [{"role": "user", "content": "Hello"}]

        with patch('litellm.completion') as mock_completion:
            # Create a mock streaming response
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = "Hi"

            mock_stream = [mock_chunk]
            mock_stream_obj = Mock()
            mock_stream_obj.__iter__ = Mock(return_value=iter(mock_stream))
            mock_stream_obj.usage = Mock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )

            mock_completion.return_value = mock_stream_obj

            result = client.chat_stream(messages)

            assert isinstance(result, StreamingResponse)

    def test_chat_stream_yields_chunks(self):
        """Test that chat_stream yields text chunks correctly."""
        client = LLMClient(
            api_key="test-key",
            default_model="test-model",
            provider="test"
        )

        messages = [{"role": "user", "content": "Hello"}]

        with patch('litellm.completion') as mock_completion:
            # Create multiple mock chunks
            chunks_data = ["Hello", " ", "world", "!"]
            mock_chunks = []

            for content in chunks_data:
                mock_chunk = Mock()
                mock_chunk.choices = [Mock()]
                mock_chunk.choices[0].delta = Mock()
                mock_chunk.choices[0].delta.content = content
                mock_chunks.append(mock_chunk)

            # Create mock stream object
            mock_stream_obj = Mock()
            mock_stream_obj.__iter__ = Mock(return_value=iter(mock_chunks))
            mock_stream_obj.usage = Mock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )

            mock_completion.return_value = mock_stream_obj

            stream = client.chat_stream(messages)
            collected = list(stream)

            assert collected == ["Hello", " ", "world", "!"]

    def test_chat_stream_usage_after_completion(self):
        """Test that usage is available after stream completion."""
        client = LLMClient(
            api_key="test-key",
            default_model="test-model",
            provider="test"
        )

        messages = [{"role": "user", "content": "Hello"}]

        with patch('litellm.completion') as mock_completion:
            # Create content chunk
            mock_content_chunk = Mock()
            mock_content_chunk.choices = [Mock()]
            mock_content_chunk.choices[0].delta = Mock()
            mock_content_chunk.choices[0].delta.content = "Response"
            mock_content_chunk.usage = None  # Content chunks don't have usage

            # Create final chunk with usage
            mock_usage_chunk = Mock()
            mock_usage_chunk.choices = [Mock()]
            mock_usage_chunk.choices[0].delta = Mock()
            mock_usage_chunk.choices[0].delta.content = None  # Final chunk has no content
            mock_usage_chunk.usage = Mock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            )

            mock_stream_obj = Mock()
            mock_stream_obj.__iter__ = Mock(return_value=iter([mock_content_chunk, mock_usage_chunk]))

            mock_completion.return_value = mock_stream_obj

            stream = client.chat_stream(messages)

            # Consume the stream
            list(stream)

            # Usage should now be available
            usage = stream.usage
            assert usage.prompt_tokens == 100
            assert usage.completion_tokens == 50
            assert usage.total_tokens == 150

    def test_chat_stream_custom_model(self):
        """Test that custom model parameter overrides default."""
        client = LLMClient(
            api_key="test-key",
            default_model="default-model",
            provider="openrouter"
        )

        messages = [{"role": "user", "content": "Hello"}]

        with patch('litellm.completion') as mock_completion:
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = "Hi"

            mock_stream_obj = Mock()
            mock_stream_obj.__iter__ = Mock(return_value=iter([mock_chunk]))
            mock_stream_obj.usage = Mock(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )

            mock_completion.return_value = mock_stream_obj

            # Call with custom model
            stream = client.chat_stream(messages, model="custom-model")
            list(stream)  # Consume stream

            # Check that litellm.completion was called with custom model
            mock_completion.assert_called_once()
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["model"] == "openrouter/custom-model"


    def test_complete_passes_temperature(self):
        """complete() passes temperature kwarg to litellm when set."""
        client = LLMClient(
            api_key="test-key",
            default_model="test-model",
            provider="test"
        )

        with patch('litellm.completion') as mock_completion:
            mock_completion.return_value = Mock()
            client.complete(
                [{"role": "user", "content": "hello"}],
                temperature=0.8,
            )

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["temperature"] == 0.8

    def test_complete_omits_temperature_when_none(self):
        """complete() does not pass temperature when not set."""
        client = LLMClient(
            api_key="test-key",
            default_model="test-model",
            provider="test"
        )

        with patch('litellm.completion') as mock_completion:
            mock_completion.return_value = Mock()
            client.complete([{"role": "user", "content": "hello"}])

            call_kwargs = mock_completion.call_args[1]
            assert "temperature" not in call_kwargs


@pytest.mark.unit
class TestStreamingResponse:
    """Tests for StreamingResponse class."""

    def test_streaming_response_iteration(self):
        """Test that StreamingResponse properly iterates through chunks."""
        def mock_generator():
            yield "chunk1"
            yield "chunk2"
            yield "chunk3"
            return (TokenUsage(10, 5, 15), Mock())

        stream = StreamingResponse(mock_generator())
        chunks = list(stream)

        assert chunks == ["chunk1", "chunk2", "chunk3"]

    def test_streaming_response_usage_after_iteration(self):
        """Test that usage is available after iteration completes."""
        def mock_generator():
            yield "text"
            return (TokenUsage(100, 50, 150), Mock())

        stream = StreamingResponse(mock_generator())
        list(stream)  # Consume stream

        usage = stream.usage
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
