"""
Stream handling for LLM responses.

Extracts streaming, metrics tracking, and cost calculation into a
reusable class shared by all agents.
"""

from dataclasses import dataclass

from packages.core.llm_client import LLMClient, TokenUsage
from packages.core.pricing import ModelPricing, calculate_cost_from_litellm
from packages.telemetry.metrics import MetricsTracker, ResponseMetrics


@dataclass
class StreamResult:
    """Result of a streamed LLM response."""
    text: str
    usage: TokenUsage
    cost_usd: float
    metrics: ResponseMetrics


class StreamHandler:
    """Streams LLM responses while tracking metrics and cost."""

    def __init__(
        self,
        client: LLMClient,
        metrics_tracker: MetricsTracker,
        pricing: ModelPricing | None,
        model_id: str,
    ):
        self.client = client
        self.metrics_tracker = metrics_tracker
        self.pricing = pricing
        self.model_id = model_id

    def stream(
        self,
        messages: list[dict],
        print_chunks: bool = False,
    ) -> StreamResult:
        """Stream an LLM response, tracking metrics and cost.

        Args:
            messages: Messages to send to the LLM.
            print_chunks: Whether to print chunks to stdout as they arrive.

        Returns:
            StreamResult with full text, usage, cost, and metrics.
        """
        self.metrics_tracker.start_request()
        response = self.client.chat_stream(messages)

        chunks: list[str] = []
        first_token = True
        for chunk in response:
            if first_token:
                self.metrics_tracker.record_first_token()
                first_token = False
            if print_chunks:
                print(chunk, end="", flush=True)
            chunks.append(chunk)

        usage = response.usage

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

        return StreamResult(
            text="".join(chunks),
            usage=usage,
            cost_usd=cost_usd,
            metrics=response_metrics,
        )
