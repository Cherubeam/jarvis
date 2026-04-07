"""
Unit tests for llm_client module.

Tests LLMClient, TokenUsage, and StreamingResponse functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Try new import path first, fall back to old for backward compatibility
try:
    from packages.core.llm_client import (
        TokenUsage, StreamingResponse, LLMClient,
        InsufficientCreditsError, PromptTokenLimitError, _parse_credit_error,
        _apply_cache_control, _extract_cache_tokens,
    )
except ImportError:
    from llm_client import TokenUsage, StreamingResponse, LLMClient


@pytest.mark.unit
class TestLiteLLMConfig:
    """Tests for module-level litellm configuration."""

    def test_suppress_debug_info_enabled(self):
        """Verify litellm debug output is suppressed at import time."""
        import litellm
        assert litellm.suppress_debug_info is True


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

    def test_llm_client_init(self):
        """Test that LLMClient stores api_keys and default_model."""
        client = LLMClient(
            api_keys={"openrouter": "test-key"},
            default_model="openrouter/anthropic/claude-sonnet-4.6",
        )

        assert client.api_keys == {"openrouter": "test-key"}
        assert client.default_model == "openrouter/anthropic/claude-sonnet-4.6"

    def test_set_model(self):
        """Test that set_model switches the default model."""
        client = LLMClient(
            api_keys={"openrouter": "test-key"},
            default_model="openrouter/anthropic/claude-sonnet-4.6",
        )
        client.set_model("anthropic/claude-opus-4.6")
        assert client.default_model == "anthropic/claude-opus-4.6"

    def test_resolve_api_key_openrouter(self):
        """Test that _resolve_api_key picks the right key for openrouter models."""
        client = LLMClient(
            api_keys={"openrouter": "or-key", "anthropic": "ant-key"},
            default_model="openrouter/anthropic/claude-sonnet-4.6",
        )
        assert client._resolve_api_key("openrouter/anthropic/claude-sonnet-4.6") == "or-key"

    def test_resolve_api_key_anthropic(self):
        """Test that _resolve_api_key picks the right key for anthropic models."""
        client = LLMClient(
            api_keys={"openrouter": "or-key", "anthropic": "ant-key"},
            default_model="anthropic/claude-sonnet-4.6",
        )
        assert client._resolve_api_key("anthropic/claude-sonnet-4.6") == "ant-key"

    def test_resolve_api_key_missing(self):
        """Test that _resolve_api_key returns None for unknown provider."""
        client = LLMClient(
            api_keys={"openrouter": "or-key"},
            default_model="openrouter/anthropic/claude-sonnet-4.6",
        )
        assert client._resolve_api_key("anthropic/claude-sonnet-4.6") is None

    def test_chat_stream_returns_streaming_response(self):
        """Test that chat_stream returns a StreamingResponse object."""
        client = LLMClient(
            api_keys={"test": "test-key"},
            default_model="test/test-model",
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
            api_keys={"test": "test-key"},
            default_model="test/test-model",
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
            api_keys={"test": "test-key"},
            default_model="test/test-model",
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
            api_keys={"openrouter": "test-key"},
            default_model="openrouter/default-model",
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
            stream = client.chat_stream(messages, model="openrouter/custom-model")
            list(stream)  # Consume stream

            # Check that litellm.completion was called with custom model
            mock_completion.assert_called_once()
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["model"] == "openrouter/custom-model"

    def test_chat_stream_passes_correct_api_key(self):
        """Test that the correct API key is passed based on model provider."""
        client = LLMClient(
            api_keys={"openrouter": "or-key", "anthropic": "ant-key"},
            default_model="openrouter/anthropic/claude-sonnet-4.6",
        )

        with patch('litellm.completion') as mock_completion:
            mock_chunk = Mock()
            mock_chunk.choices = [Mock()]
            mock_chunk.choices[0].delta = Mock()
            mock_chunk.choices[0].delta.content = "Hi"

            mock_stream_obj = Mock()
            mock_stream_obj.__iter__ = Mock(return_value=iter([mock_chunk]))

            mock_completion.return_value = mock_stream_obj

            stream = client.chat_stream([{"role": "user", "content": "Hi"}])
            list(stream)

            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["api_key"] == "or-key"

    def test_complete_passes_temperature(self):
        """complete() passes temperature kwarg to litellm when set."""
        client = LLMClient(
            api_keys={"test": "test-key"},
            default_model="test/test-model",
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
            api_keys={"test": "test-key"},
            default_model="test/test-model",
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


@pytest.mark.unit
class TestCreditErrorParsing:
    """Tests for 402 credit error detection."""

    def test_402_raises_insufficient_credits_error(self):
        """A 402 with 'can only afford N' is converted to InsufficientCreditsError."""
        import litellm

        client = LLMClient(
            api_keys={"test": "test-key"},
            default_model="test/test-model",
        )

        error = litellm.APIError(
            status_code=402,
            message="You requested up to 16384 tokens, but can only afford 8612",
            llm_provider="openrouter",
            model="test/test-model",
        )

        with patch("litellm.completion", side_effect=error):
            with pytest.raises(InsufficientCreditsError) as exc_info:
                stream = client.chat_stream(
                    [{"role": "user", "content": "hi"}], max_tokens=16384,
                )
                list(stream)  # Consume to trigger the generator

            assert exc_info.value.affordable == 8612
            assert exc_info.value.requested == 16384

    def test_402_prompt_limit_raises_prompt_token_limit_error(self):
        """A 402 with 'Prompt tokens limit exceeded' raises PromptTokenLimitError."""
        import litellm

        client = LLMClient(
            api_keys={"test": "test-key"},
            default_model="test/test-model",
        )

        error = litellm.APIError(
            status_code=402,
            message="Prompt tokens limit exceeded: 13391 > 7985. To increase, visit https://openrouter.ai/settings/keys",
            llm_provider="openrouter",
            model="test/test-model",
        )

        with patch("litellm.completion", side_effect=error):
            with pytest.raises(PromptTokenLimitError) as exc_info:
                stream = client.chat_stream(
                    [{"role": "user", "content": "hi"}], max_tokens=16384,
                )
                list(stream)

            assert exc_info.value.prompt_tokens == 13391
            assert exc_info.value.limit == 7985

    def test_non_402_error_passes_through(self):
        """A 500 error is not caught by the credit error handler."""
        import litellm

        client = LLMClient(
            api_keys={"test": "test-key"},
            default_model="test/test-model",
        )

        error = litellm.APIError(
            status_code=500,
            message="Internal server error",
            llm_provider="openrouter",
            model="test/test-model",
        )

        with patch("litellm.completion", side_effect=error):
            with pytest.raises(litellm.APIError):
                stream = client.chat_stream([{"role": "user", "content": "hi"}])
                list(stream)  # Consume to trigger the generator


@pytest.mark.unit
class TestCacheControl:
    """Tests for prompt caching helpers."""

    def test_cache_control_added_for_anthropic_model(self):
        """Verify cache_control is injected for openrouter/anthropic models."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = _apply_cache_control(messages, "openrouter/anthropic/claude-sonnet-4.6")

        assert result[0]["role"] == "system"
        content = result[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "You are helpful."
        assert content[0]["cache_control"] == {"type": "ephemeral"}
        # User message unchanged
        assert result[1] == {"role": "user", "content": "Hello"}

    def test_cache_control_added_for_direct_anthropic_model(self):
        """Verify cache_control is injected for direct anthropic/ models."""
        messages = [{"role": "system", "content": "System prompt."}]
        result = _apply_cache_control(messages, "anthropic/claude-sonnet-4.6")

        content = result[0]["content"]
        assert isinstance(content, list)
        assert content[0]["cache_control"] == {"type": "ephemeral"}

    def test_cache_control_not_added_for_non_anthropic(self):
        """Verify no modification for non-Anthropic models."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = _apply_cache_control(messages, "openrouter/google/gemini-2.5-flash")

        assert result is messages  # Same object, no copy
        assert result[0]["content"] == "You are helpful."

    def test_cache_control_no_system_message(self):
        """Verify no modification when first message is not system."""
        messages = [{"role": "user", "content": "Hello"}]
        result = _apply_cache_control(messages, "openrouter/anthropic/claude-sonnet-4.6")

        assert result is messages

    def test_cache_control_empty_messages(self):
        """Verify no crash on empty messages."""
        result = _apply_cache_control([], "openrouter/anthropic/claude-sonnet-4.6")
        assert result == []

    def test_cache_control_already_block_format(self):
        """Verify no modification when content is already in block format."""
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "Already blocks"}],
            },
        ]
        result = _apply_cache_control(messages, "openrouter/anthropic/claude-sonnet-4.6")
        # Should not modify non-string content
        assert result is messages


@pytest.mark.unit
class TestExtractCacheTokens:
    """Tests for cache token extraction from usage objects."""

    def test_extract_anthropic_cache_tokens(self):
        """Extract cache tokens from Anthropic-style usage object."""
        usage = Mock()
        usage.cache_read_input_tokens = 5000
        usage.cache_creation_input_tokens = 2000
        usage.prompt_tokens_details = None

        read, write = _extract_cache_tokens(usage)
        assert read == 5000
        assert write == 2000

    def test_extract_openai_cache_tokens(self):
        """Extract cache tokens from OpenAI-style usage object."""
        usage = Mock(spec=[])
        usage.cache_read_input_tokens = 0
        usage.cache_creation_input_tokens = 0
        details = Mock()
        details.cached_tokens = 3000
        usage.prompt_tokens_details = details

        read, write = _extract_cache_tokens(usage)
        assert read == 3000
        assert write == 0

    def test_extract_no_cache_tokens(self):
        """Extract returns zeros when no cache info available."""
        usage = Mock(spec=[])
        usage.cache_read_input_tokens = 0
        usage.cache_creation_input_tokens = 0
        usage.prompt_tokens_details = None

        read, write = _extract_cache_tokens(usage)
        assert read == 0
        assert write == 0


@pytest.mark.unit
class TestTokenUsageCacheFields:
    """Tests for cache fields on TokenUsage."""

    def test_token_usage_cache_defaults(self):
        """Cache fields default to zero."""
        usage = TokenUsage()
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0

    def test_token_usage_cache_values(self):
        """Cache fields can be set."""
        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            cache_read_tokens=800,
            cache_write_tokens=200,
        )
        assert usage.cache_read_tokens == 800
        assert usage.cache_write_tokens == 200
