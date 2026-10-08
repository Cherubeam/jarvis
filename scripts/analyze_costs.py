"""Analyze costs per conversation type, and measure native JARVIS use.

Cost tables classify conversations by source, model, and length, then
aggregate cost/token/latency metrics per group. The usage reports (AON-01
measurement) count only native sessions, not imports:

- sessions: native sessions per ISO week and front end (environment.client)
- spend: native spend per month, split by usage_source (billed, estimated, legacy)
- caching: billed turns per model with cache-read share, the TOK caching baseline

Run scripts/backfill_billed_usage.py first, or recent turns stay estimated.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any

from packages.core.memory import migrate_conversation
from packages.core.pricing import format_cost
from packages.core.settings import load_config


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


def classify_source(conversation: dict[str, Any]) -> str:
    """Classify conversation source from metadata.import_source, else from tags (older imports)."""
    import_source = (conversation.get("metadata") or {}).get("import_source")
    if import_source:
        return f"imported/{import_source}"
    tags = conversation.get("tags", [])
    if "imported" in tags:
        if "chatgpt" in tags:
            return "imported/chatgpt"
        if "claude" in tags:
            return "imported/claude"
        return "imported/other"
    return "native"


def classify_model(conversation: dict[str, Any]) -> str:
    """Extract model ID from conversation."""
    model = conversation.get("model")
    if isinstance(model, dict):
        model_id: str = model.get("id", "unknown")
        return model_id
    return "unknown"


def classify_length(conversation: dict[str, Any]) -> str:
    """Classify conversation by message count."""
    msg_count = len(conversation.get("messages", []))
    if msg_count <= 3:
        return "short (1-3)"
    elif msg_count <= 10:
        return "medium (4-10)"
    else:
        return "long (11+)"


def aggregate_conversation(stats: GroupStats, conversation: dict[str, Any]) -> None:
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


def is_native(conversation: dict[str, Any]) -> bool:
    """A JARVIS session (CLI or GUI), not an imported conversation."""
    return classify_source(conversation) == "native"


def has_user_message(conversation: dict[str, Any]) -> bool:
    return any(m.get("role") == "user" for m in conversation.get("messages", []))


def iso_week(timestamp: str) -> str:
    """'2026-10-08T21:30:10' -> '2026-W41'."""
    year, week, _ = datetime.fromisoformat(timestamp).isocalendar()
    return f"{year}-W{week:02d}"


def assistant_turns(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    """Assistant messages that carry usage."""
    return [m for m in conversation.get("messages", []) if m.get("role") == "assistant" and m.get("usage")]


def usage_source(message: dict[str, Any]) -> str:
    """billed | estimated | legacy (logged before usage_source existed, 2026-09-29)."""
    source = (message.get("metadata") or {}).get("usage_source")
    return source if source in ("billed", "estimated") else "legacy"


def turn_model(conversation: dict[str, Any], message: dict[str, Any]) -> str:
    """Model that answered. Logged per turn since 2026-10-08; before that, the session's
    model with a "(session)" mark, which is wrong for pinned agents such as substack_publisher."""
    model = (message.get("metadata") or {}).get("model")
    if model:
        return str(model)
    return f"{classify_model(conversation)} (session)"


def sessions_by_week(conversations: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Native sessions with at least one user message, per ISO week and front end."""
    weeks: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for conv in conversations:
        if not is_native(conv) or not has_user_message(conv):
            continue
        client = (conv.get("environment") or {}).get("client") or "unknown"
        weeks[iso_week(conv["session_start"])][client] += 1
    return {week: dict(clients) for week, clients in weeks.items()}


@dataclass
class SpendStats:
    """Native spend in one month, split by where the numbers come from."""

    billed: float = 0.0
    estimated: float = 0.0
    legacy: float = 0.0
    turns: int = 0

    @property
    def total(self) -> float:
        return self.billed + self.estimated + self.legacy


def spend_by_month(conversations: list[dict[str, Any]]) -> dict[str, SpendStats]:
    """Native spend per month (from the turn's timestamp), by usage_source."""
    months: dict[str, SpendStats] = defaultdict(SpendStats)
    for conv in conversations:
        if not is_native(conv):
            continue
        for msg in assistant_turns(conv):
            stats = months[str(msg.get("timestamp") or conv["session_start"])[:7]]
            cost = float(msg["usage"].get("cost_usd") or 0.0)
            setattr(stats, usage_source(msg), getattr(stats, usage_source(msg)) + cost)
            stats.turns += 1
    return dict(months)


@dataclass
class CacheStats:
    """Billed turns of one model: how much of the prompt came from the cache."""

    turns: int = 0
    prompt_tokens: int = 0
    cache_read_tokens: int = 0
    cost: float = 0.0
    later_turns: int = 0  # billed turns after the session's first turn
    later_turns_with_reads: int = 0

    @property
    def read_share(self) -> float:
        return self.cache_read_tokens / self.prompt_tokens if self.prompt_tokens else 0.0


def caching_by_model(conversations: list[dict[str, Any]]) -> dict[str, CacheStats]:
    """Cache reads per model over billed native turns (estimates carry no cache fields)."""
    models: dict[str, CacheStats] = defaultdict(CacheStats)
    for conv in conversations:
        if not is_native(conv):
            continue
        for index, msg in enumerate(assistant_turns(conv)):
            if usage_source(msg) != "billed":
                continue
            usage = msg["usage"]
            stats = models[turn_model(conv, msg)]
            stats.turns += 1
            stats.prompt_tokens += int(usage.get("prompt_tokens") or 0)
            stats.cache_read_tokens += int(usage.get("cache_read_tokens") or 0)
            stats.cost += float(usage.get("cost_usd") or 0.0)
            if index > 0:
                stats.later_turns += 1
                stats.later_turns_with_reads += int(bool(usage.get("cache_read_tokens")))
    return dict(models)


