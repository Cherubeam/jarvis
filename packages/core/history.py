"""
Session history management — trim and summarize conversation history to
reduce token costs.

Long sessions accumulate full conversation history including all tool call
results. Tool results (vault reads, searches, fetches) are the biggest
bloat contributors but are rarely needed verbatim after the LLM has
processed them. This module provides two complementary strategies:

1. ``trim_tool_results`` — truncates old tool result content (zero API cost).
2. ``summarize_history`` — compresses old conversation turns into a summary
   using a cheap/fast model (one LLM call when threshold is exceeded).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

_TOOL_RESULT_SUMMARY_LEN = 200
_KEEP_RECENT_MESSAGES = 6  # ~2 full user/assistant exchanges + their tool results
_SUMMARY_MARKER = "[JARVIS_SUMMARY]"
_DEFAULT_TOKEN_THRESHOLD = 40_000
_DEFAULT_KEEP_RECENT_FOR_SUMMARY = 10


def trim_tool_results(
    history: list[dict],
    keep_recent: int = _KEEP_RECENT_MESSAGES,
) -> list[dict]:
    """Trim tool result content from older messages to reduce token usage.

    Recent messages (last ``keep_recent``) are preserved intact. For older
    messages with role "tool", content longer than the summary threshold is
    truncated. Non-tool messages are never modified.

    Args:
        history: List of message dicts (user, assistant, tool).
        keep_recent: Number of recent messages to preserve intact.

    Returns:
        A new list with old tool results truncated.
    """
    if len(history) <= keep_recent:
        return history

    trimmed: list[dict] = []
    cutoff = len(history) - keep_recent

    for i, msg in enumerate(history):
        if i < cutoff and msg.get("role") == "tool":
            content = msg.get("content", "")
            if len(content) > _TOOL_RESULT_SUMMARY_LEN:
                trimmed.append(
                    {
                        **msg,
                        "content": content[:_TOOL_RESULT_SUMMARY_LEN] + "\n[... truncated]",
                    }
                )
                continue
        trimmed.append(msg)

    return trimmed


def _approx_tokens(messages: list[dict]) -> int:
    """Estimate token count using the bytes/4 heuristic."""
    return sum(len(str(m.get("content", "")).encode("utf-8")) for m in messages) // 4


def _format_messages_for_summary(messages: list[dict]) -> str:
    """Format messages into a condensed text representation for the summarizer."""
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", ""))

        if role == "tool":
            tool_id = msg.get("tool_call_id", "unknown")
            preview = content[:100].replace("\n", " ")
            lines.append(f"[tool result for {tool_id}]: {preview}...")
        elif role == "assistant" and msg.get("tool_calls"):
            names = [tc.get("function", {}).get("name", "?") for tc in msg["tool_calls"]]
            lines.append(f"[assistant called tools: {', '.join(names)}]")
        else:
            lines.append(f"[{role}]: {content}")

    return "\n".join(lines)


_SUMMARIZATION_PROMPT = r"""\  # pragma: no mutate
Summarize this conversation history concisely. Preserve:
- Key decisions made by the user
- User preferences and corrections expressed
- Important facts, names, and context established
- What tasks were completed or are in progress

Do NOT include tool call details or raw tool output. Focus on the semantic content.

History:
{history_text}"""


def summarize_history(
    history: list[dict],
    client: LLMClient,
    model_id: str,
    token_threshold: int = _DEFAULT_TOKEN_THRESHOLD,
    keep_recent: int = _DEFAULT_KEEP_RECENT_FOR_SUMMARY,
) -> list[dict]:
    """Compress old conversation turns into a summary to reduce token costs.

    Uses a cheap/fast model to produce the summary. Detects prior summaries
    to avoid re-summarizing every turn (summarize-once pattern).

    Args:
        history: List of message dicts (user, assistant, tool).
        client: LLMClient instance for the summarization call.
        model_id: Pre-resolved model ID for the fast/cheap model.
        token_threshold: Approximate token count above which to trigger.
        keep_recent: Number of recent messages to preserve intact.

    Returns:
        A new list with old messages replaced by a summary, or the
        original list if summarization was not needed or failed.
    """
    if len(history) <= keep_recent:
        return history

    # Detect prior summary and calculate tokens for new content only.
    summary_idx = None
    for i, msg in enumerate(history):
        content = str(msg.get("content", ""))
        if msg.get("role") == "assistant" and content.startswith(_SUMMARY_MARKER):
            summary_idx = i
            break

    if summary_idx is not None:
        new_content = history[summary_idx + 1 :]
        if _approx_tokens(new_content) < token_threshold:
            return history
    else:
        if _approx_tokens(history) < token_threshold:
            return history

    # Find a safe split point that lands on a user message.
    split_idx = len(history) - keep_recent
    while split_idx < len(history) and history[split_idx]["role"] != "user":
        split_idx += 1

    if split_idx >= len(history):
        return history

    old_messages = history[:split_idx]
    recent_messages = history[split_idx:]

    history_text = _format_messages_for_summary(old_messages)
    prompt = _SUMMARIZATION_PROMPT.format(history_text=history_text)

    try:
        response = client.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are a conversation summarizer. Be concise.",
                },  # pragma: no mutate
                {"role": "user", "content": prompt},
            ],
            model=model_id,
        )
        summary_text = response.choices[0].message.content
    except Exception:
        logger.warning("History summarization failed; returning original history", exc_info=True)  # pragma: no mutate
        return history

    summary_msg = {
        "role": "assistant",
        "content": f"{_SUMMARY_MARKER} Here is a summary of our conversation so far:\n{summary_text}",
    }
    return [summary_msg, *recent_messages]
