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

from pathlib import Path

import yaml


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


def build_system_prompt(context_dir: Path, prefix: str) -> str:
    """
    Assemble the full system prompt from context files.

    Order: personal → professional → preferences → current focus → tasks →
           project index → active project contexts.

    Project files with frontmatter `active: false` appear only in the
    project index (summary line). Files without frontmatter default to active.
    """
    sections = []

    # Load split profile files (replaces old profile.md)
    personal = load_context_file(context_dir / "personal_context.md")
    professional = load_context_file(context_dir / "professional_context.md")
    preferences = load_context_file(context_dir / "preferences.md")
    current_focus = load_context_file(context_dir / "current_focus.md")
    tasks = load_context_file(context_dir / "tasks.md")

    # Assemble with clear separation
    if personal:
        sections.append(f"## About this person\n\n{personal}")
    if professional:
        sections.append(f"## Professional context\n\n{professional}")
    if preferences:
        sections.append(f"## Their preferences\n\n{preferences}")
    if current_focus:
        sections.append(f"## Current focus\n\n{current_focus}")
    if tasks:
        sections.append(f"## Their tasks\n\n{tasks}")

    # Load project context files with frontmatter-based filtering
    projects_dir = context_dir / "projects"
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
            sections.append("\n".join(index_lines))

        # Append full content for active projects only
        for _name, _summary, content in active_projects:
            sections.append(f"## Project context\n\n{content}")

    context_block = "\n\n---\n\n".join(sections)

    return f"{prefix.strip()}\n\n{context_block}"
