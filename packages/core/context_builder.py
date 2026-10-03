"""
Reads context files and assembles them into a system prompt.
This is intentionally simple — just file reading and string concatenation.

Project files support YAML frontmatter for selective loading:
  ---
  active: true
  topics: [python, ai]
  summary: "One-line project description"
  ---
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from packages.core.settings import ContextFilesSettings

logger = logging.getLogger(__name__)


def _approx_tokens(text: str) -> int:
    """Approximate token count from text (1 token ≈ 4 bytes for English)."""
    return len(text.encode("utf-8")) // 4


@dataclass
class ContextSection:
    """Metadata for a single section of the system prompt."""

    name: str
    size_bytes: int
    approx_tokens: int


@dataclass
class ContextMetadata:
    """Metadata about the assembled system prompt, for instrumentation."""

    total_approx_tokens: int = 0
    sections: list[ContextSection] = field(default_factory=list)

    def section_percentages(self) -> dict[str, float]:
        """Return each section's percentage of total tokens."""
        if self.total_approx_tokens == 0:
            return {}
        return {s.name: (s.approx_tokens / self.total_approx_tokens) * 100 for s in self.sections}


def load_context_file(filepath: Path) -> str:
    """Load a single markdown file, return empty string if missing."""
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from markdown. Returns (metadata, content).

    Backward-compat re-export of :func:`packages.core.frontmatter.parse`.
    """
    from packages.core import frontmatter as _fm

    return _fm.parse(text)


def strip_frontmatter(text: str, name: str = "context file") -> str:
    """Return ``text`` without its YAML frontmatter block (e.g. ``updated``/``source``).

    Text without frontmatter is returned unchanged. Malformed frontmatter is left
    in place rather than guessed at, with a warning naming the file: it would
    otherwise reach the prompt unnoticed.
    """
    from packages.core import frontmatter as _fm

    try:
        _meta, body = _fm.parse(text)
    except yaml.YAMLError as e:
        logger.warning(  # pragma: no mutate
            "Invalid YAML frontmatter in %s; it stays in the system prompt. "  # pragma: no mutate
            "Quote values that contain ': '. (%s)",  # pragma: no mutate
            name,
            str(e).splitlines()[0],
        )
        return text
    if body == text:
        return text
    return body.lstrip("\n")


def build_system_prompt(
    context_dir: Path,
    context_files: ContextFilesSettings | None = None,
    tasks_file: Path | None = None,
) -> str:
    """
    Assemble the full system prompt from context files.

    Identity comes from the soul file (placed first in the prompt).
    Order: soul → personal → professional → preferences → current focus → tasks → reading.

    ``context_files`` names each file relative to ``context_dir`` (default: today's
    names, e.g. ``soul.md``); ``tasks_file`` defaults to ``context_dir / "tasks.md"``.
    YAML frontmatter is stripped from every file; missing files are skipped.
    """
    prompt, _metadata = build_system_prompt_with_metadata(context_dir, context_files, tasks_file)
    return prompt


def build_system_prompt_with_metadata(
    context_dir: Path,
    context_files: ContextFilesSettings | None = None,
    tasks_file: Path | None = None,
) -> tuple[str, ContextMetadata]:
    """
    Assemble the full system prompt and return section-level metadata.

    Returns (prompt_text, metadata) where metadata contains per-section
    token counts (of the frontmatter-stripped text) for instrumentation.
    """
    files = context_files or ContextFilesSettings()
    tasks_path = tasks_file if tasks_file is not None else context_dir / "tasks.md"
    metadata = ContextMetadata()

    soul = strip_frontmatter(load_context_file(context_dir / files.soul), name=files.soul)
    if soul:
        metadata.sections.append(
            ContextSection(
                name="soul",
                size_bytes=len(soul.encode("utf-8")),
                approx_tokens=_approx_tokens(soul),
            )
        )

    sections = []

    context_sections = [
        ("personal", context_dir / files.personal, "## About this person\n\n"),
        ("professional", context_dir / files.professional, "## Professional context\n\n"),
        ("preferences", context_dir / files.preferences, "## Their preferences\n\n"),
        ("focus", context_dir / files.focus, "## Current focus\n\n"),
        ("tasks", tasks_path, "## Their tasks\n\n"),
        ("reading", context_dir / files.reading, "## Reading profile\n\n"),
    ]

    for section_name, path, header in context_sections:
        content = strip_frontmatter(load_context_file(path), name=path.name)
        if content:
            section_text = f"{header}{content}"
            sections.append(section_text)
            metadata.sections.append(
                ContextSection(
                    name=section_name,
                    size_bytes=len(section_text.encode("utf-8")),
                    approx_tokens=_approx_tokens(section_text),
                )
            )

    context_block = "\n\n---\n\n".join(sections)

    if soul:
        prompt = f"{soul.strip()}\n\n{context_block}" if context_block else soul.strip()
    else:
        prompt = context_block

    metadata.total_approx_tokens = _approx_tokens(prompt)

    return prompt, metadata
