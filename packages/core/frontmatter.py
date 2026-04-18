"""YAML frontmatter parsing and serialization for markdown files.

`parse` accepts markdown text and returns (metadata, body).
`dump` serializes (metadata, body) back into a full markdown document.
`write_atomic` writes a markdown document to disk via tmp-file + os.replace.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml


def parse(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown. Returns (metadata, body).

    Returns ({}, text) unchanged if no frontmatter delimiters are present.
    """
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            meta = yaml.safe_load(text[4:end]) or {}
            body = text[end + 5:]
            return meta, body
    return {}, text


def dump(metadata: dict, body: str) -> str:
    """Serialize (metadata, body) into a markdown document with frontmatter.

    Preserves insertion order via `sort_keys=False`. Body is appended verbatim.
    If metadata is empty, returns the body alone (no frontmatter block).
    """
    if not metadata:
        return body
    yaml_text = yaml.safe_dump(
        metadata,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_text}---\n{body}"


def write_atomic(path: Path, content: str) -> None:
    """Write content to path atomically via tmp-file + os.replace.

    Creates parent directories if needed. Uses the same parent directory
    for the tmp file so os.replace is atomic on the same filesystem.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
