"""Import Claude context exports (memories + projects) into Jarvis context files."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextImportSummary:
    """Summary of a context import operation."""

    files_written: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    projects_imported: int = 0
    projects_skipped: int = 0
    docs_saved: int = 0
    warnings: list[str] = field(default_factory=list)


# ==================== Parsing ====================


def parse_memory_sections(text: str) -> dict[str, str]:
    """Split Claude conversations_memory on **bold** section headers.

    Returns a dict like {"Work context": "...", "Personal context": "...", ...}.
    """
    if not text or not text.strip():
        return {}

    sections: dict[str, str] = {}
    # Match lines that are bold headers: **Header Name**
    header_pattern = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)

    matches = list(header_pattern.finditer(text))
    if not matches:
        return {}

    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections[name] = body

    return sections


def parse_existing_profile(text: str) -> dict[str, str]:
    """Parse profile.md sections by ## headers.

    Returns a dict like {"Personal Information": "...", "Professional background": "...", ...}.
    """
    if not text or not text.strip():
        return {}

    sections: dict[str, str] = {}
    header_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)

    matches = list(header_pattern.finditer(text))
    if not matches:
        return {}

    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections[name] = body

    return sections


# ==================== Slugify ====================


def slugify_project_name(name: str) -> str:
    """Convert project name to a URL-friendly slug.

    "The Technical Humanist" -> "technical-humanist"
    "Agile Product & Software Development" -> "agile-product-software-development"
    """
    slug = name.lower().strip()
    # Remove leading "the "
    slug = re.sub(r"^the\s+", "", slug)
    # Replace & with empty (remove it)
    slug = slug.replace("&", "")
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to 50 chars at word boundary
    if len(slug) > 50:
        slug = slug[:50].rsplit("-", 1)[0]
    return slug


# ==================== Builders ====================

# Profile sections that map to personal_context.md
_PERSONAL_SECTIONS = {
    "Personal Information",
    "Personality Traits",
    "Learning style",
    "Tools & setup",
}

# Profile sections that map to professional_context.md
_PROFESSIONAL_SECTIONS = {
    "Professional background",
    "Industry Context",
    "Skills & knowledge",
    "Current trajectory",
}


def build_personal_context(
    profile_sections: dict[str, str],
    memory_sections: dict[str, str],
) -> str:
    """Build personal_context.md from profile + Claude memories."""
    parts: list[str] = []
    parts.append("# Personal Context\n")

    # From profile.md
    for section_name in _PERSONAL_SECTIONS:
        if section_name in profile_sections:
            parts.append(f"## {section_name}\n{profile_sections[section_name]}\n")

    # From Claude memories
    personal_memory = memory_sections.get("Personal context")
    if personal_memory:
        parts.append(f"## From Claude Memories\n{personal_memory}\n")

    return "\n".join(parts).rstrip() + "\n"


def build_professional_context(
    profile_sections: dict[str, str],
    memory_sections: dict[str, str],
) -> str:
    """Build professional_context.md from profile + Claude memories."""
    parts: list[str] = []
    parts.append("# Professional Context\n")

    # From profile.md
    for section_name in _PROFESSIONAL_SECTIONS:
        if section_name in profile_sections:
            parts.append(f"## {section_name}\n{profile_sections[section_name]}\n")

    # From Claude memories: work context
    work_memory = memory_sections.get("Work context")
    if work_memory:
        parts.append(f"## From Claude Memories — Work\n{work_memory}\n")

    # From Claude memories: brief history
    history_memory = memory_sections.get("Brief history")
    if history_memory:
        parts.append(f"## From Claude Memories — Career History\n{history_memory}\n")

    return "\n".join(parts).rstrip() + "\n"


def build_current_focus(
    existing_focus: str,
    memory_sections: dict[str, str],
) -> str:
    """Build updated current_focus.md, replacing 'top of mind' section."""
    top_of_mind = memory_sections.get("Top of mind")
    if not top_of_mind:
        return existing_focus

    # Replace the "What's top of mind this week" section if it exists
    pattern = re.compile(
        r"(## What's top of mind this week\n).*?(?=\n## |\Z)",
        re.DOTALL,
    )
    replacement = f"## What's top of mind this week\n{top_of_mind}"

    if pattern.search(existing_focus):
        return pattern.sub(replacement, existing_focus).rstrip() + "\n"
    else:
        # Append at the end
        return existing_focus.rstrip() + f"\n\n{replacement}\n"


def build_project_file(
    name: str,
    memory: str | None,
    prompt_template: str | None,
    doc_filenames: list[str] | None = None,
) -> str:
    """Build a project context markdown file."""
    parts: list[str] = []
    parts.append(f"# {name}\n")

    if memory:
        parts.append(f"## Project Memory\n{memory}\n")

    if prompt_template:
        parts.append(f"## Prompt Template\n{prompt_template}\n")

    if doc_filenames:
        slug = slugify_project_name(name)
        parts.append("## Reference Documents")
        parts.append(f"Available in `data/context/projects/docs/{slug}/`:")
        for doc in doc_filenames:
            parts.append(f"- {doc}")
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


# ==================== Starter Project Detection ====================


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Replace path separators and problematic chars
    sanitized = re.sub(r'[/\\:*?"<>|&]', "-", name)
    sanitized = re.sub(r"-+", "-", sanitized)
    sanitized = sanitized.strip("- ")
    if not sanitized.endswith(".md"):
        sanitized += ".md"
    return sanitized


def _is_starter_project(project: dict[str, Any]) -> bool:
    """Detect Claude starter/template projects that shouldn't be imported."""
    if project.get("is_starter_project"):
        return True
    if project.get("is_starter"):
        return True
    return project.get("type") == "starter"


