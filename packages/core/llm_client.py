"""
Thin wrapper around LiteLLM for unified LLM access.
Supports multiple providers via LiteLLM's routing conventions.
"""

from dataclasses import dataclass
from typing import Generator
import litellm

from packages.core.model_resolver import infer_provider, get_api_key


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

    def __init__(self, api_keys: dict[str, str], default_model: str):
        """
        Initialize the LLM client.

        Args:
            api_keys: Mapping of provider name -> API key
                      (e.g. {"openrouter": "sk-...", "anthropic": "sk-ant-..."})
            default_model: Default LiteLLM-routable model ID
                           (e.g. "openrouter/anthropic/claude-sonnet-4.6")
        """
        self.api_keys = api_keys
        self.default_model = default_model

    def set_model(self, model_id: str) -> None:
        """Switch the default model mid-session."""
        self.default_model = model_id

    def _resolve_api_key(self, model: str) -> str | None:
        """Pick the right API key based on the model's provider prefix."""
        provider = infer_provider(model)
        return get_api_key(provider, self.api_keys)

    def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> object:
        """
        Non-streaming completion. Used in the agentic tool-calling loop.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed
            tools: LiteLLM-formatted tool definitions
            temperature: Sampling temperature override

        Returns:
            Raw LiteLLM ModelResponse object
        """
        model_to_use = model or self.default_model

        kwargs: dict = dict(
            model=model_to_use,
            messages=messages,
            stream=False,
            api_key=self._resolve_api_key(model_to_use),
        )
        if tools:
            kwargs["tools"] = tools
        if temperature is not None:
            kwargs["temperature"] = temperature

        return litellm.completion(**kwargs)

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> StreamingResponse:
        """
        Stream a chat response, yielding chunks as they arrive.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed
            tools: LiteLLM-formatted tool definitions

        Returns:
            StreamingResponse that yields text chunks and provides usage stats after completion
        """
        return StreamingResponse(self._stream_response(messages, model, tools))

    def _stream_response(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> Generator[str, None, tuple[TokenUsage, object]]:
        """Stream the response chunk by chunk, returning usage stats and raw response at the end."""

        model_to_use = model or self.default_model

        # LiteLLM will handle provider-specific auth and formatting
        kwargs: dict = dict(
            model=model_to_use,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},  # Request usage in streaming
            api_key=self._resolve_api_key(model_to_use),
        )
        if tools:
            kwargs["tools"] = tools

        response = litellm.completion(**kwargs)

        # Stream content chunks and extract usage from chunks
        usage = TokenUsage()

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

            # Check if this chunk contains usage info (usually the last chunk)
            if hasattr(chunk, 'usage') and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                )

        return usage, response
