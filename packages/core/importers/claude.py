"""Convert Claude conversation exports to Jarvis schema v1.0.0."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from packages.core.importers.common import ImportSummary, make_conv_id, make_filename
from packages.core.memory import SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Sender mapping: Claude export uses "human"/"assistant"
_ROLE_MAP = {"human": "user", "assistant": "assistant"}


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
                result.append({
                    "type": "text",
                    "text": thinking_text,
                    "metadata": {"thought": True},
                })

        elif block_type == "tool_use":
            name = block.get("name", "unknown_tool")
            tool_input = block.get("input", {})
            result.append({
                "type": "text",
                "text": f"[Tool: {name}]",
                "metadata": {
                    "tool_use": True,
                    "tool_name": name,
                    "tool_input": tool_input,
                },
            })

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
            result.append({
                "type": "text",
                "text": text,
                "metadata": {
                    "tool_result": True,
                    "tool_name": name,
                    "is_error": is_error,
                },
            })

        elif block_type == "token_budget":
            # Skip entirely — this is a marker block with no content
            continue

        else:
            # Unknown block type: best-effort fallback
            text = block.get("text", "") or block.get("thinking", "") or ""
            if text.strip():
                result.append({
                    "type": "text",
                    "text": text,
                    "metadata": {"original_content_type": block_type},
                })

    # Convert attachments (on human messages)
    if attachments:
        for att in attachments:
            file_name = att.get("file_name", "")
            extracted = att.get("extracted_content", "")
            if extracted:
                result.append({
                    "type": "text",
                    "text": extracted,
                    "metadata": {
                        "attachment": True,
                        "file_name": file_name,
                        "file_size": att.get("file_size"),
                        "file_type": att.get("file_type"),
                    },
                })

    # Convert files (assistant-generated artifacts)
    if files:
        for f in files:
            file_name = f.get("file_name", "")
            if file_name:
                result.append({
                    "type": "text",
                    "text": f"[Generated file: {file_name}]",
                    "metadata": {
                        "generated_file": True,
                        "file_name": file_name,
                    },
                })

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

    tags = ["imported", "claude"]

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

        messages.append({
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
        })

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "id": conv_id,
        "title": name,
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
        "metadata": {
            "import_source": "claude",
            "claude_id": claude_id,
            "import_timestamp": now_iso,
        },
    }


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
    dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc) if date_from else None
    dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) if date_to else None
    if dt_to:
        dt_to = dt_to.replace(hour=23, minute=59, second=59)

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    # Track filenames for collision handling within this run
    used_filenames: set[str] = set()
    # Track already-imported claude IDs for idempotent skip
    existing_claude_ids: set[str] = set()
    if not dry_run:
        used_filenames = {f.name for f in target_dir.glob("*.json")}
        for f in target_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                cid = data.get("metadata", {}).get("claude_id")
                if cid:
                    existing_claude_ids.add(cid)
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

            # Skip already imported (idempotent by claude_id)
            claude_id = conv.get("uuid", "")
            if claude_id and claude_id in existing_claude_ids:
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

            filepath = target_dir / filename

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
