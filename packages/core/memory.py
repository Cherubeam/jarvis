"""
Handles conversation persistence.
For now, just saves conversations to JSON files.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SessionMetrics:
    """Aggregated token usage, costs, and latency for a session."""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0
    total_ttft_ms: float = 0.0
    total_latency_ms: float = 0.0

    def add_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float = 0.0,
        ttft_ms: float = 0.0,
        total_latency_ms: float = 0.0,
    ):
        """Add usage from a single request."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.total_cost_usd += cost_usd
        self.total_ttft_ms += ttft_ms
        self.total_latency_ms += total_latency_ms
        self.request_count += 1

    @property
    def average_ttft_ms(self) -> float:
        """Average time to first token across all requests."""
        return self.total_ttft_ms / self.request_count if self.request_count > 0 else 0.0

    @property
    def average_latency_ms(self) -> float:
        """Average total latency across all requests."""
        return self.total_latency_ms / self.request_count if self.request_count > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "request_count": self.request_count,
            "average_ttft_ms": self.average_ttft_ms,
            "average_latency_ms": self.average_latency_ms,
        }


class ConversationLogger:
    """Logs conversations to files for later review/learning."""

    def __init__(self, conversations_dir: Path):
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.current_conversation: list[dict] = []
        self.session_start = datetime.now()
        self.metrics = SessionMetrics()

    def add_message(
        self,
        role: str,
        content: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        ttft_ms: float = 0.0,
        total_latency_ms: float = 0.0,
    ):
        """Add a message to the current conversation with optional token usage, cost, and latency."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        # Only add usage for assistant messages (where we have the data)
        if role == "assistant" and total_tokens > 0:
            message["usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
            }
            # Add latency metrics if available
            if ttft_ms > 0 or total_latency_ms > 0:
                message["latency"] = {
                    "ttft_ms": ttft_ms,
                    "total_ms": total_latency_ms,
                }
            self.metrics.add_usage(
                prompt_tokens, completion_tokens, total_tokens, cost_usd,
                ttft_ms, total_latency_ms
            )

        self.current_conversation.append(message)

    def save(self):
        """Save the current conversation to a file."""
        if not self.current_conversation:
            return

        filename = self.session_start.strftime("%Y-%m-%d_%H-%M-%S.json")
        filepath = self.conversations_dir / filename

        data = {
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "metrics": self.metrics.to_dict(),
            "messages": self.current_conversation,
        }

        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nConversation saved to {filepath}")
        self._print_session_summary()

    def _print_session_summary(self):
        """Print token usage, cost, and latency summary for the session."""
        m = self.metrics
        if m.request_count > 0:
            # Format cost based on amount
            if m.total_cost_usd < 0.01:
                cost_str = f"${m.total_cost_usd:.4f}"
            else:
                cost_str = f"${m.total_cost_usd:.2f}"

            # Format latency stats
            latency_str = ""
            if m.average_ttft_ms > 0:
                latency_str = f" | Avg TTFT: {m.average_ttft_ms:.0f}ms | Avg latency: {m.average_latency_ms:.0f}ms"

            print(
                f"Session: {m.total_tokens:,} tokens "
                f"({m.total_prompt_tokens:,} prompt + {m.total_completion_tokens:,} completion) | "
                f"Cost: {cost_str} | "
                f"{m.request_count} request(s){latency_str}"
            )

    def get_messages_for_api(self) -> list[dict]:
        """Return messages in the format the API expects (without timestamps)."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.current_conversation
        ]
