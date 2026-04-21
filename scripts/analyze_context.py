"""Analyze context utilization across conversations.

Measures whether assistant responses reference loaded context files,
helping identify which context files are most/least useful.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.memory import migrate_conversation


@dataclass
class ContextFileStats:
    """Aggregated stats for a single context file."""

    path: str
    times_loaded: int = 0
    total_size_bytes: int = 0
    conversations_referenced: int = 0
    total_conversations_loaded: int = 0

    @property
    def avg_size_bytes(self) -> int:
        return self.total_size_bytes // self.times_loaded if self.times_loaded else 0

    @property
    def utilization_pct(self) -> float:
        if self.total_conversations_loaded == 0:
            return 0.0
        return (self.conversations_referenced / self.total_conversations_loaded) * 100


@dataclass
class AnalysisResult:
    """Complete context utilization analysis."""

    total_conversations: int = 0
    conversations_with_context: int = 0
    file_stats: dict[str, ContextFileStats] = field(default_factory=dict)
    total_context_tokens_estimate: int = 0
    total_prompt_tokens: int = 0

    @property
    def context_overhead_pct(self) -> float:
        if self.total_prompt_tokens == 0:
            return 0.0
        return (self.total_context_tokens_estimate / self.total_prompt_tokens) * 100


def extract_keywords(text: str, min_length: int = 4) -> set[str]:
    """Extract meaningful keywords from text for matching.

    Splits on non-alphanumeric boundaries, lowercases, and filters
    short/common words.
    """
    stop_words = {
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "will",
        "your",
        "they",
        "them",
        "their",
        "what",
        "when",
        "where",
        "which",
        "while",
        "about",
        "after",
        "before",
        "between",
        "each",
        "some",
        "such",
        "than",
        "then",
        "these",
        "those",
        "into",
        "also",
        "just",
        "like",
        "more",
        "most",
        "only",
        "other",
        "over",
        "very",
        "well",
        "would",
        "could",
        "should",
        "does",
        "don't",
        "doesn",
        "true",
        "false",
        "none",
        "null",
        "type",
        "text",
    }
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if len(w) >= min_length and w not in stop_words}


def check_context_referenced(
    context_keywords: set[str],
    response_text: str,
    threshold: int = 3,
) -> bool:
    """Check if enough context keywords appear in the response.

    Args:
        context_keywords: Keywords extracted from the context file.
        response_text: The assistant's response text.
        threshold: Minimum keyword matches to count as referenced.
    """
    if not context_keywords:
        return False
    response_lower = response_text.lower()
    matches = sum(1 for kw in context_keywords if kw in response_lower)
    return matches >= threshold


def _extract_assistant_text(conversation: dict) -> str:
    """Extract all assistant response text from a conversation."""
    parts = []
    for msg in conversation.get("messages", []):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return " ".join(parts)


def _estimate_context_tokens(size_bytes: int) -> int:
    """Rough estimate: ~4 chars per token for English text."""
    return size_bytes // 4


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


def analyze_context_utilization(
    conversations: list[dict],
    context_dir: Path | None = None,
) -> AnalysisResult:
    """Analyze how context files are utilized across conversations.

    Args:
        conversations: List of migrated conversation dicts.
        context_dir: Optional path to context directory for reading file content.
    """
    result = AnalysisResult()
    result.total_conversations = len(conversations)

    # Cache for context file content keywords
    context_content_cache: dict[str, set[str]] = {}

    for conv in conversations:
        context = conv.get("context")
        if not context or not isinstance(context, dict):
            continue

        files_loaded = context.get("files_loaded", [])
        if not files_loaded:
            continue

        result.conversations_with_context += 1
        assistant_text = _extract_assistant_text(conv)

        # Accumulate prompt token estimate
        metrics = conv.get("metrics", {})
        result.total_prompt_tokens += metrics.get("total_prompt_tokens", 0)

        for file_info in files_loaded:
            file_path = file_info.get("path", "")
            size_bytes = file_info.get("size_bytes", 0)

            if file_path not in result.file_stats:
                result.file_stats[file_path] = ContextFileStats(path=file_path)

            stats = result.file_stats[file_path]
            stats.times_loaded += 1
            stats.total_size_bytes += size_bytes
            stats.total_conversations_loaded += 1
            result.total_context_tokens_estimate += _estimate_context_tokens(size_bytes)

            # Try to check if this context file was referenced in responses
            if context_dir and assistant_text:
                if file_path not in context_content_cache:
                    full_path = PROJECT_ROOT / file_path
                    if not full_path.exists() and context_dir:
                        # Try relative to context_dir
                        name = Path(file_path).name
                        full_path = context_dir / name
                    if full_path.exists():
                        try:
                            content = full_path.read_text(encoding="utf-8")
                            context_content_cache[file_path] = extract_keywords(content)
                        except OSError:
                            context_content_cache[file_path] = set()
                    else:
                        context_content_cache[file_path] = set()

                keywords = context_content_cache.get(file_path, set())
                if check_context_referenced(keywords, assistant_text):
                    stats.conversations_referenced += 1

    return result


def format_report(result: AnalysisResult) -> str:
    """Format the analysis result as a markdown report."""
    lines = [
        "# Context Utilization Report",
        "",
        "## Summary",
        "",
        f"- **Total conversations**: {result.total_conversations}",
        f"- **Conversations with context**: {result.conversations_with_context}",
        f"- **Context coverage**: {result.conversations_with_context / result.total_conversations * 100:.1f}%"
        if result.total_conversations
        else "- **Context coverage**: N/A",
        f"- **Context overhead**: {result.context_overhead_pct:.1f}% of prompt tokens (estimated)",
        "",
    ]

    if result.file_stats:
        lines.extend(
            [
                "## Per-File Utilization",
                "",
                "| File | Times Loaded | Avg Size | Conversations Referenced | Utilization |",
                "| --- | --- | --- | --- | --- |",
            ]
        )

        for stats in sorted(
            result.file_stats.values(), key=lambda s: s.utilization_pct, reverse=True
        ):
            lines.append(
                f"| {stats.path} | {stats.times_loaded} | "
                f"{stats.avg_size_bytes:,} bytes | "
                f"{stats.conversations_referenced}/{stats.total_conversations_loaded} | "
                f"{stats.utilization_pct:.0f}% |"
            )

        lines.append("")

    lines.extend(
        [
            "## Context Loading Summary",
            "",
            f"- **Unique context files**: {len(result.file_stats)}",
            f"- **Est. context tokens**: {result.total_context_tokens_estimate:,}",
            f"- **Total prompt tokens**: {result.total_prompt_tokens:,}",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze context utilization across conversations."
    )
    parser.add_argument(
        "--conversations-dir",
        default="data/conversations",
        help="Path to conversations directory.",
    )
    parser.add_argument(
        "--context-dir",
        default="data/context",
        help="Path to context files directory (for keyword extraction).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write report to file instead of stdout.",
    )

    args = parser.parse_args()
    conversations_dir = PROJECT_ROOT / args.conversations_dir
    context_dir = PROJECT_ROOT / args.context_dir

    if not conversations_dir.exists():
        print(f"Error: Conversations directory not found: {conversations_dir}")
        return 1

    conversations = load_conversations(conversations_dir)
    if not conversations:
        print("No conversations found.")
        return 1

    result = analyze_context_utilization(
        conversations, context_dir if context_dir.exists() else None
    )
    report = format_report(result)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to {output_path}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
