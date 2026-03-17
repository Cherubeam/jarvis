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

    # Load project context files with frontmatter-based filtering
    projects_dir = context_dir / "projects"
    projects_total_bytes = 0
    projects_total_tokens = 0

    if projects_dir.is_dir():
        active_projects = []   # (name, summary, content)
        inactive_projects = [] # (name, summary)

        for project_file in sorted(projects_dir.glob("*.md")):
            raw = load_context_file(project_file)
            if not raw:
                continue

            meta, content = parse_frontmatter(raw)
            is_active = meta.get("active", True)  # default to active
            summary = meta.get("summary", "")
            name = project_file.stem.replace("-", " ").replace("_", " ").title()

            if is_active:
                active_projects.append((name, summary, content))
            else:
                inactive_projects.append((name, summary))

        # Build project index if any projects exist
        if active_projects or inactive_projects:
            index_lines = ["## Project index", ""]
            if active_projects:
                index_lines.append("Active projects (full context below):")
                for name, summary, _ in active_projects:
                    line = f"- {name}"
                    if summary:
                        line += f": {summary}"
                    index_lines.append(line)
            if inactive_projects:
                if active_projects:
                    index_lines.append("")
                index_lines.append("Other projects (context available on request):")
                for name, summary in inactive_projects:
                    line = f"- {name}"
                    if summary:
                        line += f": {summary}"
                    index_lines.append(line)
            index_text = "\n".join(index_lines)
            sections.append(index_text)
            projects_total_bytes += len(index_text.encode("utf-8"))
            projects_total_tokens += _approx_tokens(index_text)

        # Append full content for active projects only
        for _name, _summary, content in active_projects:
            section_text = f"## Project context\n\n{content}"
            sections.append(section_text)
            projects_total_bytes += len(section_text.encode("utf-8"))
            projects_total_tokens += _approx_tokens(section_text)

    if projects_total_tokens > 0:
        metadata.sections.append(ContextSection(
            name="projects", size_bytes=projects_total_bytes,
            approx_tokens=projects_total_tokens,
        ))

    context_block = "\n\n---\n\n".join(sections)

    if soul:
        prompt = f"{soul.strip()}\n\n{context_block}" if context_block else soul.strip()
    else:
        prompt = context_block

    metadata.total_approx_tokens = _approx_tokens(prompt)

    return prompt, metadata
