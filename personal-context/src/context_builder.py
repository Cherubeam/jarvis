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
    
    The order matters — profile first (who they are), then preferences
    (how to behave), then current focus (what's relevant now).
    """
    sections = []
    
    # Load each context file
    profile = load_context_file(context_dir / "profile.md")
    preferences = load_context_file(context_dir / "preferences.md")
    current_focus = load_context_file(context_dir / "current_focus.md")
    
    # Assemble with clear separation
    if profile:
        sections.append(f"## About this person\n\n{profile}")
    if preferences:
        sections.append(f"## Their preferences\n\n{preferences}")
    if current_focus:
        sections.append(f"## Current focus\n\n{current_focus}")
    
    context_block = "\n\n---\n\n".join(sections)
    
    return f"{prefix.strip()}\n\n{context_block}"