# ==================== Main Entry Point ====================


def import_context(
    memories_path: Path | None,
    projects_path: Path | None,
    target_dir: Path,
    *,
    existing_profile_path: Path | None = None,
    dry_run: bool = False,
) -> ContextImportSummary:
    """Import Claude context (memories + projects) into Jarvis context files.

    Args:
        memories_path: Path to Claude memories.json export.
        projects_path: Path to Claude projects.json export.
        target_dir: Target context directory (e.g., data/context/).
        existing_profile_path: Path to existing profile.md for data migration.
        dry_run: If True, don't write files, just report what would happen.

    Returns:
        ContextImportSummary with details of what was done.
    """
    summary = ContextImportSummary()

    # Parse memories
    memory_sections: dict[str, str] = {}
    project_memories: dict[str, str] = {}  # uuid -> memory text
    if memories_path and memories_path.exists():
        with open(memories_path) as f:
            memories_raw = json.load(f)

        # Claude exports memories as a list wrapping a single object
        if isinstance(memories_raw, list):
            memories_data = memories_raw[0] if memories_raw else {}
        else:
            memories_data = memories_raw

        # Parse the narrative memory
        conversations_memory = memories_data.get("conversations_memory", "")
        if conversations_memory:
            memory_sections = parse_memory_sections(conversations_memory)

        # Parse per-project memories (dict: uuid -> memory string)
        raw_project_memories = memories_data.get("project_memories", {})
        if isinstance(raw_project_memories, dict):
            for uuid, memory_text in raw_project_memories.items():
                if uuid and memory_text:
                    project_memories[uuid] = memory_text
        elif isinstance(raw_project_memories, list):
            for pm in raw_project_memories:
                uuid = pm.get("project_uuid", "")
                memory_text = pm.get("memory", "")
                if uuid and memory_text:
                    project_memories[uuid] = memory_text
    else:
        if memories_path:
            summary.warnings.append(f"Memories file not found: {memories_path}")

    # Parse existing profile
    profile_sections: dict[str, str] = {}
    if existing_profile_path and existing_profile_path.exists():
        profile_text = existing_profile_path.read_text(encoding="utf-8")
        profile_sections = parse_existing_profile(profile_text)

    # Load existing current_focus
    existing_focus = ""
    focus_path = target_dir / "current_focus.md"
    if focus_path.exists():
        existing_focus = focus_path.read_text(encoding="utf-8")

    # Build personal_context.md
    if profile_sections or memory_sections:
        personal_content = build_personal_context(profile_sections, memory_sections)
        personal_path = target_dir / "personal_context.md"
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            personal_path.write_text(personal_content, encoding="utf-8")
        summary.files_written.append("personal_context.md")

    # Build professional_context.md
    if profile_sections or memory_sections:
        professional_content = build_professional_context(profile_sections, memory_sections)
        professional_path = target_dir / "professional_context.md"
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            professional_path.write_text(professional_content, encoding="utf-8")
        summary.files_written.append("professional_context.md")

    # Build current_focus.md (update top-of-mind)
    if memory_sections.get("Top of mind"):
        updated_focus = build_current_focus(existing_focus, memory_sections)
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            focus_path.write_text(updated_focus, encoding="utf-8")
        summary.files_written.append("current_focus.md")

    # Delete profile.md (content migrated)
    if existing_profile_path and existing_profile_path.exists() and profile_sections:
        if not dry_run:
            existing_profile_path.unlink()
        summary.files_written.append("profile.md (deleted)")

    # Process projects
    projects_by_uuid: dict[str, dict[str, Any]] = {}
    if projects_path and projects_path.exists():
        with open(projects_path) as f:
            projects_data = json.load(f)

        for project in projects_data:
            uuid = project.get("uuid", "")
            if uuid:
                projects_by_uuid[uuid] = project
    else:
        if projects_path:
            summary.warnings.append(f"Projects file not found: {projects_path}")

    # Write project files
    projects_dir = target_dir / "projects"
    for uuid, project in projects_by_uuid.items():
        name = project.get("name", "Untitled")

        if _is_starter_project(project):
            summary.projects_skipped += 1
            continue

        slug = slugify_project_name(name)
        memory = project_memories.get(uuid) or project.get("memory", "")
        prompt_template = project.get("prompt_template", "")

        # Collect doc filenames
        docs = project.get("docs", [])
        doc_filenames = [_sanitize_filename(d.get("filename", d.get("title", "untitled"))) for d in docs if d]

        project_content = build_project_file(name, memory, prompt_template, doc_filenames)
        project_path = projects_dir / f"{slug}.md"

        if not dry_run:
            projects_dir.mkdir(parents=True, exist_ok=True)
            project_path.write_text(project_content, encoding="utf-8")

        summary.files_written.append(f"projects/{slug}.md")
        summary.projects_imported += 1

        # Write docs
        if docs:
            docs_dir = projects_dir / "docs" / slug
            for doc in docs:
                doc_content = doc.get("content", "")
                raw_filename = doc.get("filename", doc.get("title", "untitled"))
                doc_filename = _sanitize_filename(raw_filename)
                if not doc_content:
                    continue
                doc_path = docs_dir / doc_filename
                if not dry_run:
                    docs_dir.mkdir(parents=True, exist_ok=True)
                    doc_path.write_text(doc_content, encoding="utf-8")
                summary.docs_saved += 1

    return summary
