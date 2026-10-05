"""Convert Claude Code session transcripts to Jarvis schema v1.0.0.

Claude Code writes one JSONL transcript per session under ``~/.claude/projects/<project>/<session>.jsonl``.
Each line is one record; an assistant message streams as several lines (one per content block) that
share ``message.id``. The desktop app keeps titles and archive flags in separate JSON files.

One Jarvis turn = one prompt the user typed + everything the assistant did until the next prompt.
Tool calls are kept as one-line summaries; tool results become a stub with their size, so the archive
and the RAG index hold what was said, not file dumps. Subagent transcripts are not imported, but the
report a subagent returns is kept verbatim: as its tool result, or for a background subagent, as the
``<result>`` of the task notification that delivers it.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.frontmatter import write_atomic
from packages.core.importers.common import ImportSummary, make_conv_id, make_filename, year_subdir
from packages.core.memory import SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_DESKTOP_SESSIONS_DIR = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code-sessions"

# Desktop entries without a cliSessionId are matched to a transcript by cwd and start time. The desktop
# entry is created 0.8-1.5 s before the transcript's first record (measured 2026-10-05 on 7 entries);
# the next-nearest transcript was always minutes away.
_START_TIME_TOLERANCE_SECONDS = 2.0

_TOOL_SUMMARY_MAX_CHARS = 200
_TITLE_FALLBACK_MAX_CHARS = 80

# Input keys that say what a tool call did, in order of preference.
_TOOL_SUMMARY_KEYS = (
    "command",
    "file_path",
    "path",
    "notebook_path",
    "pattern",
    "url",
    "query",
    "skill",
    "description",
    "prompt",
)

# User records that the harness injected rather than the user typing them.
_INJECTED_PREFIXES = (
    "<local-command-caveat>",
    "<local-command-stdout>",
    "<local-command-stderr>",
    "<task-notification>",
    "<system-reminder>",
    "<bash-input>",
    "<bash-stdout>",
    "[Request interrupted",
)

# Tools that run a subagent; their final report is kept instead of a size stub.
_SUBAGENT_TOOLS = ("Agent", "Task")

_NOTIFICATION_TOOL_USE_RE = re.compile(r"<tool-use-id>(.*?)</tool-use-id>", re.DOTALL)
_NOTIFICATION_RESULT_RE = re.compile(r"<result>(.*?)</result>", re.DOTALL)

_COMMAND_NAME_RE = re.compile(r"<command-name>(.*?)</command-name>", re.DOTALL)
_COMMAND_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO timestamp (``Z`` suffix allowed) to a timezone-aware datetime."""
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def read_transcript(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL transcript; lines that aren't valid JSON objects are skipped."""
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping invalid JSON on line %d of %s", line_no, path)
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def project_name(cwd: str | None) -> str | None:
    """Repository name for a session's cwd; worktrees map to the repo they belong to."""
    if not cwd:
        return None
    parts = Path(cwd).parts
    if ".claude" in parts:
        idx = parts.index(".claude")
        if idx > 0 and idx + 1 < len(parts) and parts[idx + 1] == "worktrees":
            return parts[idx - 1]
    return parts[-1] if parts else None


def summarize_tool_input(tool_input: Any) -> str:
    """One-line summary of a tool call's input (the command, path, query, …)."""
    if not isinstance(tool_input, dict) or not tool_input:
        return ""
    value: Any = None
    for key in _TOOL_SUMMARY_KEYS:
        if isinstance(tool_input.get(key), str) and tool_input[key].strip():
            value = tool_input[key]
            break
    if value is None:
        value = next((v for v in tool_input.values() if isinstance(v, str) and v.strip()), None)
    if value is None:
        value = json.dumps(tool_input, ensure_ascii=False)
    one_line = " ".join(str(value).split())
    if len(one_line) > _TOOL_SUMMARY_MAX_CHARS:
        one_line = one_line[: _TOOL_SUMMARY_MAX_CHARS - 1] + "…"
    return one_line


def _tool_result_text(content: Any) -> str:
    """Text of a tool result, which is either a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("text"))
    return ""


def _tool_result_chars(content: Any) -> int:
    """Size of a tool result's text content in characters."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(item.get("text", "")) for item in content if isinstance(item, dict))
    return 0


def _subagent_report(description: str, text: str) -> dict[str, Any]:
    return {
        "type": "text",
        "text": f"[Subagent report: {description}]\n{text}",
        "metadata": {"tool_result": True, "subagent_report": True, "is_error": False, "result_chars": len(text)},
    }


def user_prompt_text(record: dict[str, Any]) -> str | None:
    """Return the text the user typed, or None if the record isn't a user prompt.

    Tool results, harness-injected messages (meta lines, task notifications, peer messages,
    local-command echoes, interrupt markers) and compaction summaries are not prompts.
    Slash commands become ``/name args``.
    """
    if record.get("type") != "user" or record.get("isSidechain"):
        return None
    if record.get("isMeta") or record.get("isCompactSummary") or record.get("isVisibleInTranscriptOnly"):
        return None
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return None

    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "image":
                parts.append("[Image]")
        text = "\n".join(p for p in parts if p)
    else:
        return None

    stripped = text.lstrip()
    if not stripped or stripped.startswith(_INJECTED_PREFIXES):
        return None
    name_match = _COMMAND_NAME_RE.search(stripped)
    if name_match and stripped.startswith(("<command-name>", "<command-message>")):
        args_match = _COMMAND_ARGS_RE.search(stripped)
        args = args_match.group(1).strip() if args_match else ""
        command = name_match.group(1).strip()
        return f"{command} {args}".strip()
    return text


def _new_message(role: str, timestamp: str | None) -> dict[str, Any]:
    return {
        "id": "",
        "parent_id": None,
        "role": role,
        "timestamp": timestamp,
        "content": [],
        "usage": None,
        "latency": None,
        "stop_reason": None,
        "status": "completed",
        "error": None,
        "metadata": {},
    }


def _assistant_blocks(content: Any) -> list[dict[str, Any]]:
    """Convert one assistant record's content blocks to Jarvis content blocks."""
    result: list[dict[str, Any]] = []
    if not isinstance(content, list):
        return result
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text", "")
            if text.strip():
                result.append({"type": "text", "text": text})
        elif block_type == "thinking":
            thinking = block.get("thinking", "")
            if thinking.strip():
                result.append({"type": "text", "text": thinking, "metadata": {"thought": True}})
        elif block_type == "tool_use":
            name = block.get("name", "unknown_tool")
            summary = summarize_tool_input(block.get("input"))
            result.append(
                {
                    "type": "text",
                    "text": f"[Tool: {name}] {summary}".rstrip(),
                    "metadata": {"tool_use": True, "tool_name": name, "tool_input_summary": summary},
                }
            )
    return result


def _tool_result_blocks(content: Any, subagent_calls: dict[str, str]) -> list[dict[str, Any]]:
    """One block per tool result: the report of a foreground subagent, else a stub with the size.

    ``subagent_calls`` maps the tool_use id of each foreground subagent call to its description.
    """
    result: list[dict[str, Any]] = []
    if not isinstance(content, list):
        return result
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        is_error = bool(block.get("is_error"))
        description = subagent_calls.get(block.get("tool_use_id", ""))
        report = _tool_result_text(block.get("content")).strip()
        if description is not None and not is_error and report:
            result.append(_subagent_report(description, report))
            continue
        chars = _tool_result_chars(block.get("content"))
        label = "Tool error" if is_error else "Tool result"
        result.append(
            {
                "type": "text",
                "text": f"[{label}: {chars:,} chars]",
                "metadata": {"tool_result": True, "is_error": is_error, "result_chars": chars},
            }
        )
    return result


def _notification_report(record: dict[str, Any], background_calls: dict[str, str]) -> dict[str, Any] | None:
    """Report block for a task notification that delivers a background subagent's result."""
    if record.get("type") != "user":
        return None
    content = (record.get("message") or {}).get("content")
    if not isinstance(content, str) or not content.lstrip().startswith("<task-notification>"):
        return None
    tool_use = _NOTIFICATION_TOOL_USE_RE.search(content)
    report = _NOTIFICATION_RESULT_RE.search(content)
    if not tool_use or not report or tool_use.group(1).strip() not in background_calls:
        return None
    text = report.group(1).strip()
    if not text:
        return None
    return _subagent_report(background_calls[tool_use.group(1).strip()], text)


def _subagent_calls(content: Any) -> tuple[dict[str, str], dict[str, str]]:
    """Foreground and background subagent calls in an assistant record: tool_use id → description."""
    foreground: dict[str, str] = {}
    background: dict[str, str] = {}
    if not isinstance(content, list):
        return foreground, background
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("name") not in _SUBAGENT_TOOLS:
            continue
        raw_input = block.get("input")
        tool_input: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
        raw_description = tool_input.get("description")
        description = "subagent"
        if isinstance(raw_description, str) and raw_description.strip():
            description = summarize_tool_input({"description": raw_description})
        target = background if tool_input.get("run_in_background") else foreground
        target[block.get("id", "")] = description
    return foreground, background


def _add_usage(totals: dict[str, int], usage: dict[str, Any]) -> None:
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            totals[key] = totals.get(key, 0) + value


def build_messages(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group transcript records into alternating user prompts and assistant turns.

    Assistant records and tool results before the first prompt are dropped. Token usage
    (repeated on every streamed line of one API message) is counted once per ``message.id``
    and kept in the turn's metadata, not in ``usage``, so imported turns never count as spend.
    """
    messages: list[dict[str, Any]] = []
    turn: dict[str, Any] | None = None
    seen_usage_ids: set[str] = set()
    foreground_calls: dict[str, str] = {}
    background_calls: dict[str, str] = {}

    for record in records:
        record_type = record.get("type")
        if record.get("isSidechain"):
            continue

        prompt = user_prompt_text(record)
        if prompt is not None:
            user_msg = _new_message("user", record.get("timestamp"))
            user_msg["content"] = [{"type": "text", "text": prompt}]
            messages.append(user_msg)
            turn = None
            continue

        if not messages:
            continue

        report = _notification_report(record, background_calls)
        if report is not None:
            if turn is None:
                turn = _new_message("assistant", record.get("timestamp"))
                messages.append(turn)
            turn["content"].append(report)
            continue

        if record_type == "assistant":
            message = record.get("message") or {}
            blocks = _assistant_blocks(message.get("content"))
            foreground, background = _subagent_calls(message.get("content"))
            foreground_calls.update(foreground)
            background_calls.update(background)
            if turn is None:
                turn = _new_message("assistant", record.get("timestamp"))
                messages.append(turn)
            turn["content"].extend(blocks)
            model = message.get("model")
            if model and model != "<synthetic>":
                turn["metadata"]["model"] = model
            if message.get("stop_reason"):
                turn["stop_reason"] = message["stop_reason"]
            msg_id = message.get("id")
            usage = message.get("usage")
            if isinstance(usage, dict) and msg_id and msg_id not in seen_usage_ids:
                seen_usage_ids.add(msg_id)
                _add_usage(turn["metadata"].setdefault("claude_code_usage", {}), usage)
        elif record_type == "user" and turn is not None:
            turn["content"].extend(_tool_result_blocks((record.get("message") or {}).get("content"), foreground_calls))

    for i, msg in enumerate(messages, start=1):
        msg["id"] = f"msg_{i:03d}"
        if not msg["content"]:
            msg["content"] = [{"type": "text", "text": ""}]
    return messages


def session_title(records: list[dict[str, Any]], desktop: dict[str, Any] | None) -> str | None:
    """Title: desktop title, else the last custom title, else the last AI title."""
    if desktop and desktop.get("title"):
        return str(desktop["title"])
    custom = [r.get("customTitle") for r in records if r.get("type") == "custom-title" and r.get("customTitle")]
    if custom:
        return str(custom[-1])
    ai = [r.get("aiTitle") for r in records if r.get("type") == "ai-title" and r.get("aiTitle")]
    if ai:
        return str(ai[-1])
    return None


def convert_session(
    session_id: str,
    records: list[dict[str, Any]],
    *,
    desktop: dict[str, Any] | None = None,
    subagent_count: int = 0,
) -> dict[str, Any] | None:
    """Convert one transcript to a Jarvis conversation; None if it holds no user prompt."""
    messages = build_messages(records)
    if not any(m["role"] == "user" for m in messages):
        return None

    timestamps = [r["timestamp"] for r in records if isinstance(r.get("timestamp"), str)]
    session_start = min(timestamps) if timestamps else None
    session_end = max(timestamps) if timestamps else None
    start_dt = _parse_iso(session_start) or datetime.now(tz=UTC)

    first = next((r for r in records if r.get("type") in ("user", "assistant") and r.get("cwd")), {})
    cwd = first.get("cwd")
    project = project_name(cwd)
    branches = sorted({r["gitBranch"] for r in records if r.get("gitBranch")})

    title = session_title(records, desktop)
    if not title:
        first_prompt = " ".join(messages[0]["content"][0]["text"].split())
        title = first_prompt[:_TITLE_FALLBACK_MAX_CHARS]

    models = [m["metadata"]["model"] for m in messages if m["metadata"].get("model")]

    tags = ["imported", "claude-code"]
    if project:
        tags.append(f"project:{project.lower()}")

    metadata: dict[str, Any] = {
        "import_source": "claude_code",
        "claude_code_session_id": session_id,
        "cwd": cwd,
        "project": project,
        "git_branches": branches,
        "entrypoint": first.get("entrypoint"),
        "claude_code_version": first.get("version"),
        "subagent_transcripts": subagent_count,
        "import_timestamp": datetime.now(tz=UTC).isoformat(),
    }
    if desktop:
        metadata["desktop_session_id"] = desktop.get("sessionId")
        metadata["archived"] = bool(desktop.get("isArchived"))

    return {
        "schema_version": SCHEMA_VERSION,
        "id": make_conv_id(session_id, start_dt),
        "title": title,
        "topic": None,
        "tags": tags,
        "session_start": session_start,
        "session_end": session_end,
        "model": models[-1] if models else (desktop or {}).get("model"),
        "agent": None,
        "context": None,
        "metrics": {},
        "environment": None,
        "messages": messages,
        "feedback": None,
        "metadata": metadata,
    }


def load_desktop_sessions(sessions_dir: Path) -> list[dict[str, Any]]:
    """Read the desktop app's session entries (title, archive flag, cliSessionId)."""
    entries: list[dict[str, Any]] = []
    if not sessions_dir.exists():
        return entries
    for path in sessions_dir.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and data.get("sessionId"):
            entries.append(data)
    return entries


def match_desktop_entry(
    session_id: str,
    session_start: str | None,
    cwd: str | None,
    by_cli_id: dict[str, dict[str, Any]],
    without_cli_id: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Desktop entry for a transcript: by cliSessionId, else the closest entry with the same cwd
    created within the start-time tolerance."""
    if session_id in by_cli_id:
        return by_cli_id[session_id]
    start_dt = _parse_iso(session_start)
    if start_dt is None:
        return None
    best: dict[str, Any] | None = None
    best_delta = _START_TIME_TOLERANCE_SECONDS
    for entry in without_cli_id:
        created_ms = entry.get("createdAt")
        if not isinstance(created_ms, int | float) or entry.get("cwd") != cwd:
            continue
        delta = abs(start_dt.timestamp() - created_ms / 1000)
        if delta <= best_delta:
            best, best_delta = entry, delta
    return best


def _comparable(conv: dict[str, Any]) -> dict[str, Any]:
    """Conversation without fields that change on every import run."""
    meta = {k: v for k, v in conv.get("metadata", {}).items() if k not in ("import_timestamp", "last_sync_timestamp")}
    return {**conv, "metadata": meta}


def import_sessions(
    projects_dir: Path,
    target_dir: Path,
    *,
    desktop_sessions_dir: Path | None = None,
    dry_run: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ImportSummary:
    """Import Claude Code transcripts into ``target_dir``.

    Re-running is safe: a session imported before is rewritten in place when its transcript grew
    (transcripts are append-only), keeping its id, file and first import timestamp; a transcript
    that got shorter than the archived copy is left alone.
    """
    summary = ImportSummary()

    desktop_entries = load_desktop_sessions(desktop_sessions_dir) if desktop_sessions_dir else []
    by_cli_id = {e["cliSessionId"]: e for e in desktop_entries if e.get("cliSessionId")}
    without_cli_id = [e for e in desktop_entries if not e.get("cliSessionId")]

    dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=UTC) if date_from else None
    dt_to = None
    if date_to:
        dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=UTC, hour=23, minute=59, second=59)

    used_filenames: set[str] = set()
    existing: dict[str, Path] = {}
    if target_dir.exists():
        for path in target_dir.rglob("*.json"):
            used_filenames.add(path.name)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            sid = data.get("metadata", {}).get("claude_code_session_id")
            if sid:
                existing[sid] = path

    for transcript in sorted(projects_dir.glob("*/*.jsonl")):
        summary.total += 1
        session_id = transcript.stem
        try:
            records = read_transcript(transcript)
            timestamps = [r["timestamp"] for r in records if isinstance(r.get("timestamp"), str)]
            session_start = min(timestamps) if timestamps else None
            start_dt = _parse_iso(session_start)
            if start_dt and ((dt_from and start_dt < dt_from) or (dt_to and start_dt > dt_to)):
                summary.skipped_filter += 1
                continue

            cwd = next((r["cwd"] for r in records if r.get("type") in ("user", "assistant") and r.get("cwd")), None)
            desktop = match_desktop_entry(session_id, session_start, cwd, by_cli_id, without_cli_id)
            subagents_dir = transcript.parent / session_id / "subagents"
            subagent_count = len(list(subagents_dir.glob("*.jsonl"))) if subagents_dir.exists() else 0

            conv = convert_session(session_id, records, desktop=desktop, subagent_count=subagent_count)
            if conv is None:
                summary.skipped_empty += 1
                continue

            if session_id in existing:
                path = existing[session_id]
                old = json.loads(path.read_text(encoding="utf-8"))
                if len(conv["messages"]) < len(old.get("messages", [])):
                    logger.warning("Transcript %s is shorter than its archived copy; left alone", transcript)
                    summary.skipped_existing += 1
                    continue
                conv["id"] = old.get("id", conv["id"])
                old_meta = old.get("metadata", {})
                conv["metadata"]["import_timestamp"] = old_meta.get(
                    "import_timestamp", conv["metadata"]["import_timestamp"]
                )
                if _comparable(conv) == _comparable(old):
                    summary.skipped_existing += 1
                    continue
                conv["metadata"]["last_sync_timestamp"] = datetime.now(tz=UTC).isoformat()
                if not dry_run:
                    write_atomic(path, json.dumps(conv, indent=2, ensure_ascii=False))
                summary.updated += 1
                continue

            ts_dt = start_dt or datetime.now(tz=UTC)
            filename = make_filename(ts_dt)
            if filename in used_filenames:
                base = filename.rsplit(".", 1)[0]
                suffix = 2
                while f"{base}_{suffix}.json" in used_filenames:
                    suffix += 1
                filename = f"{base}_{suffix}.json"
            used_filenames.add(filename)

            if not dry_run:
                write_atomic(year_subdir(target_dir, ts_dt) / filename, json.dumps(conv, indent=2, ensure_ascii=False))
            summary.imported += 1

        except Exception as e:
            err_msg = f"Error converting '{transcript}': {e}"
            logger.error(err_msg)
            summary.errors += 1
            summary.error_details.append(err_msg)

    return summary
