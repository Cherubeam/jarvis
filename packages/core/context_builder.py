"""
Reads context files and assembles them into a system prompt.
This is intentionally simple — just file reading and string concatenation.
"""

from pathlib import Path


def load_context_file(filepath: Path) -> str:
    """Load a single markdown file, return empty string if missing."""
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return ""


def build_system_prompt(context_dir: Path, prefix: str) -> str:
    """
    Assemble the full system prompt from context files.

    Order: personal → professional → preferences → current focus → tasks → projects.
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

    # Load project context files
    projects_dir = context_dir / "projects"
    if projects_dir.is_dir():
        for project_file in sorted(projects_dir.glob("*.md")):
            content = load_context_file(project_file)
            if content:
                sections.append(f"## Project context\n\n{content}")

    context_block = "\n\n---\n\n".join(sections)

    return f"{prefix.strip()}\n\n{context_block}"
