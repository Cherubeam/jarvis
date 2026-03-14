"""
Stream handling for LLM responses.

Extracts streaming, metrics tracking, and cost calculation into a
reusable class shared by all agents.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from packages.core.llm_client import LLMClient, StreamToolResult, StreamingResponse, TokenUsage
from packages.core.pricing import ModelPricing, calculate_cost_from_litellm
from packages.telemetry.metrics import MetricsTracker, ResponseMetrics

_MAX_AGENTIC_ITERATIONS = 5


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
    ):
        self.client = client
        self.metrics_tracker = metrics_tracker
        self.pricing = pricing
        self.model_id = model_id
        self.on_tool_call = on_tool_call
        self.on_chunk = on_chunk

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
        from packages.core.tools.base import ToolRegistry
        from packages.core.tools.executor import execute_tool_calls

        tools_format = None
        self._terminal_tool_fired = False
        self._streaming_response = None
        self.metrics_tracker.start_request()
        if tool_registry is not None and not tool_registry.is_empty():
            messages, tools_format = self._run_agentic_loop(
                messages, tool_registry, execute_tool_calls,
                max_iterations=max_iterations,
            )

        if self._terminal_tool_fired:
            # Terminal tool fired — skip streaming, return accumulated results
            usage = getattr(self, "_intermediate_usage", TokenUsage())
            tool_messages = getattr(self, "_tool_messages", [])
            self._intermediate_usage = None
            self._tool_messages = []

            cost_usd = 0.0
            if self.pricing:
                cost_usd = self.pricing.calculate_cost(usage.prompt_tokens, usage.completion_tokens)

            response_metrics = self.metrics_tracker.finish_request(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_usd=cost_usd,
                model=self.model_id,
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

        return self._stream_simple(messages, print_chunks, tools=tools_format)

    def _run_agentic_loop(self, messages: list[dict], tool_registry, execute_tool_calls, max_iterations: int | None = None) -> tuple[list[dict], list[dict]]:
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
            result = self.client.stream_with_tool_detection(
                messages, tools=tools_format,
            )

            # Content response — no tool calls detected
            if isinstance(result, StreamingResponse):
                # Save the streaming response so stream() can use it
                # instead of making another API call
                self._streaming_response = result
                break

            # Tool calls detected via streaming
            tool_result: StreamToolResult = result
            accumulated_usage = TokenUsage(
                prompt_tokens=accumulated_usage.prompt_tokens + tool_result.usage.prompt_tokens,
                completion_tokens=accumulated_usage.completion_tokens + tool_result.usage.completion_tokens,
                total_tokens=accumulated_usage.total_tokens + (
                    tool_result.usage.prompt_tokens + tool_result.usage.completion_tokens
                ),
            )

            # UX feedback for each tool call
            for call in tool_result.tool_calls:
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
            tool_results = execute_tool_calls(tool_result.tool_calls, tool_registry)
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

        # Store accumulated intermediate usage so _stream_simple can add to it
        self._intermediate_usage = accumulated_usage
        self._tool_messages = tool_messages
        return messages, tools_format

    def _stream_from_response(self, response: StreamingResponse, print_chunks: bool) -> StreamResult:
        """Stream from an already-started StreamingResponse (from tool detection)."""
        chunks: list[str] = []
        first_token = True
        for chunk in response:
            if first_token:
                self.metrics_tracker.record_first_token()
                first_token = False
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
            )
            self._intermediate_usage = None

        cost_usd = 0.0
        if self.pricing:
            cost_usd = self.pricing.calculate_cost(usage.prompt_tokens, usage.completion_tokens)
        else:
            cost_usd = calculate_cost_from_litellm(response.raw_response)

        response_metrics = self.metrics_tracker.finish_request(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost_usd,
            model=self.model_id,
        )

        tool_messages = getattr(self, "_tool_messages", [])
        self._tool_messages = []

        return StreamResult(
            text="".join(chunks),
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
            tool_messages=tool_messages,
        )

    def _stream_simple(self, messages: list[dict], print_chunks: bool, tools: list[dict] | None = None) -> StreamResult:
        """Stream the final response and return a StreamResult."""
        response = self.client.chat_stream(messages, tools=tools)

        chunks: list[str] = []
        first_token = True
        for chunk in response:
            if first_token:
                self.metrics_tracker.record_first_token()
                first_token = False
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
            )
            self._intermediate_usage = None

        cost_usd = 0.0
        if self.pricing:
            cost_usd = self.pricing.calculate_cost(usage.prompt_tokens, usage.completion_tokens)
        else:
            cost_usd = calculate_cost_from_litellm(response.raw_response)

        response_metrics = self.metrics_tracker.finish_request(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=cost_usd,
            model=self.model_id,
        )

        # Collect any tool messages from the agentic loop
        tool_messages = getattr(self, "_tool_messages", [])
        self._tool_messages = []

        return StreamResult(
            text="".join(chunks),
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
            tool_messages=tool_messages,
        )
