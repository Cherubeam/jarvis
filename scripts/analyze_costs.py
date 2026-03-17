"""Analyze costs per conversation type.

Classifies conversations by source, model, and length, then
aggregates cost/token/latency metrics per group.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.memory import migrate_conversation
from packages.core.pricing import format_cost


@dataclass
class GroupStats:
    """Aggregated stats for a conversation group."""

    count: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    latency_count: int = 0  # conversations with latency data

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.count if self.count else 0.0

    @property
    def avg_tokens(self) -> int:
        return self.total_tokens // self.count if self.count else 0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.latency_count if self.latency_count else 0.0


def classify_source(conversation: dict) -> str:
    """Classify conversation source from tags."""
    tags = conversation.get("tags", [])
    if "imported" in tags:
        if "chatgpt" in tags:
            return "imported/chatgpt"
        if "claude" in tags:
            return "imported/claude"
        return "imported/other"
    return "native"


def classify_model(conversation: dict) -> str:
    """Extract model ID from conversation."""
    model = conversation.get("model")
    if isinstance(model, dict):
        return model.get("id", "unknown")
    return "unknown"


def classify_length(conversation: dict) -> str:
    """Classify conversation by message count."""
    msg_count = len(conversation.get("messages", []))
    if msg_count <= 3:
        return "short (1-3)"
    elif msg_count <= 10:
        return "medium (4-10)"
    else:
        return "long (11+)"


def aggregate_conversation(stats: GroupStats, conversation: dict) -> None:
    """Add a conversation's metrics to a group."""
    stats.count += 1
    metrics = conversation.get("metrics", {})
    stats.total_cost += metrics.get("total_cost_usd", 0.0)
    stats.total_tokens += metrics.get("total_tokens", 0)
    stats.total_prompt_tokens += metrics.get("total_prompt_tokens", 0)
    stats.total_completion_tokens += metrics.get("total_completion_tokens", 0)

    avg_latency = metrics.get("average_latency_ms", 0.0)
    if avg_latency > 0:
        stats.total_latency_ms += avg_latency
        stats.latency_count += 1


def load_conversations(conversations_dir: Path) -> list[dict]:
    """Load and migrate all conversation files."""
    conversations = []
    for json_file in sorted(conversations_dir.rglob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
            conversations.append(migrate_conversation(data))
        except (json.JSONDecodeError, OSError):
            continue
    return conversations


def analyze_by_group(
    conversations: list[dict],
    group_by: str,
) -> dict[str, GroupStats]:
    """Group conversations and aggregate stats.

    Args:
        conversations: Migrated conversation dicts.
        group_by: One of "source", "model", "length".

    Returns:
        Dict mapping group label to aggregated stats.
    """
    classifiers = {
        "source": classify_source,
        "model": classify_model,
        "length": classify_length,
    }
    classifier = classifiers.get(group_by)
    if not classifier:
        raise ValueError(f"Unknown group_by: {group_by}. Use: {list(classifiers)}")

    groups: dict[str, GroupStats] = defaultdict(GroupStats)
    for conv in conversations:
        label = classifier(conv)
        aggregate_conversation(groups[label], conv)

    return dict(groups)


def format_table(groups: dict[str, GroupStats], group_by: str) -> str:
    """Format grouped stats as a markdown table."""
    lines = [
        f"### Costs by {group_by}",
        "",
        f"| {group_by.title()} | Count | Total Cost | Avg Cost | Avg Tokens | Avg Latency |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for label in sorted(groups, key=lambda k: groups[k].total_cost, reverse=True):
        stats = groups[label]
        latency_str = (
            f"{stats.avg_latency_ms:.0f} ms" if stats.latency_count else "n/a"
        )
        lines.append(
            f"| {label} | {stats.count} | "
            f"{format_cost(stats.total_cost)} | "
            f"{format_cost(stats.avg_cost)} | "
            f"{stats.avg_tokens:,} | "
            f"{latency_str} |"
        )

    return "\n".join(lines)


def format_full_report(
    conversations: list[dict],
    group_types: list[str],
) -> str:
    """Generate the full report with all requested groupings."""
    lines = [
        "# Cost Analysis Report",
        "",
        f"**Total conversations**: {len(conversations)}",
        "",
    ]

    total_cost = sum(
        c.get("metrics", {}).get("total_cost_usd", 0.0) for c in conversations
    )
    lines.append(f"**Total cost**: {format_cost(total_cost)}")
    lines.append("")

    for group_by in group_types:
        groups = analyze_by_group(conversations, group_by)
        lines.append(format_table(groups, group_by))
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze costs per conversation type."
    )
    parser.add_argument(
        "--conversations-dir",
        default="data/conversations",
        help="Path to conversations directory.",
    )
    parser.add_argument(
        "--by",
        choices=["source", "model", "length", "all"],
        default="all",
        help="Group conversations by this dimension.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write report to file instead of stdout.",
    )

    args = parser.parse_args()
    conversations_dir = PROJECT_ROOT / args.conversations_dir

    if not conversations_dir.exists():
        print(f"Error: Conversations directory not found: {conversations_dir}")
        return 1

    conversations = load_conversations(conversations_dir)
    if not conversations:
        print("No conversations found.")
        return 1

    if args.by == "all":
        group_types = ["source", "model", "length"]
    else:
        group_types = [args.by]

    report = format_full_report(conversations, group_types)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
