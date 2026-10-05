"""Turn a Claude memory export into memory proposals for approval (ADR-041).

Reads the 2026-09 export format: ``memories/<account>.json`` with ``memory_files`` (one Markdown
file of ``- [stated] …`` facts per topic, each with ``updated_at``). Facts about the user are routed
to one memory note each; project memories are left to the project mapping (HUB-03).

Imports propose, they never overwrite. A model drafts the proposals per note (add a fact, update a
line), dropping facts the note already covers. Code, not the model, enforces the date rule: a fact
older than the note's ``updated`` date is a conflict that is shown but never applied. Nothing is
written without the user's yes (human oversight, EU AI Act Art. 14); every decision is logged.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core import frontmatter

SOURCE_TAG = "claude-export"

# Export file → memory section (key in paths.context_files). Exact paths first, then prefixes.
_ROUTES_EXACT = {
    "/profile.md": "professional",
    "/topics/communication.md": "preferences",
    "/topics/recent-work.md": "focus",
    "/topics/skills-and-learning.md": "professional",
}
_ROUTES_PREFIX = (
    ("/people/", "professional"),
    ("/areas/", "professional"),
    ("/topics/", "personal"),
)
# Sections an import may propose changes to; soul and reading profile are never touched.
PROPOSABLE_SECTIONS = ("personal", "professional", "preferences", "focus")

# Not archived: login history and account data (ADR-041).
_ARCHIVE_EXCLUDE = ("light_metadata*", ".DS_Store")

_FACT_RE = re.compile(r"^\s*-\s+(?:\[[a-z-]+\]\s+)?(.+?)\s*$")
_JSON_BLOCK_RE = re.compile(r"\[.*\]", re.DOTALL)


@dataclass
class Fact:
    """One fact from the export."""

    id: str
    text: str
    source_file: str
    updated: str  # YYYY-MM-DD


@dataclass
class Proposal:
    """A change to one memory note, drafted by the model and checked by code."""

    section: str
    action: str  # "add" | "update"
    heading: str
    new: str
    old: str | None
    fact_ids: list[str]
    fact_date: str
    reason: str
    conflict: bool = False  # fact older than the note: shown, never applied

    @property
    def appliable(self) -> bool:
        return not self.conflict


@dataclass
class ExportFacts:
    """Facts routed to memory sections, plus what was left out."""

    by_section: dict[str, list[Fact]] = field(default_factory=dict)
    skipped_projects: int = 0
    unrouted: list[str] = field(default_factory=list)


def route(path: str) -> str | None:
    """Memory section for an export file, None for project files and unknown paths."""
    if path in _ROUTES_EXACT:
        return _ROUTES_EXACT[path]
    if path.startswith("/projects/"):
        return None
    for prefix, section in _ROUTES_PREFIX:
        if path.startswith(prefix):
            return section
    return None


def parse_facts(content: str) -> list[str]:
    """Bullet facts of one export file, without the ``[stated]`` marker; frontmatter is skipped."""
    _, body = frontmatter.parse(content)
    facts: list[str] = []
    for line in body.splitlines():
        match = _FACT_RE.match(line)
        if match:
            facts.append(match.group(1))
    return facts


def find_memory_file(export_dir: Path) -> Path:
    """The single memories JSON file of an export directory.

    Lists the folder with ``iterdir`` rather than ``glob``: glob hides a PermissionError (macOS
    blocks terminals without access to Downloads) behind an empty result.
    """
    memories_dir = export_dir / "memories"
    try:
        candidates = sorted(p for p in memories_dir.iterdir() if p.suffix == ".json")
    except PermissionError as e:
        raise ValueError(
            f"No permission to read {memories_dir}. On macOS, give your terminal app access to this "
            "folder (System Settings > Privacy & Security > Files and Folders), or move the export."
        ) from e
    except FileNotFoundError as e:
        raise ValueError(f"No memories folder in {export_dir}") from e
    if len(candidates) != 1:
        raise ValueError(f"Expected one file in {export_dir / 'memories'}, found {len(candidates)}")
    return candidates[0]


def load_export_facts(memory_file: Path) -> ExportFacts:
    """Read the export's memory files and route their facts to memory sections."""
    data = json.loads(memory_file.read_text(encoding="utf-8"))
    result = ExportFacts()
    counter = 0
    for entry in data.get("memory_files", []):
        path = entry.get("path", "")
        section = route(path)
        if section is None:
            if path.startswith("/projects/"):
                result.skipped_projects += 1
            else:
                result.unrouted.append(path)
            continue
        updated = str(entry.get("updated_at", ""))[:10]
        for text in parse_facts(entry.get("content", "")):
            counter += 1
            fact = Fact(id=f"f{counter}", text=text, source_file=path, updated=updated)
            result.by_section.setdefault(section, []).append(fact)
    return result


