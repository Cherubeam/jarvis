"""
Handles conversation persistence.
Saves conversations to JSON files with a future-proof schema (v1.0.0).
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.core.context_builder import ContextMetadata

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"


def generate_conversation_id() -> str:
    """Generate a unique conversation ID: conv_{YYYYMMDD}_{HHMMSS}_{6hex}."""
    now = datetime.now()
    hex_suffix = secrets.token_hex(3)  # 6 hex chars
    return f"conv_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}_{hex_suffix}"


def hash_content(text: str) -> str:
    """Return a truncated SHA-256 hash of text (first 16 hex chars)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_content(content) -> list[dict]:
    """Wrap string content in typed block array; pass-through if already a list."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    return [{"type": "text", "text": str(content)}]


def _extract_text_from_content(content: list[dict]) -> str:
    """Extract plain text from content blocks for API calls."""
    parts = []
    for block in content:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def migrate_conversation(data: dict) -> dict:
    """Migrate old conversation format to v1.0.0 schema at read time.

    Handles three known old formats:
    - v0 (no metrics): session_start, session_end, messages
    - v1 (metrics without latency): adds metrics without average_ttft_ms
    - v2 (metrics with latency): adds average_ttft_ms, average_latency_ms
    """
    if "schema_version" in data:
        if data["schema_version"] != SCHEMA_VERSION:
            logger.warning(
                "Unknown schema version %s (expected %s) in conversation %s",
                data["schema_version"],
                SCHEMA_VERSION,
                data.get("id", "unknown"),
            )
        return data

    migrated = {
        "schema_version": SCHEMA_VERSION,
        "id": None,
        "title": None,
        "topic": None,
        "tags": [],
        "session_start": data.get("session_start"),
        "session_end": data.get("session_end"),
        "model": None,
        "agent": None,
        "context": None,
        "metrics": {},
        "environment": None,
        "messages": [],
        "feedback": None,
        "metadata": {},
    }

    # Migrate metrics
    old_metrics = data.get("metrics")
    if old_metrics:
        migrated["metrics"] = {
            "total_prompt_tokens": old_metrics.get("total_prompt_tokens", 0),
            "total_completion_tokens": old_metrics.get("total_completion_tokens", 0),
            "total_tokens": old_metrics.get("total_tokens", 0),
            "total_cost_usd": old_metrics.get("total_cost_usd", 0.0),
            "total_cache_read_tokens": 0,
            "total_cache_write_tokens": 0,
            "total_thinking_tokens": 0,
            "request_count": old_metrics.get("request_count", 0),
            "average_ttft_ms": old_metrics.get("average_ttft_ms", 0.0),
            "average_latency_ms": old_metrics.get("average_latency_ms", 0.0),
            "metadata": {},
        }

    # Migrate messages
    for i, msg in enumerate(data.get("messages", []), start=1):
        content = msg.get("content", "")
        new_msg = {
            "id": f"msg_{i:03d}",
            "parent_id": None,
            "role": msg.get("role", "user"),
            "timestamp": msg.get("timestamp"),
            "content": _normalize_content(content),
            "usage": None,
            "latency": None,
            "stop_reason": None,
            "status": "completed",
            "error": None,
            "metadata": {},
        }

        # Migrate usage
        old_usage = msg.get("usage")
        if old_usage:
            new_msg["usage"] = {
                "prompt_tokens": old_usage.get("prompt_tokens", 0),
                "completion_tokens": old_usage.get("completion_tokens", 0),
                "total_tokens": old_usage.get("total_tokens", 0),
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "thinking_tokens": 0,
                "cost_usd": old_usage.get("cost_usd", 0.0),
                "metadata": {},
            }

        # Migrate latency
        old_latency = msg.get("latency")
        if old_latency:
            new_msg["latency"] = {
                "ttft_ms": old_latency.get("ttft_ms", 0.0),
                "total_ms": old_latency.get("total_ms", 0.0),
            }

        migrated["messages"].append(new_msg)

    return migrated


@dataclass
class SessionMetrics:
    """Aggregated token usage, costs, and latency for a session."""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0
    total_thinking_tokens: int = 0
    request_count: int = 0
    total_ttft_ms: float = 0.0
    total_latency_ms: float = 0.0
    history_tokens_per_turn: list[int] = field(default_factory=list)

    def add_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost_usd: float = 0.0,
        ttft_ms: float = 0.0,
        total_latency_ms: float = 0.0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        thinking_tokens: int = 0,
    ):
        """Add usage from a single request."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.total_cost_usd += cost_usd
        self.total_ttft_ms += ttft_ms
        self.total_latency_ms += total_latency_ms
        self.total_cache_read_tokens += cache_read_tokens
        self.total_cache_write_tokens += cache_write_tokens
        self.total_thinking_tokens += thinking_tokens
        self.request_count += 1

    def record_history_tokens(self, approx_tokens: int):
        """Record approximate history token count for the current turn."""
        self.history_tokens_per_turn.append(approx_tokens)

    @property
    def average_ttft_ms(self) -> float:
        """Average time to first token across all requests."""
        return self.total_ttft_ms / self.request_count if self.request_count > 0 else 0.0

    @property
    def average_latency_ms(self) -> float:
        """Average total latency across all requests."""
        return self.total_latency_ms / self.request_count if self.request_count > 0 else 0.0

    def to_dict(self) -> dict:
        result = {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_cache_read_tokens": self.total_cache_read_tokens,
            "total_cache_write_tokens": self.total_cache_write_tokens,
            "total_thinking_tokens": self.total_thinking_tokens,
            "request_count": self.request_count,
            "average_ttft_ms": self.average_ttft_ms,
            "average_latency_ms": self.average_latency_ms,
            "metadata": {},
        }
        if self.history_tokens_per_turn:
            result["history_tokens_per_turn"] = self.history_tokens_per_turn
        return result


