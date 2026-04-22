"""Convert ChatGPT conversation exports to Jarvis schema v1.0.0."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from packages.core.importers.common import ImportSummary, make_conv_id, make_filename, year_subdir
from packages.core.memory import SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Roles that map directly to Jarvis roles
_ROLE_MAP = {"user": "user", "assistant": "assistant", "system": "system", "tool": "tool"}


def linearize_message_tree(mapping: dict, current_node: str) -> list[dict]:
    """Walk from current_node to root via parent pointers, return messages in chronological order.

    Skips nodes with no message. Detects cycles.
    """
    chain: list[dict] = []
    visited: set[str] = set()
    node_id: str | None = current_node

    while node_id:
        if node_id in visited:
            logger.warning("Cycle detected at node %s, stopping traversal", node_id)
            break
        visited.add(node_id)

        node = mapping.get(node_id)
        if node is None:
            logger.warning("Missing node %s in mapping, stopping traversal", node_id)
            break

        msg = node.get("message")
        if msg is not None:
            chain.append(msg)

        node_id = node.get("parent")

    chain.reverse()
    return chain


def convert_content_parts(content: dict) -> list[dict]:
    """Convert a ChatGPT message content dict to Jarvis content blocks."""
    content_type = content.get("content_type", "text")
    parts = content.get("parts", [])

    if content_type == "text":
        return _convert_text_parts(parts)

    if content_type == "multimodal_text":
        return _convert_multimodal_parts(parts)

    if content_type == "code":
        text = content.get("text", "")
        lang = content.get("language", "")
        if lang and lang != "unknown":
            text = f"```{lang}\n{text}\n```"
        else:
            text = f"```\n{text}\n```"
        return [{"type": "text", "text": text}]

    if content_type == "thoughts":
        thoughts = content.get("thoughts", [])
        blocks: list[dict] = []
        for thought in thoughts:
            t = thought.get("content", "") or thought.get("summary", "")
            if t:
                blocks.append({"type": "text", "text": t, "metadata": {"thought": True}})
        return blocks or [{"type": "text", "text": ""}]

    if content_type == "execution_output":
        text = content.get("text", "")
        return [{"type": "text", "text": text, "metadata": {"execution_output": True}}]

    if content_type == "tether_browsing_display":
        result = content.get("result", "")
        summary = content.get("summary", "")
        text = result or summary or ""
        return [{"type": "text", "text": text, "metadata": {"browsing_display": True}}]

    if content_type == "tether_quote":
        text = content.get("text", "")
        domain = content.get("domain", "")
        url = content.get("url", "")
        return [{"type": "text", "text": text, "metadata": {"quote_source": domain, "quote_url": url}}]

    if content_type == "reasoning_recap":
        text = content.get("content", "")
        return [{"type": "text", "text": text, "metadata": {"reasoning_recap": True}}]

    if content_type == "system_error":
        text = content.get("text", "")
        name = content.get("name", "")
        return [{"type": "text", "text": text, "metadata": {"error_name": name}}]

    if content_type == "user_editable_context":
        text = content.get("user_profile", "")
        return [{"type": "text", "text": text, "metadata": {"user_editable_context": True}}]

    if content_type == "app_pairing_content":
        context_parts = content.get("context_parts", [])
        text = "\n".join(cp.get("text", "") for cp in context_parts if cp.get("text"))
        return [{"type": "text", "text": text, "metadata": {"app_pairing": True}}]

    # Unknown content type: best-effort fallback
    text = _extract_fallback_text(content, parts)
    return [{"type": "text", "text": text, "metadata": {"original_content_type": content_type}}]


def _convert_text_parts(parts: list) -> list[dict]:
    texts = []
    for p in parts:
        if isinstance(p, str):
            texts.append(p)
        else:
            texts.append(str(p))
    combined = "\n".join(texts)
    return [{"type": "text", "text": combined}]


def _convert_multimodal_parts(parts: list) -> list[dict]:
    blocks: list[dict] = []
    for p in parts:
        if isinstance(p, str):
            if p:
                blocks.append({"type": "text", "text": p})
        elif isinstance(p, dict):
            ct = p.get("content_type", "")
            if ct == "image_asset_pointer":
                blocks.append(
                    {
                        "type": "text",
                        "text": "[Image not available]",
                        "metadata": {
                            "original_type": "image",
                            "asset_pointer": p.get("asset_pointer", ""),
                        },
                    }
                )
            else:
                blocks.append(
                    {
                        "type": "text",
                        "text": str(p),
                        "metadata": {"original_type": ct or "unknown"},
                    }
                )
        else:
            blocks.append({"type": "text", "text": str(p)})
    return blocks or [{"type": "text", "text": ""}]


def _extract_fallback_text(content: dict, parts: list) -> str:
    if parts:
        return "\n".join(str(p) for p in parts if isinstance(p, str))
    return content.get("text", "")


def _unix_to_iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _make_conv_id(chatgpt_uuid: str, create_time: float | None) -> str:
    """Generate deterministic conv_id from ChatGPT UUID."""
    if create_time:
        dt = datetime.fromtimestamp(create_time, tz=UTC)
    else:
        dt = datetime.now(tz=UTC)
    return make_conv_id(chatgpt_uuid, dt)


def _make_filename(create_time: float | None, update_time: float | None) -> str:
    ts = create_time or update_time
    if ts:
        dt = datetime.fromtimestamp(ts, tz=UTC)
    else:
        dt = datetime.now(tz=UTC)
    return make_filename(dt)


def convert_conversation(chatgpt_conv: dict) -> dict:
    """Convert a single ChatGPT conversation to Jarvis schema v1.0.0."""
    chatgpt_id = chatgpt_conv.get("conversation_id") or chatgpt_conv.get("id", "")
    create_time = chatgpt_conv.get("create_time")
    update_time = chatgpt_conv.get("update_time")

    conv_id = _make_conv_id(chatgpt_id, create_time)

    tags = ["imported", "chatgpt"]
    if chatgpt_conv.get("is_archived"):
        tags.append("archived")

    model_slug = chatgpt_conv.get("default_model_slug")
    model = {"id": model_slug, "provider": "openai"} if model_slug else None

    # Linearize message tree
    mapping = chatgpt_conv.get("mapping", {})
    current_node = chatgpt_conv.get("current_node")
    raw_messages = []
    if mapping and current_node:
        raw_messages = linearize_message_tree(mapping, current_node)

    # Convert messages
    messages: list[dict] = []
    for i, raw_msg in enumerate(raw_messages, start=1):
        author = raw_msg.get("author", {})
        role = _ROLE_MAP.get(author.get("role", ""), "system")

        content_dict = raw_msg.get("content", {})
        content_blocks = convert_content_parts(content_dict)

        msg_create = raw_msg.get("create_time")
        msg_update = raw_msg.get("update_time")
        timestamp = _unix_to_iso(msg_create or msg_update)

        messages.append(
            {
                "id": f"msg_{i:03d}",
                "parent_id": None,
                "role": role,
                "timestamp": timestamp,
                "content": content_blocks,
                "usage": None,
                "latency": None,
                "stop_reason": None,
                "status": "completed",
                "error": None,
                "metadata": {},
            }
        )

    now_iso = datetime.now(tz=UTC).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "id": conv_id,
        "title": chatgpt_conv.get("title"),
        "topic": None,
        "tags": tags,
        "session_start": _unix_to_iso(create_time),
        "session_end": _unix_to_iso(update_time),
        "model": model,
        "agent": None,
        "context": None,
        "metrics": {},
        "environment": None,
        "messages": messages,
        "feedback": None,
        "metadata": {
            "import_source": "chatgpt",
            "chatgpt_id": chatgpt_id,
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
    model_filter: str | None = None,
    include_archived: bool = False,
) -> ImportSummary:
    """Import ChatGPT conversations to Jarvis format.

    Args:
        source_path: Path to ChatGPT conversations.json export.
        target_dir: Directory to write converted JSON files.
        dry_run: If True, don't write files, just report what would happen.
        date_from: ISO date string (YYYY-MM-DD). Only import conversations created on or after.
        date_to: ISO date string (YYYY-MM-DD). Only import conversations created on or before.
        model_filter: Only import conversations using this model slug.
        include_archived: If True, include archived conversations.

    Returns:
        ImportSummary with counts and error details.
    """
    summary = ImportSummary()

    with open(source_path) as f:
        conversations = json.load(f)

    summary.total = len(conversations)

    # Parse filter dates
    dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=UTC) if date_from else None
    dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=UTC) if date_to else None
    if dt_to:
        dt_to = dt_to.replace(hour=23, minute=59, second=59)

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    # Track filenames for collision handling within this run
    used_filenames: set[str] = set()
    # Track already-imported chatgpt IDs for idempotent skip
    existing_chatgpt_ids: set[str] = set()
    if not dry_run:
        used_filenames = {p.name for p in target_dir.rglob("*.json")}
        for path in target_dir.rglob("*.json"):
            try:
                data = json.loads(path.read_text())
                cid = data.get("metadata", {}).get("chatgpt_id")
                if cid:
                    existing_chatgpt_ids.add(cid)
            except (json.JSONDecodeError, OSError):
                pass

    for conv in conversations:
        try:
            # Filter: archived
            if conv.get("is_archived") and not include_archived:
                summary.skipped_archived += 1
                continue

            create_time = conv.get("create_time")

            # Filter: date range
            if create_time and (dt_from or dt_to):
                conv_dt = datetime.fromtimestamp(create_time, tz=UTC)
                if dt_from and conv_dt < dt_from:
                    summary.skipped_filter += 1
                    continue
                if dt_to and conv_dt > dt_to:
                    summary.skipped_filter += 1
                    continue

            # Filter: model
            if model_filter and conv.get("default_model_slug") != model_filter:
                summary.skipped_filter += 1
                continue

            # Skip already imported (idempotent by chatgpt_id)
            chatgpt_id = conv.get("conversation_id") or conv.get("id", "")
            if chatgpt_id and chatgpt_id in existing_chatgpt_ids:
                summary.skipped_existing += 1
                continue

            # Generate filename
            update_time = conv.get("update_time")
            ts = create_time or update_time
            ts_dt = datetime.fromtimestamp(ts, tz=UTC) if ts else datetime.now(tz=UTC)
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
            title = conv.get("title", "unknown")
            err_msg = f"Error converting '{title}': {e}"
            logger.error(err_msg)
            summary.errors += 1
            summary.error_details.append(err_msg)

    return summary