def export_date(export_dir: Path) -> str:
    """Date the export was created (from its manifest), else today."""
    for manifest in sorted(export_dir.glob("manifest-*.json")):
        try:
            created = json.loads(manifest.read_text(encoding="utf-8")).get("created_at", "")
        except (json.JSONDecodeError, OSError):
            continue
        if created:
            return str(created)[:10]
    return date.today().isoformat()


def archive_export(export_dir: Path, archive_dir: Path) -> bool:
    """Copy the raw export into archive_dir, without login history and account data.

    Returns False when the archive already exists (an export is archived once).
    """
    if archive_dir.exists():
        return False
    shutil.copytree(export_dir, archive_dir, ignore=shutil.ignore_patterns(*_ARCHIVE_EXCLUDE))
    return True


def note_updated(note_text: str) -> str:
    """The note's ``updated`` date (YYYY-MM-DD), or "" if it has none."""
    meta, _ = frontmatter.parse(note_text)
    value = meta.get("updated")
    return str(value)[:10] if value else ""


PROMPT = """You compare facts from a Claude memory export with one of Marco's memory notes and propose \
changes to the note. Marco reviews every proposal; nothing is applied without his yes.

Rules:
- Drop facts the note already says, even in other words. Drop facts that are trivia for this note.
- "add": a fact the note lacks. Give the existing "## heading" it belongs under, or a new heading.
- "update": a fact that changes or contradicts an existing bullet. "old" is that bullet's text \
copied exactly, without the leading "- ".
- Merge related facts into one bullet where natural. Keep Marco's terse bullet style, English.
- Never propose deleting anything.

Answer with a JSON array only, no prose:
[{{"action": "add"|"update", "heading": "...", "old": "..."|null, "new": "...", \
"fact_ids": ["f1"], "reason": "..."}}]
Return [] if nothing is worth proposing.

Memory note "{section}" (last updated {updated}):
<note>
{body}
</note>

Export facts:
{facts}
"""


def build_prompt(section: str, note_text: str, facts: list[Fact]) -> str:
    _, body = frontmatter.parse(note_text)
    fact_lines = "\n".join(f"{f.id} ({f.updated}, {f.source_file}): {f.text}" for f in facts)
    return PROMPT.format(
        section=section, updated=note_updated(note_text) or "unknown", body=body.strip(), facts=fact_lines
    )


def parse_proposals(raw: str, section: str, facts: list[Fact], note_text: str) -> list[Proposal]:
    """Validate the model's JSON and apply the date rule.

    Drops entries with an unknown action, no text, no known fact ids, or (for updates) an ``old``
    line that isn't in the note. Marks proposals whose newest fact is older than the note as conflicts.
    """
    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []

    known = {f.id: f for f in facts}
    _, body = frontmatter.parse(note_text)
    bullets = {_bullet_text(line) for line in body.splitlines() if _bullet_text(line)}
    updated = note_updated(note_text)

    proposals: list[Proposal] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        new = str(item.get("new") or "").strip()
        fact_ids = [i for i in item.get("fact_ids") or [] if i in known]
        if action not in ("add", "update") or not new or not fact_ids:
            continue
        old = str(item.get("old") or "").strip() or None
        if action == "update" and (old is None or old not in bullets):
            continue
        fact_date = max(known[i].updated for i in fact_ids)
        proposals.append(
            Proposal(
                section=section,
                action=action,
                heading=str(item.get("heading") or "").strip().lstrip("#").strip() or "From Claude export",
                new=new,
                old=old if action == "update" else None,
                fact_ids=fact_ids,
                fact_date=fact_date,
                reason=str(item.get("reason") or "").strip(),
                conflict=bool(updated) and fact_date < updated,
            )
        )
    return proposals