class ConversationLogger:
    """Logs conversations to files for later review/learning."""

    def __init__(
        self,
        conversations_dir: Path,
        model_config: dict | None = None,
        agent_config: dict | None = None,
        context_snapshot: dict | None = None,
        environment: dict | None = None,
        context_metadata: "ContextMetadata | None" = None,
    ):
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.current_conversation: list[dict] = []
        self.session_start = datetime.now()
        self.metrics = SessionMetrics()
        self.conversation_id = generate_conversation_id()
        self._message_counter = 0

        # New schema fields
        self.model_config = model_config
        self.agent_config = agent_config
        self.context_snapshot = context_snapshot
        self.environment = environment
        self.context_metadata = context_metadata
        self.title: str | None = None
        self.topic: str | None = None
        self.tags: list[str] = []
        self.feedback: dict | None = None
        self.metadata: dict = {}
        self.utilization: list[dict] = []

    def set_title(self, title: str):
        """Set the conversation title."""
        self.title = title

    def set_topic(self, topic: str):
        """Set the conversation topic."""
        self.topic = topic

    def add_tag(self, tag: str):
        """Add a tag to the conversation."""
        if tag not in self.tags:
            self.tags.append(tag)

    def record_utilization(self, response_text: str, section_names: list[str]):
        """Check which context sections appear referenced in a response.

        Uses simple keyword matching as a heuristic — not perfect, but
        gives directional data on which sections contribute to responses.
        """
        text_lower = response_text.lower()
        # Keywords that suggest a section was utilized
        section_keywords: dict[str, list[str]] = {
            "soul": ["jarvis", "assistant"],
            "personal": ["marco", "personal", "family"],
            "professional": ["work", "career", "professional", "engineering"],
            "preferences": ["prefer", "style", "tone"],
            "focus": ["focus", "current", "priority"],
            "tasks": ["task", "todo", "things"],
            "projects": ["project", "jarvis", "repo"],
        }
        utilized = []
        for name in section_names:
            keywords = section_keywords.get(name, [name])
            if any(kw in text_lower for kw in keywords):
                utilized.append(name)
        self.utilization.append({
            "turn": self.metrics.request_count,
            "sections_loaded": section_names,
            "sections_utilized": utilized,
        })

    def set_feedback(self, overall_rating: int | None = None, helpful: bool | None = None, notes: str | None = None, **kwargs):
        """Set session-level feedback."""
        self.feedback = {
            "overall_rating": overall_rating,
            "helpful": helpful,
            "notes": notes,
            "metadata": kwargs,
        }

    def add_tool_messages(self, tool_messages: list[dict], agent_name: str | None = None) -> None:
        """Store tool-calling messages (assistant with tool_calls + tool results).

        Preserves tool_calls and tool_call_id fields so that
        get_messages_for_api() can reconstruct the full tool context.
        """
        for msg in tool_messages:
            self._message_counter += 1
            msg_id = f"msg_{self._message_counter:03d}"

            stored = {
                "id": msg_id,
                "parent_id": None,
                "role": msg["role"],
                "timestamp": datetime.now().isoformat(),
                "content": _normalize_content(msg.get("content") or ""),
                "usage": None,
                "latency": None,
                "stop_reason": None,
                "status": "completed",
                "error": None,
                "metadata": {},
            }

            # Tag assistant tool-call messages with the originating agent
            if agent_name and msg["role"] == "assistant":
                stored["agent"] = agent_name

            # Preserve tool_calls on assistant messages
            if "tool_calls" in msg:
                stored["tool_calls"] = msg["tool_calls"]

            # Preserve tool_call_id on tool result messages
            if "tool_call_id" in msg:
                stored["tool_call_id"] = msg["tool_call_id"]

            self.current_conversation.append(stored)

    def add_message(
        self,
        role: str,
        content,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        ttft_ms: float = 0.0,
        total_latency_ms: float = 0.0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        thinking_tokens: int = 0,
        stop_reason: str | None = None,
        status: str = "completed",
        error: dict | None = None,
        metadata: dict | None = None,
        agent_name: str | None = None,
    ):
        """Add a message to the current conversation with optional token usage, cost, and latency."""
        self._message_counter += 1
        msg_id = f"msg_{self._message_counter:03d}"

        message = {
            "id": msg_id,
            "parent_id": None,
            "role": role,
            "timestamp": datetime.now().isoformat(),
            "content": _normalize_content(content),
            "usage": None,
            "latency": None,
            "stop_reason": stop_reason,
            "status": status,
            "error": error,
            "metadata": metadata or {},
        }

        # Tag assistant messages with the originating agent
        if agent_name and role == "assistant":
            message["agent"] = agent_name

        # Add usage for assistant messages with token data
        if role == "assistant" and total_tokens > 0:
            message["usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_write_tokens": cache_write_tokens,
                "thinking_tokens": thinking_tokens,
                "cost_usd": cost_usd,
                "metadata": {},
            }
            # Add latency metrics if available
            if ttft_ms > 0 or total_latency_ms > 0:
                message["latency"] = {
                    "ttft_ms": ttft_ms,
                    "total_ms": total_latency_ms,
                }
            self.metrics.add_usage(
                prompt_tokens, completion_tokens, total_tokens, cost_usd,
                ttft_ms, total_latency_ms,
                cache_read_tokens, cache_write_tokens, thinking_tokens,
            )

        self.current_conversation.append(message)

    def save(self):
        """Save the current conversation to a file."""
        if not self.current_conversation:
            return

        filename = self.session_start.strftime("%Y-%m-%d_%H-%M-%S.json")
        year_dir = self.conversations_dir / str(self.session_start.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        filepath = year_dir / filename

        # Enrich context snapshot with token metadata
        context = self.context_snapshot
        if context and self.context_metadata:
            context = {**context}
            # Add approx_tokens to each file entry
            section_tokens = {
                s.name: s.approx_tokens
                for s in self.context_metadata.sections
            }
            context["system_prompt_approx_tokens"] = self.context_metadata.total_approx_tokens
            context["section_breakdown"] = [
                {"name": s.name, "approx_tokens": s.approx_tokens, "size_bytes": s.size_bytes}
                for s in self.context_metadata.sections
            ]
            if self.utilization:
                context["utilization"] = self.utilization

        data = {
            "schema_version": SCHEMA_VERSION,
            "id": self.conversation_id,
            "title": self.title,
            "topic": self.topic,
            "tags": self.tags,
            "session_start": self.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "model": self.model_config,
            "agent": self.agent_config,
            "context": context,
            "metrics": self.metrics.to_dict(),
            "environment": self.environment,
            "messages": self.current_conversation,
            "feedback": self.feedback,
            "metadata": self.metadata,
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

            # Print context breakdown if available
            if self.context_metadata:
                pcts = self.context_metadata.section_percentages()
                if pcts:
                    parts = [f"{name}: {pct:.0f}%" for name, pct in pcts.items()]
                    print(
                        f"  System prompt: ~{self.context_metadata.total_approx_tokens:,} tokens "
                        f"({', '.join(parts)})"
                    )

                # Print history growth if tracked
                if m.history_tokens_per_turn:
                    last_history = m.history_tokens_per_turn[-1]
                    print(f"  History: ~{last_history:,} tokens (turn {m.request_count})")

            # Print utilization summary
            if self.utilization:
                all_loaded = set()
                all_utilized = set()
                for entry in self.utilization:
                    all_loaded.update(entry["sections_loaded"])
                    all_utilized.update(entry["sections_utilized"])
                print(
                    f"  Context utilized: {', '.join(sorted(all_utilized)) or 'none'} "
                    f"({len(all_utilized)}/{len(all_loaded)} sections referenced in responses)"
                )

    def get_messages_for_api(self) -> list[dict]:
        """Return messages in the format the API expects.

        Regular messages get {role, content}. Tool-calling assistant messages
        include tool_calls and set content to None when empty. Tool result
        messages include tool_call_id.
        """
        result = []
        for m in self.current_conversation:
            content = m["content"]
            # Extract text from content blocks
            if isinstance(content, list):
                text = _extract_text_from_content(content)
            else:
                text = content

            api_msg: dict = {"role": m["role"], "content": text}

            # Preserve tool_calls on assistant messages
            if "tool_calls" in m:
                api_msg["tool_calls"] = m["tool_calls"]
                # API requires content=None when tool_calls present and no text
                if not text:
                    api_msg["content"] = None

            # Preserve tool_call_id on tool result messages
            if "tool_call_id" in m:
                api_msg["tool_call_id"] = m["tool_call_id"]

            result.append(api_msg)
        return result

    @staticmethod
    def load(filepath: str | Path) -> dict:
        """Load a conversation file with read-time migration for old formats."""
        filepath = Path(filepath)
        with open(filepath) as f:
            data = json.load(f)
        return migrate_conversation(data)