def _cost(value: float) -> str:
    return format_cost(value) if value else "–"


def format_sessions(weeks: dict[str, dict[str, int]]) -> str:
    clients = sorted({c for counts in weeks.values() for c in counts})
    lines = [
        "### Native sessions per week",
        "",
        "| Week | " + " | ".join(clients) + " | Total |",
        "| --- |" + " --- |" * (len(clients) + 1),
    ]
    for week in sorted(weeks):
        counts = weeks[week]
        cells = " | ".join(str(counts.get(c, 0)) for c in clients)
        lines.append(f"| {week} | {cells} | {sum(counts.values())} |")
    total = sum(sum(c.values()) for c in weeks.values())
    lines += ["", f"{total} sessions in {len(weeks)} active weeks (sessions with at least one message)."]
    return "\n".join(lines)


def format_spend(months: dict[str, SpendStats]) -> str:
    lines = [
        "### Native spend per month",
        "",
        "| Month | Turns | Billed | Estimated | Legacy | Total |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for month in sorted(months):
        m = months[month]
        lines.append(
            f"| {month} | {m.turns} | {_cost(m.billed)} | {_cost(m.estimated)} | {_cost(m.legacy)} | {_cost(m.total)} |"
        )
    lines += [
        "",
        "Billed = OpenRouter's billing record. Estimated = streamed turn not yet reconciled (run "
        "scripts/backfill_billed_usage.py). Legacy = logged before 2026-09-29, mostly streamed estimates.",
    ]
    return "\n".join(lines)


def format_caching(models: dict[str, CacheStats]) -> str:
    lines = [
        "### Prompt caching (billed native turns)",
        "",
        "| Model | Turns | Prompt tokens | Cache reads | Read share | Turns 2+ with reads | Cost |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model in sorted(models, key=lambda k: models[k].cost, reverse=True):
        c = models[model]
        lines.append(
            f"| {model} | {c.turns} | {c.prompt_tokens:,} | {c.cache_read_tokens:,} | {c.read_share:.0%} | "
            f"{c.later_turns_with_reads}/{c.later_turns} | {_cost(c.cost)} |"
        )
    if not models:
        lines.append("| (no billed turns yet) | | | | | | |")
    lines += [
        "",
        "Cache writes aren't in OpenRouter's billing record, so they show only in the cost. "
        '"(session)" = turn logged before the per-turn model field (2026-10-08); pinned agents may differ.',
    ]
    return "\n".join(lines)


def load_conversations(conversations_dir: Path) -> list[dict[str, Any]]:
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
    conversations: list[dict[str, Any]],
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
        latency_str = f"{stats.avg_latency_ms:.0f} ms" if stats.latency_count else "n/a"
        lines.append(
            f"| {label} | {stats.count} | "
            f"{format_cost(stats.total_cost)} | "
            f"{format_cost(stats.avg_cost)} | "
            f"{stats.avg_tokens:,} | "
            f"{latency_str} |"
        )

    return "\n".join(lines)


USAGE_REPORTS = ["sessions", "spend", "caching"]


def format_usage_report(conversations: list[dict[str, Any]], report: str) -> str:
    if report == "sessions":
        return format_sessions(sessions_by_week(conversations))
    if report == "spend":
        return format_spend(spend_by_month(conversations))
    if report == "caching":
        return format_caching(caching_by_model(conversations))
    raise ValueError(f"Unknown report: {report}. Use: {USAGE_REPORTS}")


def format_full_report(
    conversations: list[dict[str, Any]],
    group_types: list[str],
) -> str:
    """Generate the full report with all requested groupings."""
    lines = [
        "# Cost Analysis Report",
        "",
        f"**Total conversations**: {len(conversations)}",
        "",
    ]

    total_cost = sum(c.get("metrics", {}).get("total_cost_usd", 0.0) for c in conversations)
    lines.append(f"**Total cost**: {format_cost(total_cost)}")
    lines.append("")

    for group_by in group_types:
        if group_by in USAGE_REPORTS:
            lines.append(format_usage_report(conversations, group_by))
        else:
            lines.append(format_table(analyze_by_group(conversations, group_by), group_by))
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze costs per conversation type.")
    parser.add_argument(
        "--conversations-dir",
        default=None,
        help="Path to conversations directory, relative to the project root "
        "(default: paths.conversations_dir from config/).",
    )
    parser.add_argument(
        "--by",
        choices=["source", "model", "length", *USAGE_REPORTS, "all"],
        default="all",
        help="Cost table by source/model/length, or a usage report (sessions, spend, caching).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write report to file instead of stdout.",
    )

    args = parser.parse_args(argv)
    conversations_dir = PROJECT_ROOT / (args.conversations_dir or load_config(PROJECT_ROOT).paths.conversations_dir)

    if not conversations_dir.exists():
        print(f"Error: Conversations directory not found: {conversations_dir}")
        return 1

    conversations = load_conversations(conversations_dir)
    if not conversations:
        print("No conversations found.")
        return 1

    if args.by == "all":
        group_types = ["source", "model", "length", *USAGE_REPORTS]
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
