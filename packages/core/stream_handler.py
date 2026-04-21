"""
Stream handling for LLM responses.

Extracts streaming, metrics tracking, and cost calculation into a
reusable class shared by all agents.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from packages.core.events import (
    Event,
    TextChunk,
    ToolCallStarted,
    UsageReport,
)
from packages.core.events import (
    ToolResult as ToolResultEvent,
)
from packages.core.llm_client import (
    LLMClient,
    StreamingResponse,
    StreamToolResult,
    TokenUsage,
    _extract_cache_tokens,
)
from packages.core.pricing import ModelPricing, calculate_cost_from_litellm
from packages.telemetry.metrics import MetricsTracker, ResponseMetrics

_MAX_AGENTIC_ITERATIONS = 5
_MIN_USEFUL_TOKENS = 256


@dataclass
class StreamResult:
    """Result of a streamed LLM response."""

    text: str
    usage: TokenUsage
    cost_usd: float
    metrics: ResponseMetrics
    tool_messages: list[dict] = field(default_factory=list)
    delegate_to: str | None = None
    delegate_task: str | None = None
    delegate_context: str | None = None


class StreamHandler:
    """Streams LLM responses while tracking metrics and cost."""

    def __init__(
        self,
        client: LLMClient,
        metrics_tracker: MetricsTracker,
        pricing: ModelPricing | None,
        model_id: str,
        on_tool_call: Callable[[str], None] | None = None,
        on_chunk: Callable[[str], None] | None = None,
        max_tokens: int | None = None,
        on_event: Callable[[Event], None] | None = None,
        instance_id: str = "",
        streaming: bool = True,
    ):
        self.client = client
        self.metrics_tracker = metrics_tracker
        self.pricing = pricing
        self.model_id = model_id
        self.on_tool_call = on_tool_call
        self.on_chunk = on_chunk
        self.max_tokens = max_tokens
        self.on_event = on_event
        self.instance_id = instance_id
        self.streaming = streaming
        self.on_before_tool_exec: Callable[[], None] | None = None
        self.on_after_tool_exec: Callable[[], None] | None = None

    def _emit(self, event: Event) -> None:
        """Emit a typed event to the event callback if registered."""
        if self.on_event is not None:
            self.on_event(event)

    def _calculate_cost(self, usage: TokenUsage, raw_response=None) -> float:
        """Calculate cost using pricing, LiteLLM fallback, or zero."""
        if self.pricing:
            return self.pricing.calculate_cost(
                usage.prompt_tokens,
                usage.completion_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
            )
        if raw_response is not None:
            return calculate_cost_from_litellm(raw_response)
        return 0.0

    def _try_with_credit_fallback(self, api_call):
        """Catch InsufficientCreditsError, reduce max_tokens, and retry once."""
        from packages.core.llm_client import InsufficientCreditsError, PromptTokenLimitError

        try:
            return api_call()
        except PromptTokenLimitError as e:
            raise RuntimeError(
                f"Prompt too large for your OpenRouter key — {e.prompt_tokens} tokens sent, "
                f"but key limit is {e.limit}. Create a key with a higher limit at "
                f"https://openrouter.ai/settings/keys"
            ) from e
        except InsufficientCreditsError as e:
            if e.affordable < _MIN_USEFUL_TOKENS:
                raise RuntimeError(
                    f"Insufficient OpenRouter credits — only {e.affordable} tokens affordable "
                    f"(minimum {_MIN_USEFUL_TOKENS} needed). Please add credits at "
                    f"https://openrouter.ai/settings/credits"
                ) from e
            print(f"\n⚠ Credit limit: reduced max_tokens from {self.max_tokens} → {e.affordable}")
            self.max_tokens = e.affordable
            return api_call()

    def stream(
        self,
        messages: list[dict],
        print_chunks: bool = False,
        tool_registry=None,
        max_iterations: int | None = None,
    ) -> StreamResult:
        """Stream an LLM response, tracking metrics and cost.

        When tool_registry is provided and non-empty, runs an agentic loop
        using streaming-first tool detection (no separate complete() call).
        This eliminates the redundant non-streaming call for queries that
        don't invoke tools.

        Args:
            messages: Messages to send to the LLM.
            print_chunks: Whether to print chunks to stdout as they arrive.
            tool_registry: Optional ToolRegistry. None or empty → simple path.

        Returns:
            StreamResult with full text, usage, cost, and metrics.
        """
        # Import here to avoid circular imports at module load time
        from packages.core.tools.executor import execute_tool_calls

        tools_format = None
        self._terminal_tool_fired = False
        self._streaming_response = None
        final_text = None  # Set by non-streaming agentic loop
        final_usage = None
        self.metrics_tracker.start_request()
        if tool_registry is not None and not tool_registry.is_empty():
            if self.streaming:
                messages, tools_format = self._run_agentic_loop(
                    messages,
                    tool_registry,
                    execute_tool_calls,
                    max_iterations=max_iterations,
                )
            else:
                messages, tools_format, final_text, final_usage = (
                    self._run_agentic_loop_nonstreaming(
                        messages,
                        tool_registry,
                        execute_tool_calls,
                        max_iterations=max_iterations,
                    )
                )

        if self._terminal_tool_fired:
            # Terminal tool fired — skip streaming, return accumulated results
            usage = getattr(self, "_intermediate_usage", TokenUsage())
            tool_messages = getattr(self, "_tool_messages", [])
            self._intermediate_usage = None
            self._tool_messages = []

            cost_usd = self._calculate_cost(usage)

            response_metrics = self.metrics_tracker.finish_request(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_usd=cost_usd,
                model=self.model_id,
            )

            self._emit(
                UsageReport(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cache_read_tokens=usage.cache_read_tokens,
                    cache_write_tokens=usage.cache_write_tokens,
                    cost_usd=cost_usd,
                    model=self.model_id,
                    instance_id=self.instance_id,
                )
            )

            return StreamResult(
                text="",
                usage=usage,
                cost_usd=cost_usd,
                metrics=response_metrics,
                tool_messages=tool_messages,
            )

        # If the agentic loop already received a streaming content response,
        # use it directly instead of making another streaming call
        if self._streaming_response is not None:
            return self._stream_from_response(self._streaming_response, print_chunks)

        # Non-streaming agentic loop already got the final answer
        if final_text is not None:
            return self._complete_from_text(final_text, final_usage or TokenUsage())

        # Final response (no agentic loop, or loop exhausted iterations)
        if self.streaming:
            return self._stream_simple(messages, print_chunks, tools=tools_format)
        return self._complete_simple(messages, tools=tools_format)

    def _run_agentic_loop(
        self,
        messages: list[dict],
        tool_registry,
        execute_tool_calls,
        max_iterations: int | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Run agentic tool-calling loop using streaming-first detection.

        Uses stream_with_tool_detection() instead of complete() to avoid
        the redundant non-streaming call when the model returns content
        instead of tool calls.

        Returns (messages, tools_format) for final streaming.
        """
        tools_format = tool_registry.to_litellm_format()
        accumulated_usage = TokenUsage()
        tool_messages: list[dict] = []

        for _ in range(max_iterations or _MAX_AGENTIC_ITERATIONS):
            result = self._try_with_credit_fallback(
                lambda: self.client.stream_with_tool_detection(
                    messages,
                    tools=tools_format,
                    max_tokens=self.max_tokens,
                )
            )

            # Content response — no tool calls detected
            if isinstance(result, StreamingResponse):
                # Save the streaming response so stream() can use it
                # instead of making another API call
                self._streaming_response = result
                break

            # Tool calls detected via streaming
            tool_result: StreamToolResult = result

            # Deduplicate parallel tool calls with identical name + arguments
            seen: set[tuple[str, str]] = set()
            unique_calls = []
            for tc in tool_result.tool_calls:
                key = (tc.function.name, tc.function.arguments)
                if key not in seen:
                    seen.add(key)
                    unique_calls.append(tc)
            tool_result = StreamToolResult(
                tool_calls=unique_calls,
                usage=tool_result.usage,
            )

            accumulated_usage = TokenUsage(
                prompt_tokens=accumulated_usage.prompt_tokens + tool_result.usage.prompt_tokens,
                completion_tokens=accumulated_usage.completion_tokens
                + tool_result.usage.completion_tokens,
                total_tokens=accumulated_usage.total_tokens
                + (tool_result.usage.prompt_tokens + tool_result.usage.completion_tokens),
                cache_read_tokens=accumulated_usage.cache_read_tokens
                + tool_result.usage.cache_read_tokens,
                cache_write_tokens=accumulated_usage.cache_write_tokens
                + tool_result.usage.cache_write_tokens,
            )

            # UX feedback for each tool call
            for call in tool_result.tool_calls:
                self._emit(
                    ToolCallStarted(
                        tool_name=call.function.name,
                        tool_call_id=call.id,
                        arguments=call.function.arguments,
                        instance_id=self.instance_id,
                    )
                )
                if self.on_tool_call is not None:
                    self.on_tool_call(call.function.name)
                else:
                    print(f"[Tool: {call.function.name}]")

            # Build assistant message from tool calls
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_result.tool_calls
                ],
            }
            if self.on_before_tool_exec:
                self.on_before_tool_exec()
            tool_results = execute_tool_calls(tool_result.tool_calls, tool_registry)
            if self.on_after_tool_exec:
                self.on_after_tool_exec()

            # Emit tool result events
            for tr in tool_results:
                self._emit(
                    ToolResultEvent(
                        tool_name=tr.get("name", ""),
                        result=tr.get("content", ""),
                        tool_call_id=tr.get("tool_call_id", ""),
                        instance_id=self.instance_id,
                    )
                )

            messages = [*messages, assistant_msg, *tool_results]

            # Track tool messages for history persistence
            tool_messages.append(assistant_msg)
            tool_messages.extend(tool_results)

            # Check if any executed tool is terminal (e.g. delegation)
            if any(
                (t := tool_registry.get(call.function.name)) and t.terminal
                for call in tool_result.tool_calls
            ):
                self._terminal_tool_fired = True
                break

        else:
            # Loop exhausted all iterations — force text-only final response
            tools_format = None

        # Store accumulated intermediate usage so _stream_simple can add to it
        self._intermediate_usage = accumulated_usage
        self._tool_messages = tool_messages
        return messages, tools_format

    def _stream_from_response(
        self, response: StreamingResponse, print_chunks: bool
    ) -> StreamResult:
        """Stream from an already-started StreamingResponse (from tool detection)."""
        chunks: list[str] = []
        first_token = True
        for chunk in response:
            if first_token:
                self.metrics_tracker.record_first_token()
                first_token = False
            self._emit(TextChunk(text=chunk, instance_id=self.instance_id))
            if self.on_chunk is not None:
                self.on_chunk(chunk)
            elif print_chunks:
                print(chunk, end="", flush=True)
            chunks.append(chunk)

        usage = response.usage

        # Add any accumulated intermediate usage
        intermediate = getattr(self, "_intermediate_usage", None)
        if intermediate is not None:
            usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens + intermediate.prompt_tokens,
                completion_tokens=usage.completion_tokens + intermediate.completion_tokens,
                total_tokens=usage.total_tokens + intermediate.total_tokens,
                cache_read_tokens=usage.cache_read_tokens + intermediate.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens + intermediate.cache_write_tokens,
            )
            self._intermediate_usage = None

        cost_usd = self._calculate_cost(usage, response.raw_response)

        response_metrics = self.metrics_tracker.finish_request(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost_usd,
            model=self.model_id,
        )

        tool_messages = getattr(self, "_tool_messages", [])
        self._tool_messages = []

        self._emit(
            UsageReport(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=cost_usd,
                model=self.model_id,
                instance_id=self.instance_id,
            )
        )

        return StreamResult(
            text="".join(chunks),
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
            tool_messages=tool_messages,
        )

    def _stream_simple(
        self, messages: list[dict], print_chunks: bool, tools: list[dict] | None = None
    ) -> StreamResult:
        """Stream the final response and return a StreamResult."""
        response = self._try_with_credit_fallback(
            lambda: self.client.chat_stream(messages, tools=tools, max_tokens=self.max_tokens)
        )

        chunks: list[str] = []
        first_token = True
        for chunk in response:
            if first_token:
                self.metrics_tracker.record_first_token()
                first_token = False
            self._emit(TextChunk(text=chunk, instance_id=self.instance_id))
            if self.on_chunk is not None:
                self.on_chunk(chunk)
            elif print_chunks:
                print(chunk, end="", flush=True)
            chunks.append(chunk)

        usage = response.usage

        # Add any accumulated intermediate usage
        intermediate = getattr(self, "_intermediate_usage", None)
        if intermediate is not None:
            usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens + intermediate.prompt_tokens,
                completion_tokens=usage.completion_tokens + intermediate.completion_tokens,
                total_tokens=usage.total_tokens + intermediate.total_tokens,
                cache_read_tokens=usage.cache_read_tokens + intermediate.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens + intermediate.cache_write_tokens,
            )
            self._intermediate_usage = None

        cost_usd = self._calculate_cost(usage, response.raw_response)

        response_metrics = self.metrics_tracker.finish_request(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost_usd,
            model=self.model_id,
        )

        # Collect any tool messages from the agentic loop
        tool_messages = getattr(self, "_tool_messages", [])
        self._tool_messages = []

        self._emit(
            UsageReport(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=cost_usd,
                model=self.model_id,
                instance_id=self.instance_id,
            )
        )

        return StreamResult(
            text="".join(chunks),
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
            tool_messages=tool_messages,
        )

    # ------------------------------------------------------------------
    # Non-streaming paths (used when self.streaming is False)
    # ------------------------------------------------------------------

    def _run_agentic_loop_nonstreaming(
        self,
        messages: list[dict],
        tool_registry,
        execute_tool_calls,
        max_iterations: int | None = None,
    ) -> tuple[list[dict], list[dict] | None, str | None, TokenUsage | None]:
        """Run agentic tool-calling loop using non-streaming complete().

        Returns (messages, tools_format, final_text, final_usage) where
        final_text is set when the model returns content instead of tool calls.
        """
        tools_format = tool_registry.to_litellm_format()
        accumulated_usage = TokenUsage()
        tool_messages: list[dict] = []
        final_text: str | None = None
        final_usage: TokenUsage | None = None

        for _ in range(max_iterations or _MAX_AGENTIC_ITERATIONS):
            response = self._try_with_credit_fallback(
                lambda: self.client.complete(
                    messages,
                    tools=tools_format,
                    max_tokens=self.max_tokens,
                )
            )

            choice = response.choices[0]
            usage_obj = response.usage

            cache_read, cache_write = _extract_cache_tokens(usage_obj)
            call_usage = TokenUsage(
                prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage_obj, "total_tokens", 0) or 0,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            )

            # Content response — no tool calls
            if not choice.message.tool_calls:
                final_text = choice.message.content or ""
                final_usage = call_usage
                # Don't add to accumulated_usage — final_usage is passed
                # separately to _complete_from_text() which merges them.
                break

            # Tool calls detected
            accumulated_usage = TokenUsage(
                prompt_tokens=accumulated_usage.prompt_tokens + call_usage.prompt_tokens,
                completion_tokens=accumulated_usage.completion_tokens
                + call_usage.completion_tokens,
                total_tokens=accumulated_usage.total_tokens + call_usage.total_tokens,
                cache_read_tokens=accumulated_usage.cache_read_tokens
                + call_usage.cache_read_tokens,
                cache_write_tokens=accumulated_usage.cache_write_tokens
                + call_usage.cache_write_tokens,
            )

            tool_calls = choice.message.tool_calls

            # Deduplicate parallel tool calls
            seen: set[tuple[str, str]] = set()
            unique_calls = []
            for tc in tool_calls:
                key = (tc.function.name, tc.function.arguments)
                if key not in seen:
                    seen.add(key)
                    unique_calls.append(tc)
            tool_calls = unique_calls

            # UX feedback for each tool call
            for call in tool_calls:
                self._emit(
                    ToolCallStarted(
                        tool_name=call.function.name,
                        tool_call_id=call.id,
                        arguments=call.function.arguments,
                        instance_id=self.instance_id,
                    )
                )
                if self.on_tool_call is not None:
                    self.on_tool_call(call.function.name)
                else:
                    print(f"[Tool: {call.function.name}]")

            # Build assistant message from tool calls
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            if self.on_before_tool_exec:
                self.on_before_tool_exec()
            tool_results = execute_tool_calls(tool_calls, tool_registry)
            if self.on_after_tool_exec:
                self.on_after_tool_exec()

            # Emit tool result events
            for tr in tool_results:
                self._emit(
                    ToolResultEvent(
                        tool_name=tr.get("name", ""),
                        result=tr.get("content", ""),
                        tool_call_id=tr.get("tool_call_id", ""),
                        instance_id=self.instance_id,
                    )
                )

            messages = [*messages, assistant_msg, *tool_results]
            tool_messages.append(assistant_msg)
            tool_messages.extend(tool_results)

            # Check if any executed tool is terminal
            if any(
                (t := tool_registry.get(call.function.name)) and t.terminal for call in tool_calls
            ):
                self._terminal_tool_fired = True
                break

        else:
            # Loop exhausted all iterations — force text-only final response
            tools_format = None

        self._intermediate_usage = accumulated_usage
        self._tool_messages = tool_messages
        return messages, tools_format, final_text, final_usage

    def _complete_simple(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> StreamResult:
        """Non-streaming final response — returns full text at once."""
        response = self._try_with_credit_fallback(
            lambda: self.client.complete(messages, tools=tools, max_tokens=self.max_tokens)
        )

        text = response.choices[0].message.content or ""
        usage_obj = response.usage

        cache_read, cache_write = _extract_cache_tokens(usage_obj)
        usage = TokenUsage(
            prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage_obj, "total_tokens", 0) or 0,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

        # Add accumulated intermediate usage from agentic loop
        intermediate = getattr(self, "_intermediate_usage", None)
        if intermediate is not None:
            usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens + intermediate.prompt_tokens,
                completion_tokens=usage.completion_tokens + intermediate.completion_tokens,
                total_tokens=usage.total_tokens + intermediate.total_tokens,
                cache_read_tokens=usage.cache_read_tokens + intermediate.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens + intermediate.cache_write_tokens,
            )
            self._intermediate_usage = None

        # Emit full text as a single event (for event subscribers)
        if text:
            self._emit(TextChunk(text=text, instance_id=self.instance_id))

        # TTFT equals total latency for non-streaming
        self.metrics_tracker.record_first_token()

        cost_usd = self._calculate_cost(usage, response)

        response_metrics = self.metrics_tracker.finish_request(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost_usd,
            model=self.model_id,
        )

        tool_messages = getattr(self, "_tool_messages", [])
        self._tool_messages = []

        self._emit(
            UsageReport(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=cost_usd,
                model=self.model_id,
                instance_id=self.instance_id,
            )
        )

        return StreamResult(
            text=text,
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
            tool_messages=tool_messages,
        )

    def _complete_from_text(self, text: str, usage: TokenUsage) -> StreamResult:
        """Build StreamResult from text already obtained by the non-streaming agentic loop."""
        # Add accumulated intermediate usage
        intermediate = getattr(self, "_intermediate_usage", None)
        if intermediate is not None:
            usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens + intermediate.prompt_tokens,
                completion_tokens=usage.completion_tokens + intermediate.completion_tokens,
                total_tokens=usage.total_tokens + intermediate.total_tokens,
                cache_read_tokens=usage.cache_read_tokens + intermediate.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens + intermediate.cache_write_tokens,
            )
            self._intermediate_usage = None

        if text:
            self._emit(TextChunk(text=text, instance_id=self.instance_id))

        self.metrics_tracker.record_first_token()

        cost_usd = self._calculate_cost(usage)

        response_metrics = self.metrics_tracker.finish_request(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost_usd,
            model=self.model_id,
        )

        tool_messages = getattr(self, "_tool_messages", [])
        self._tool_messages = []

        self._emit(
            UsageReport(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                cost_usd=cost_usd,
                model=self.model_id,
                instance_id=self.instance_id,
            )
        )

        return StreamResult(
            text=text,
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
            tool_messages=tool_messages,
        )
