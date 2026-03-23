"""
Session history management — trim old tool results to reduce token costs.

Delegate agent sessions accumulate full conversation history including all
tool call results. Tool results (vault reads, searches, fetches) are the
biggest bloat contributors but are rarely needed verbatim after the LLM
has processed them. This module truncates old tool result content while
preserving recent messages intact.
"""

_TOOL_RESULT_SUMMARY_LEN = 200
_KEEP_RECENT_MESSAGES = 6  # ~2 full user/assistant exchanges + their tool results


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
                trimmed.append({
                    **msg,
                    "content": content[:_TOOL_RESULT_SUMMARY_LEN] + "\n[... truncated]",
                })
                continue
        trimmed.append(msg)

    return trimmed
