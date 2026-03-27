"""
Thin wrapper around LiteLLM for unified LLM access.
Supports multiple providers via LiteLLM's routing conventions.
"""

import re
from dataclasses import dataclass, field
from typing import Generator
import litellm

from packages.core.model_resolver import infer_provider, get_api_key


def _apply_cache_control(messages: list[dict], model: str) -> list[dict]:
    """Add cache_control breakpoint to system message for Anthropic models.

    Only activates when the model string contains 'anthropic' (covers both
    openrouter/anthropic/... and direct anthropic/... models).
    """
    if "anthropic" not in model:
        return messages
    if not messages or messages[0].get("role") != "system":
        return messages

    system_msg = messages[0]
    content = system_msg["content"]

    if isinstance(content, str):
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": content,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            *messages[1:],
        ]
    return messages


def _get_nested(obj, *attrs):
    """Safely traverse nested attributes, returning None if any is missing."""
    for attr in attrs:
        obj = getattr(obj, attr, None)
        if obj is None:
            return None
    return obj


def _extract_cache_tokens(usage) -> tuple[int, int]:
    """Extract cache read/write tokens from a usage object, regardless of provider.

    Anthropic: cache_read_input_tokens, cache_creation_input_tokens
    OpenAI:    prompt_tokens_details.cached_tokens (read only, no write concept)
    LiteLLM:   May normalize to cache_read_input_tokens / cache_creation_input_tokens
    """
    cache_read = (
        getattr(usage, "cache_read_input_tokens", 0)
        or _get_nested(usage, "prompt_tokens_details", "cached_tokens")
        or 0
    )
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return cache_read, cache_write


class InsufficientCreditsError(Exception):
    """Raised when OpenRouter returns 402 due to insufficient credits."""

    def __init__(self, requested: int, affordable: int, original_error: Exception):
        self.requested = requested
        self.affordable = affordable
        self.original_error = original_error
        super().__init__(f"Requested {requested} tokens but can only afford {affordable}")


class PromptTokenLimitError(Exception):
    """Raised when prompt tokens exceed the API key's monthly limit."""

    def __init__(self, prompt_tokens: int, limit: int, original_error: Exception):
        self.prompt_tokens = prompt_tokens
        self.limit = limit
        self.original_error = original_error
        super().__init__(f"Prompt tokens ({prompt_tokens}) exceed key limit ({limit})")


_AFFORDABLE_TOKENS_RE = re.compile(r"can only afford (\d+)")
_PROMPT_LIMIT_RE = re.compile(r"Prompt tokens limit exceeded:\s*(\d+)\s*>\s*(\d+)")


def _parse_credit_error(
    error: Exception, max_tokens: int | None,
) -> InsufficientCreditsError | PromptTokenLimitError | None:
    """Parse a 402 API error into a typed exception, or return None."""
    if getattr(error, "status_code", None) != 402:
        return None
    msg = str(error)
    prompt_match = _PROMPT_LIMIT_RE.search(msg)
    if prompt_match:
        return PromptTokenLimitError(int(prompt_match.group(1)), int(prompt_match.group(2)), error)
    match = _AFFORDABLE_TOKENS_RE.search(msg)
    if not match:
        return None
    return InsufficientCreditsError(max_tokens or 0, int(match.group(1)), error)


@dataclass
class TokenUsage:
    """Token usage statistics from a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class StreamToolResult:
    """Result from a streaming call that detected tool calls instead of content."""
    tool_calls: list  # Accumulated tool call objects
    usage: TokenUsage
    finish_reason: str = "tool_calls"


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
        max_tokens: int | None = None,
    ) -> object:
        """
        Non-streaming completion. Used in the agentic tool-calling loop
        and as the primary path when streaming is disabled.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed
            tools: LiteLLM-formatted tool definitions
            temperature: Sampling temperature override
            max_tokens: Maximum tokens to generate

        Returns:
            Raw LiteLLM ModelResponse object
        """
        model_to_use = model or self.default_model
        messages = _apply_cache_control(messages, model_to_use)

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
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        return litellm.completion(**kwargs)

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> StreamingResponse:
        """
        Stream a chat response, yielding chunks as they arrive.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed
            tools: LiteLLM-formatted tool definitions
            max_tokens: Maximum tokens for the response

        Returns:
            StreamingResponse that yields text chunks and provides usage stats after completion
        """
        return StreamingResponse(self._stream_response(messages, model, tools, max_tokens=max_tokens))

    def stream_with_tool_detection(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> StreamingResponse | StreamToolResult:
        """Stream a response, detecting tool calls without a separate complete() call.

        If the model wants to call tools, accumulates the full tool call info
        from streaming deltas and returns a StreamToolResult.
        If the model returns content, returns a normal StreamingResponse.

        This eliminates the separate complete() call in the agentic loop,
        saving one round-trip per non-tool query.
        """
        model_to_use = model or self.default_model
        messages = _apply_cache_control(messages, model_to_use)

        kwargs: dict = dict(
            model=model_to_use,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            api_key=self._resolve_api_key(model_to_use),
        )
        if tools:
            kwargs["tools"] = tools
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = litellm.completion(**kwargs)
        except litellm.APIError as e:
            credit_err = _parse_credit_error(e, kwargs.get("max_tokens"))
            if credit_err:
                raise credit_err from e
            raise

        # Peek at chunks to determine if this is a tool call or content response
        content_chunks: list[str] = []
        tool_call_deltas: dict[int, dict] = {}  # index -> accumulated tool call
        usage = TokenUsage()
        is_tool_response = False

        for chunk in response:
            # Extract usage from final chunk
            if hasattr(chunk, 'usage') and chunk.usage:
                cache_read, cache_write = _extract_cache_tokens(chunk.usage)
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                )

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # Accumulate tool call deltas
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                is_tool_response = True
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {
                            "id": tc_delta.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    entry = tool_call_deltas[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if hasattr(tc_delta, 'function') and tc_delta.function:
                        if tc_delta.function.name:
                            entry["function"]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["function"]["arguments"] += tc_delta.function.arguments

            # Accumulate content
            if delta.content:
                content_chunks.append(delta.content)

        if is_tool_response:
            # Build tool call objects that match the complete() response format
            from types import SimpleNamespace
            tool_calls = []
            for idx in sorted(tool_call_deltas):
                tc = tool_call_deltas[idx]
                tool_calls.append(SimpleNamespace(
                    id=tc["id"],
                    function=SimpleNamespace(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                    type="function",
                ))
            return StreamToolResult(tool_calls=tool_calls, usage=usage)

        # Content response — wrap remaining content in a StreamingResponse
        def _replay_content() -> Generator[str, None, tuple[TokenUsage, object]]:
            for c in content_chunks:
                yield c
            return usage, response

        return StreamingResponse(_replay_content())

    def _stream_response(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> Generator[str, None, tuple[TokenUsage, object]]:
        """Stream the response chunk by chunk, returning usage stats and raw response at the end."""

        model_to_use = model or self.default_model
        messages = _apply_cache_control(messages, model_to_use)

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
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = litellm.completion(**kwargs)
        except litellm.APIError as e:
            credit_err = _parse_credit_error(e, kwargs.get("max_tokens"))
            if credit_err:
                raise credit_err from e
            raise

        # Stream content chunks and extract usage from chunks
        usage = TokenUsage()

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

            # Check if this chunk contains usage info (usually the last chunk)
            if hasattr(chunk, 'usage') and chunk.usage:
                cache_read, cache_write = _extract_cache_tokens(chunk.usage)
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                    total_tokens=chunk.usage.total_tokens or 0,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                )

        return usage, response
