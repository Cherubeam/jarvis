"""Convert Claude conversation exports to Jarvis schema v1.0.0."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from packages.core.importers.common import ImportSummary, make_conv_id, make_filename, year_subdir
from packages.core.memory import SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Sender mapping: Claude export uses "human"/"assistant"
_ROLE_MAP = {"human": "user", "assistant": "assistant"}

# Bracket-prefix to status-tag mapping
_STATUS_PREFIX_MAP = {
    "X": "status:done",
    " ": "status:open",
    "!": "status:important",
    "~": "status:in-progress",
}

_BRACKET_RE = re.compile(r"^\[([^\]]*)\]\s*")


def parse_title_prefixes(name: str | None) -> tuple[str, list[str]]:
    """Extract bracket prefixes from a conversation name and derive tags.

    Returns (clean_title, derived_tags). Known status prefixes ([X], [ ], [!], [~])
    map to status:* tags. Other brackets become topic:* tags.
    """
    if not name:
        return ("", [])

    tags: list[str] = []
    remaining = name
    while True:
        m = _BRACKET_RE.match(remaining)
        if not m:
            break
        content = m.group(1)
        remaining = remaining[m.end() :]
        status_tag = _STATUS_PREFIX_MAP.get(content)
        if status_tag:
            tags.append(status_tag)
        else:
            tags.append(f"topic:{content.lower()}")

    return (remaining.strip(), tags)


def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    if not ts:
        return None
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def convert_content_blocks(
    blocks: list[dict],
    attachments: list[dict] | None = None,
    files: list[dict] | None = None,
) -> list[dict]:
    """Convert Claude content blocks to Jarvis content blocks.

    Handles: text, thinking, tool_use, tool_result, token_budget.
    Also converts attachments (human messages) and files (assistant-generated).
    """
    result: list[dict] = []

    for block in blocks:
        block_type = block.get("type")

        if block_type == "text":
            text = block.get("text", "")
            # Skip empty whitespace-only text blocks
            if text.strip():
                result.append({"type": "text", "text": text})

        elif block_type == "thinking":
            thinking_text = block.get("thinking", "")
            if thinking_text.strip():
                result.append(
                    {
                        "type": "text",
                        "text": thinking_text,
                        "metadata": {"thought": True},
                    }
                )

        elif block_type == "tool_use":
            name = block.get("name", "unknown_tool")
            tool_input = block.get("input", {})
            result.append(
                {
                    "type": "text",
                    "text": f"[Tool: {name}]",
                    "metadata": {
                        "tool_use": True,
                        "tool_name": name,
                        "tool_input": tool_input,
                    },
                }
            )

        elif block_type == "tool_result":
            name = block.get("name", "unknown_tool")
            is_error = block.get("is_error", False)
            # Extract text from nested content blocks
            nested = block.get("content", [])
            text_parts = []
            for item in nested:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            text = "\n".join(text_parts) if text_parts else ""
            result.append(
                {
                    "type": "text",
                    "text": text,
                    "metadata": {
                        "tool_result": True,
                        "tool_name": name,
                        "is_error": is_error,
                    },
                }
            )

        elif block_type == "token_budget":
            # Skip entirely — this is a marker block with no content
            continue

        else:
            # Unknown block type: best-effort fallback
            text = block.get("text", "") or block.get("thinking", "") or ""
            if text.strip():
                result.append(
                    {
                        "type": "text",
                        "text": text,
                        "metadata": {"original_content_type": block_type},
                    }
                )

    # Convert attachments (on human messages)
    if attachments:
        for att in attachments:
            file_name = att.get("file_name", "")
            extracted = att.get("extracted_content", "")
            if extracted:
                result.append(
                    {
                        "type": "text",
                        "text": extracted,
                        "metadata": {
                            "attachment": True,
                            "file_name": file_name,
                            "file_size": att.get("file_size"),
                            "file_type": att.get("file_type"),
                        },
                    }
                )

    # Convert files (assistant-generated artifacts)
    if files:
        for f in files:
            file_name = f.get("file_name", "")
            if file_name:
                result.append(
                    {
                        "type": "text",
                        "text": f"[Generated file: {file_name}]",
                        "metadata": {
                            "generated_file": True,
                            "file_name": file_name,
                        },
                    }
                )

    # Ensure at least one content block
    if not result:
        result.append({"type": "text", "text": ""})

    return result


def convert_conversation(claude_conv: dict) -> dict:
    """Convert a single Claude conversation to Jarvis schema v1.0.0."""
    claude_id = claude_conv.get("uuid", "")
    name = claude_conv.get("name")
    created_at = claude_conv.get("created_at")
    updated_at = claude_conv.get("updated_at")

    created_dt = _parse_iso(created_at)
    updated_dt = _parse_iso(updated_at)

    # Generate deterministic conv_id
    dt_for_id = created_dt or updated_dt or datetime.now(tz=timezone.utc)
    conv_id = make_conv_id(claude_id, dt_for_id)

    # Parse title prefixes into tags
    clean_title, prefix_tags = parse_title_prefixes(name)

    tags = ["imported", "claude"]
    tags.extend(prefix_tags)

    # Convert messages
    raw_messages = claude_conv.get("chat_messages", [])
    messages = []
    for i, raw_msg in enumerate(raw_messages, start=1):
        sender = raw_msg.get("sender", "")
        role = _ROLE_MAP.get(sender, "system")

        content_blocks = raw_msg.get("content", [])
        attachments = raw_msg.get("attachments", []) or []
        files = raw_msg.get("files", []) or []
        jarvis_content = convert_content_blocks(content_blocks, attachments, files)

        msg_created = raw_msg.get("created_at")
        msg_updated = raw_msg.get("updated_at")
        timestamp = msg_created or msg_updated

        messages.append(
            {
                "id": f"msg_{i:03d}",
                "parent_id": None,
                "role": role,
                "timestamp": timestamp,
                "content": jarvis_content,
                "usage": None,
                "latency": None,
                "stop_reason": None,
                "status": "completed",
                "error": None,
                "metadata": {},
            }
        )

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    metadata = {
        "import_source": "claude",
        "claude_id": claude_id,
        "claude_summary": claude_conv.get("summary"),
        "import_timestamp": now_iso,
    }
    if name and name != clean_title:
        metadata["original_title"] = name

    return {
        "schema_version": SCHEMA_VERSION,
        "id": conv_id,
        "title": clean_title or name,
        "topic": None,
        "tags": tags,
        "session_start": created_at,
        "session_end": updated_at,
        "model": None,  # Claude export doesn't include model info
        "agent": None,
        "context": None,
        "metrics": {},
        "environment": None,
        "messages": messages,
        "feedback": None,
        "metadata": metadata,
    }


def _convert_new_messages(claude_conv: dict, start_index: int) -> list[dict]:
    """Convert Claude messages starting from start_index to Jarvis format.

    Message IDs continue from start_index (1-based).
    """
    raw_messages = claude_conv.get("chat_messages", [])
    messages = []
    for i, raw_msg in enumerate(raw_messages[start_index:], start=start_index + 1):
        sender = raw_msg.get("sender", "")
        role = _ROLE_MAP.get(sender, "system")

        content_blocks = raw_msg.get("content", [])
        attachments = raw_msg.get("attachments", []) or []
        files = raw_msg.get("files", []) or []
        jarvis_content = convert_content_blocks(content_blocks, attachments, files)

        msg_created = raw_msg.get("created_at")
        msg_updated = raw_msg.get("updated_at")
        timestamp = msg_created or msg_updated

        messages.append(
            {
                "id": f"msg_{i:03d}",
                "parent_id": None,
                "role": role,
                "timestamp": timestamp,
                "content": jarvis_content,
                "usage": None,
                "latency": None,
                "stop_reason": None,
                "status": "completed",
                "error": None,
                "metadata": {},
            }
        )
    return messages


def update_conversation(existing_path: Path, claude_conv: dict, *, dry_run: bool = False) -> bool:
    """Update an existing JARVIS conversation with new data from Claude.

    Syncs title, session_end, and appends new messages. Never removes
    existing JARVIS messages (additive-only).

    Returns True if changes were made, False if no changes needed.
    """
    jarvis_data = json.loads(existing_path.read_text())
    changed = False

    # Title and prefix-tag sync — Claude is source of truth
    claude_title = claude_conv.get("name")
    if claude_title:
        clean_title, new_prefix_tags = parse_title_prefixes(claude_title)
        if clean_title != jarvis_data.get("title"):
            jarvis_data["title"] = clean_title
            changed = True

        # Replace status tags (mutually exclusive), merge topic tags (additive)
        existing_tags = jarvis_data.get("tags", [])
        new_status = {t for t in new_prefix_tags if t.startswith("status:")}
        new_topics = {t for t in new_prefix_tags if t.startswith("topic:")}
        # Rebuild: keep non-prefix tags, replace status, keep existing topics, add new ones
        merged: list[str] = []
        for t in existing_tags:
            if t.startswith("status:"):
                continue  # Will be replaced
            merged.append(t)
        merged.extend(sorted(new_status))
        for topic in sorted(new_topics):
            if topic not in merged:
                merged.append(topic)
        if set(merged) != set(existing_tags) or len(merged) != len(existing_tags):
            jarvis_data["tags"] = merged
            changed = True

        # Sync original_title metadata
        meta = jarvis_data.setdefault("metadata", {})
        if claude_title != clean_title:
            if meta.get("original_title") != claude_title:
                meta["original_title"] = claude_title
                changed = True
        elif "original_title" in meta:
            del meta["original_title"]
            changed = True

    # Summary sync
    claude_summary = claude_conv.get("summary")
    if claude_summary != jarvis_data.get("metadata", {}).get("claude_summary"):
        jarvis_data.setdefault("metadata", {})["claude_summary"] = claude_summary
        changed = True

    # Session end — use newer timestamp
    claude_updated = claude_conv.get("updated_at")
    if claude_updated:
        jarvis_end = jarvis_data.get("session_end")
        if not jarvis_end or claude_updated > jarvis_end:
            jarvis_data["session_end"] = claude_updated
            changed = True

    # Append new messages
    claude_msg_count = len(claude_conv.get("chat_messages", []))
    jarvis_msg_count = len(jarvis_data.get("messages", []))
    if claude_msg_count > jarvis_msg_count:
        new_messages = _convert_new_messages(claude_conv, jarvis_msg_count)
        jarvis_data["messages"].extend(new_messages)
        changed = True

    if changed:
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        jarvis_data.setdefault("metadata", {})["last_sync_timestamp"] = now_iso
        if not dry_run:
            existing_path.write_text(json.dumps(jarvis_data, indent=2, ensure_ascii=False))

    return changed


def import_conversations(
    source_path: Path,
    target_dir: Path,
    *,
    dry_run: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ImportSummary:
    """Import Claude conversations to Jarvis format.

    Args:
        source_path: Path to Claude conversations.json export.
        target_dir: Directory to write converted JSON files.
        dry_run: If True, don't write files, just report what would happen.
        date_from: ISO date string (YYYY-MM-DD). Only import conversations created on or after.
        date_to: ISO date string (YYYY-MM-DD). Only import conversations created on or before.

    Returns:
        ImportSummary with counts and error details.
    """
    summary = ImportSummary()

    with open(source_path) as f:
        conversations = json.load(f)

    summary.total = len(conversations)

    # Parse filter dates
    dt_from = (
        datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc) if date_from else None
    )
    dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) if date_to else None
    if dt_to:
        dt_to = dt_to.replace(hour=23, minute=59, second=59)

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    # Track filenames for collision handling within this run
    used_filenames: set[str] = set()
    # Track already-imported claude IDs → file path for incremental sync
    existing_claude_ids: dict[str, Path] = {}
    if target_dir.exists():
        used_filenames = {f.name for f in target_dir.rglob("*.json")}
        for f in target_dir.rglob("*.json"):
            try:
                data = json.loads(f.read_text())
                cid = data.get("metadata", {}).get("claude_id")
                if cid:
                    existing_claude_ids[cid] = f
            except (json.JSONDecodeError, OSError):
                pass

    for conv in conversations:
        try:
            created_at = conv.get("created_at")
            created_dt = _parse_iso(created_at)

            # Filter: date range
            if created_dt and (dt_from or dt_to):
                if dt_from and created_dt < dt_from:
                    summary.skipped_filter += 1
                    continue
                if dt_to and created_dt > dt_to:
                    summary.skipped_filter += 1
                    continue

            # Incremental sync for existing conversations
            claude_id = conv.get("uuid", "")
            if claude_id and claude_id in existing_claude_ids:
                existing_path = existing_claude_ids[claude_id]
                if update_conversation(existing_path, conv, dry_run=dry_run):
                    summary.updated += 1
                else:
                    summary.skipped_existing += 1
                continue

            # Generate filename
            updated_at = conv.get("updated_at")
            ts_dt = created_dt or _parse_iso(updated_at) or datetime.now(tz=timezone.utc)
            filename = make_filename(ts_dt)

            # Handle collisions
            if filename in used_filenames:
                base = filename.rsplit(".", 1)[0]
                suffix = 2
                while f"{base}_{suffix}.json" in used_filenames:
                    suffix += 1
                filename = f"{base}_{suffix}.json"

            filepath = year_subdir(target_dir, ts_dt) / filename

            # Convert
            jarvis_conv = convert_conversation(conv)

            if not dry_run:
                filepath.write_text(json.dumps(jarvis_conv, indent=2, ensure_ascii=False))

            used_filenames.add(filename)
            summary.imported += 1

        except Exception as e:
            title = conv.get("name", "unknown")
            err_msg = f"Error converting '{title}': {e}"
            logger.error(err_msg)
            summary.errors += 1
            summary.error_details.append(err_msg)

    return summary