def draft_proposals(section: str, note_text: str, facts: list[Fact], complete: Callable[[str], str]) -> list[Proposal]:
    """Ask the model for proposals for one note and validate them."""
    if not facts:
        return []
    raw = complete(build_prompt(section, note_text, facts))
    return parse_proposals(raw, section, facts, note_text)


def _bullet_text(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip()
    return None


def apply_proposal(note_text: str, proposal: Proposal, *, today: str, own_words: bool = False) -> str | None:
    """Return the note with the proposal applied, or None if it no longer fits the note.

    Only the lines involved change. The frontmatter gets ``updated: today``, ``claude-export`` in
    ``source`` and, unless the user typed the text, ``prose`` in ``assist`` (P7).
    """
    if not proposal.appliable:
        return None
    lines = note_text.split("\n")
    body_start = _body_start(lines)

    if proposal.action == "update":
        for i in range(body_start, len(lines)):
            if _bullet_text(lines[i]) == proposal.old:
                indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                lines[i] = f"{indent}- {proposal.new}"
                break
        else:
            return None
    else:
        lines = _insert_under_heading(lines, body_start, proposal.heading, f"- {proposal.new}")

    return _update_frontmatter("\n".join(lines), today=today, add_prose=not own_words)


def _body_start(lines: list[str]) -> int:
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                return i + 1
    return 0


def _insert_under_heading(lines: list[str], body_start: int, heading: str, bullet: str) -> list[str]:
    """Insert bullet after the last line of the ``## heading`` section, or add the section at the end."""
    target = f"## {heading}".lower()
    start = next((i for i in range(body_start, len(lines)) if lines[i].strip().lower() == target), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        return [*lines, "", f"## {heading}", bullet, ""]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    return [*lines[:insert_at], bullet, *lines[insert_at:]]


def _update_frontmatter(text: str, *, today: str, add_prose: bool) -> str:
    """Edit the frontmatter as text, so fields and formatting Obsidian shows stay as they are."""
    lines = text.split("\n")
    end = _body_start(lines) - 1
    if end <= 0:
        return text
    head = lines[1:end]

    def set_scalar(key: str, value: str) -> None:
        for i, line in enumerate(head):
            if line.startswith(f"{key}:"):
                head[i] = f"{key}: {value}"
                return
        head.append(f"{key}: {value}")

    def add_list_item(key: str, value: str) -> None:
        idx = next((i for i, line in enumerate(head) if line.startswith(f"{key}:")), None)
        if idx is None:
            head.extend([f"{key}:", f"  - {value}"])
            return
        inline = head[idx].split(":", 1)[1].strip()
        if inline:
            values = [v.strip() for v in inline.strip("[]").split(",") if v.strip()]
            head[idx : idx + 1] = [f"{key}:", *(f"  - {v}" for v in values)]
        j = idx + 1
        items = []
        while j < len(head) and head[j].startswith("  - "):
            items.append(head[j][4:].strip())
            j += 1
        if value not in items:
            head[idx] = f"{key}:"
            head.insert(j, f"  - {value}")

    set_scalar("updated", today)
    add_list_item("source", SOURCE_TAG)
    if add_prose:
        add_list_item("assist", "prose")
    return "\n".join([lines[0], *head, *lines[end:]])


def log_decision(log_file: Path, proposal: Proposal, decision: str, *, model: str, applied_text: str | None) -> None:
    """Append one decision to the JSONL log (record-keeping, EU AI Act Art. 12)."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "decision": decision,
        "model": model,
        **asdict(proposal),
    }
    if applied_text is not None and applied_text != proposal.new:
        record["applied_text"] = applied_text
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
