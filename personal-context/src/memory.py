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
    """Aggregated token usage and costs for a session."""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0

    def add_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float = 0.0,
    ):
        """Add usage from a single request."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.total_cost_usd += cost_usd
        self.request_count += 1

    def to_dict(self) -> dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "request_count": self.request_count,
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
    ):
        """Add a message to the current conversation with optional token usage and cost."""
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
            self.metrics.add_usage(prompt_tokens, completion_tokens, total_tokens, cost_usd)

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
        """Print token usage and cost summary for the session."""
        m = self.metrics
        if m.request_count > 0:
            # Format cost based on amount
            if m.total_cost_usd < 0.01:
                cost_str = f"${m.total_cost_usd:.4f}"
            else:
                cost_str = f"${m.total_cost_usd:.2f}"

            print(
                f"Session: {m.total_tokens:,} tokens "
                f"({m.total_prompt_tokens:,} prompt + {m.total_completion_tokens:,} completion) | "
                f"Cost: {cost_str} | "
                f"{m.request_count} request(s)"
            )
    
    def get_messages_for_api(self) -> list[dict]:
        """Return messages in the format the API expects (without timestamps)."""
        return [
            {"role": m["role"], "content": m["content"]} 
            for m in self.current_conversation
        ]