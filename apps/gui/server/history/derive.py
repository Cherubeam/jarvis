"""Pure extraction helpers over a migrated conversation JSON.

Every helper takes the raw dict/list from the file (post-migration) and
returns a primitive. No I/O. Defensive against missing keys so legacy
and imported conversations don't crash the index.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

# If packages/core/tools/delegate.py ever renames the tool, update this.
HANDOFF_TOOL_NAME = "delegate_to_agent"

_TITLE_MAX = 80


def _user_messages(messages: Iterable[dict]) -> list[str]:
    """Collect user-role text bodies. Handles both string and block-list content."""
    out: list[str] = []
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content", "")
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            # Content blocks: pick text blocks, concatenate.
            pieces = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") in (None, "text")
            ]
            if pieces:
                out.append(" ".join(p for p in pieces if p))
    return out


def title_from_messages(messages: Iterable[dict], max_len: int = _TITLE_MAX) -> str:
    """Derive a conversation title from the first user message.

    Strips newlines and leading slashes. Truncates with `…`. Fallback
    when there are no user messages: `"(no messages)"`.
    """
    users = _user_messages(messages)
    if not users:
        return "(no messages)"
    raw = users[0].strip()
    if not raw:
        return "(no messages)"
    # Collapse whitespace + newlines to a single space.
    flat = " ".join(raw.split())
    if len(flat) > max_len:
        flat = flat[: max_len - 1].rstrip() + "…"
    return flat


def _tool_calls(messages: Iterable[dict]) -> Iterable[dict]:
    """Yield each tool_call dict on any assistant message (flat)."""
    for m in messages:
        if m.get("role") != "assistant":
            continue
        for tc in m.get("tool_calls") or []:
            if isinstance(tc, dict):
                yield tc


def handoff_count(messages: Iterable[dict]) -> int:
    """Count `delegate_to_agent` invocations — the only on-disk marker of a handoff."""
    n = 0
    for tc in _tool_calls(messages):
        fn = (tc.get("function") or {}).get("name")
        if fn == HANDOFF_TOOL_NAME:
            n += 1
    return n


def tools_used(messages: Iterable[dict]) -> list[str]:
    """Unique tool names invoked, excluding the handoff tool. Stable order."""
    seen: set[str] = set()
    out: list[str] = []
    for tc in _tool_calls(messages):
        fn = (tc.get("function") or {}).get("name")
        if not fn or fn == HANDOFF_TOOL_NAME or fn in seen:
            continue
        seen.add(fn)
        out.append(fn)
    return sorted(out)


def tool_call_count(messages: Iterable[dict]) -> int:
    """Total tool invocations (including the handoff tool)."""
    return sum(1 for _ in _tool_calls(messages))


def agents_seen(messages: Iterable[dict]) -> list[str]:
    """Unique agent names from assistant messages' top-level `agent` field.

    Legacy CLI runs and imported conversations may not have this field —
    return [] in that case. Stable order (insertion).
    """
    seen: set[str] = set()
    out: list[str] = []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        name = m.get("agent")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def dominant_agent(agents: list[str]) -> str:
    """First non-JARVIS agent if present, else JARVIS, else empty."""
    if not agents:
        return ""
    for a in agents:
        if a and a != "JARVIS":
            return a
    return agents[0]


def duration_ms(session_start: str | None, session_end: str | None) -> int:
    """ISO timestamps → duration in ms. 0 if either is missing or invalid."""
    if not session_start or not session_end:
        return 0
    try:
        start = datetime.fromisoformat(session_start)
        end = datetime.fromisoformat(session_end)
    except (ValueError, TypeError):
        return 0
    return max(0, int((end - start).total_seconds() * 1000))


def duration_str(ms: int) -> str:
    """Pretty duration: '8m 12s', '1h 14m', '—'."""
    if ms <= 0:
        return "—"
    total_s = ms // 1000
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _text_from_content(content: Any) -> str:
    """Flatten content (string or block list) to a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") in (None, "text")
        )
    return ""


def preview_messages(
    messages: Iterable[dict], max_items: int = 4, max_chars: int = 240
) -> list[dict[str, str]]:
    """First few non-tool messages as {role, text}.

    role: 'user' for user messages, the agent name (or 'JARVIS') for
    assistant messages. Used by the design's Preview section.
    """
    out: list[dict[str, str]] = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _text_from_content(m.get("content", "")).strip()
        if not text:
            continue
        text = " ".join(text.split())
        if len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        if role == "user":
            out.append({"role": "user", "text": text})
        else:
            out.append({"role": m.get("agent") or "JARVIS", "text": text})
        if len(out) >= max_items:
            break
    return out
