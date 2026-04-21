"""Summary + detail dataclasses. Mirrored on the wire as dicts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConversationSummary:
    """One row in the History list / Sidebar."""

    id: str  # filename stem (e.g. "2026-04-20_10-20-20")
    date: str  # "YYYY-MM-DD"
    title: str  # derived from first user message
    agents: list[str]  # dominant agent first, others after
    messages: int
    tokens: int
    cost: float
    duration_ms: int
    tool_calls: int
    tools: list[str]  # unique tool names (excl. handoff)
    handoffs: int
    model: str
    provider: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationDetail:
    """Summary + full messages + small transcript preview."""

    summary: ConversationSummary
    messages: list[dict[str, Any]] = field(default_factory=list)
    preview: list[dict[str, str]] = field(default_factory=list)  # [{role, text}]

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.summary.to_dict(),
            "messages": self.messages,
            "preview": self.preview,
        }
