"""
Thin wrapper around LiteLLM for unified LLM access.
Supports OpenRouter and can easily switch to other providers.
"""

from dataclasses import dataclass
from typing import Generator
import litellm


@dataclass
class TokenUsage:
    """Token usage statistics from a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StreamingResponse:
    """Wrapper for streaming that captures both content and usage."""

    def __init__(self, generator: Generator[str, None, tuple[TokenUsage, object]]):
        self._generator = generator
        self._usage: TokenUsage | None = None
        self._raw_response: object | None = None

    def __iter__(self):
        return self

    def __next__(self) -> str:
        try:
            return next(self._generator)
        except StopIteration as e:
            self._usage, self._raw_response = e.value
            raise

    @property
    def usage(self) -> TokenUsage:
        """Get token usage. Only available after iteration completes."""
        return self._usage or TokenUsage()

    @property
    def raw_response(self) -> object | None:
        """Get the raw LiteLLM response object. Only available after iteration completes."""
        return self._raw_response


class LLMClient:
    """Handles communication with LLM providers via LiteLLM."""

    def __init__(self, api_key: str, default_model: str, provider: str = "openrouter"):
        """
        Initialize the LLM client.

        Args:
            api_key: API key for the provider
            default_model: Default model ID (provider-specific format)
            provider: Provider name ("openrouter", "anthropic", "openai", etc.)
        """
        self.api_key = api_key
        self.provider = provider

        # Format model name for LiteLLM
        # OpenRouter models need "openrouter/" prefix
        if provider == "openrouter" and not default_model.startswith("openrouter/"):
            self.default_model = f"openrouter/{default_model}"
        else:
            self.default_model = default_model

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> StreamingResponse:
        """
        Stream a chat response, yielding chunks as they arrive.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed

        Returns:
            StreamingResponse that yields text chunks and provides usage stats after completion
        """
        return StreamingResponse(self._stream_response(messages, model))

    def _stream_response(
        self,
        messages: list[dict],
        model: str | None = None
    ) -> Generator[str, None, tuple[TokenUsage, object]]:
        """Stream the response chunk by chunk, returning usage stats and raw response at the end."""

        # Prepare model name
        model_to_use = model or self.default_model
        if self.provider == "openrouter" and not model_to_use.startswith("openrouter/"):
            model_to_use = f"openrouter/{model_to_use}"

        # LiteLLM will handle provider-specific auth and formatting
        response = litellm.completion(
            model=model_to_use,
            messages=messages,
            stream=True,
            api_key=self.api_key,
            # fallbacks=[],  # Could specify fallbacks if desired
        )

        # Stream content chunks
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

        # Extract usage from the response object
        # LiteLLM aggregates usage across all chunks
        usage = TokenUsage()
        if hasattr(response, 'usage') and response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return usage, response
