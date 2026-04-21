"""
Metrics tracking for JARVIS.

This module provides utilities for tracking response latency,
token usage, costs, and other performance metrics.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ResponseMetrics:
    """Metrics for a single response."""

    ttft_ms: float = 0.0  # Time to first token
    total_latency_ms: float = 0.0  # Total response time
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    timestamp: str = ""


@dataclass
class SessionMetricsSummary:
    """Aggregated metrics for a session."""

    request_count: int = 0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    average_ttft_ms: float = 0.0
    average_latency_ms: float = 0.0
    responses: list[ResponseMetrics] = field(default_factory=list)


class MetricsTracker:
    """
    Tracks metrics for JARVIS responses.

    Usage:
        tracker = MetricsTracker()

        # Start timing
        tracker.start_request()

        # Record first token (for TTFT)
        tracker.record_first_token()

        # Finish request with token counts
        metrics = tracker.finish_request(
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            model="anthropic/claude-sonnet-4"
        )
    """

    def __init__(self):
        self.session_start = datetime.now()
        self.responses: list[ResponseMetrics] = []
        self._request_start: float | None = None
        self._first_token_time: float | None = None

    def start_request(self):
        """Start timing a new request."""
        self._request_start = time.perf_counter()
        self._first_token_time = None

    def record_first_token(self):
        """Record when the first token was received (for TTFT)."""
        if self._request_start and self._first_token_time is None:
            self._first_token_time = time.perf_counter()

    def finish_request(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        model: str = "",
    ) -> ResponseMetrics:
        """
        Finish timing and record metrics for a request.

        Returns:
            ResponseMetrics for this request
        """
        end_time = time.perf_counter()

        # Calculate TTFT
        ttft_ms = 0.0
        if self._request_start and self._first_token_time:
            ttft_ms = (self._first_token_time - self._request_start) * 1000

        # Calculate total latency
        total_latency_ms = 0.0
        if self._request_start:
            total_latency_ms = (end_time - self._request_start) * 1000

        metrics = ResponseMetrics(
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            model=model,
            timestamp=datetime.now().isoformat(),
        )

        self.responses.append(metrics)
        self._request_start = None
        self._first_token_time = None

        return metrics

    def get_session_summary(self) -> SessionMetricsSummary:
        """Get aggregated metrics for the session."""
        if not self.responses:
            return SessionMetricsSummary()

        total_tokens = sum(r.total_tokens for r in self.responses)
        total_prompt = sum(r.prompt_tokens for r in self.responses)
        total_completion = sum(r.completion_tokens for r in self.responses)
        total_cost = sum(r.cost_usd for r in self.responses)

        # Calculate averages
        avg_ttft = sum(r.ttft_ms for r in self.responses) / len(self.responses)
        avg_latency = sum(r.total_latency_ms for r in self.responses) / len(self.responses)

        return SessionMetricsSummary(
            request_count=len(self.responses),
            total_tokens=total_tokens,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_cost_usd=total_cost,
            average_ttft_ms=avg_ttft,
            average_latency_ms=avg_latency,
            responses=self.responses,
        )

    def to_dict(self) -> dict:
        """Convert session metrics to dictionary."""
        summary = self.get_session_summary()
        return {
            "session_start": self.session_start.isoformat(),
            "request_count": summary.request_count,
            "total_tokens": summary.total_tokens,
            "total_prompt_tokens": summary.total_prompt_tokens,
            "total_completion_tokens": summary.total_completion_tokens,
            "total_cost_usd": summary.total_cost_usd,
            "average_ttft_ms": summary.average_ttft_ms,
            "average_latency_ms": summary.average_latency_ms,
        }
