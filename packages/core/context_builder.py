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

from dataclasses import dataclass, field
from pathlib import Path

import yaml


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
        return {
            s.name: (s.approx_tokens / self.total_approx_tokens) * 100
            for s in self.sections
        }


def load_context_file(filepath: Path) -> str:
    """Load a single markdown file, return empty string if missing."""
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown. Returns (metadata, content)."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            frontmatter = yaml.safe_load(text[4:end]) or {}
            content = text[end + 5:]  # skip past closing ---\n
            return frontmatter, content
    return {}, text


def build_system_prompt(context_dir: Path) -> str:
    """
    Assemble the full system prompt from context files.

    Identity comes from soul.md (placed first in the prompt).
    Order: soul → personal → professional → preferences → current focus → tasks →
           project index → active project contexts.

    Project files with frontmatter `active: false` appear only in the
    project index (summary line). Files without frontmatter default to active.
    """
    prompt, _metadata = build_system_prompt_with_metadata(context_dir)
    return prompt


def build_system_prompt_with_metadata(context_dir: Path) -> tuple[str, ContextMetadata]:
    """
    Assemble the full system prompt and return section-level metadata.

    Returns (prompt_text, metadata) where metadata contains per-section
    token counts for instrumentation.
    """
    metadata = ContextMetadata()

    soul = load_context_file(context_dir / "soul.md")
    if soul:
        metadata.sections.append(ContextSection(
            name="soul", size_bytes=len(soul.encode("utf-8")),
            approx_tokens=_approx_tokens(soul),
        ))

    sections = []

    # Load split profile files (replaces old profile.md)
    context_files = [
        ("personal", "personal_context.md", "## About this person\n\n"),
        ("professional", "professional_context.md", "## Professional context\n\n"),
        ("preferences", "preferences.md", "## Their preferences\n\n"),
        ("focus", "current_focus.md", "## Current focus\n\n"),
        ("tasks", "tasks.md", "## Their tasks\n\n"),
        ("reading", "reader_persona.md", "## Reading profile\n\n"),
    ]

    for section_name, filename, header in context_files:
        content = load_context_file(context_dir / filename)
        if content:
            section_text = f"{header}{content}"
            sections.append(section_text)
            metadata.sections.append(ContextSection(
                name=section_name, size_bytes=len(section_text.encode("utf-8")),
                approx_tokens=_approx_tokens(section_text),
            ))

    context_block = "\n\n---\n\n".join(sections)

    if soul:
        prompt = f"{soul.strip()}\n\n{context_block}" if context_block else soul.strip()
    else:
        prompt = context_block

    metadata.total_approx_tokens = _approx_tokens(prompt)

    return prompt, metadata
