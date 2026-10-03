"""
Task synchronization module for Things 3 integration.

Reads Things through the "JARVIS Things Export" Shortcut (see shortcut_source.py
and ADR-037) — no access to Things' database, so no Full Disk Access needed.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.settings import Things3Settings
from packages.integrations.things3.shortcut_source import ThingsUnavailableError, run_export

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Represents a Things 3 task."""

    title: str
    uuid: str = ""
    notes: str = ""
    due_date: str = ""
    when_date: str = ""
    tags: str = ""
    project: str = ""
    area: str = ""


class TaskSyncCache:
    """Simple file-based cache for task data to avoid repeated reads."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_file = Path.home() / ".cache" / "jarvis" / "tasks_cache.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> dict[str, Any] | None:
        """Get cached tasks if not expired."""
        if not self.cache_file.exists():
            return None

        try:
            data = json.loads(self.cache_file.read_text())
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time < timedelta(seconds=self.cache_ttl_seconds):
                logger.debug("Using cached task data")
                tasks: dict[str, Any] = data["tasks"]
                return tasks
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Cache read error: {e}")

        return None

    def set(self, tasks: dict[str, Any]) -> None:
        """Cache tasks with timestamp."""
        try:
            data = {"timestamp": datetime.now().isoformat(), "tasks": tasks}
            self.cache_file.write_text(json.dumps(data, indent=2))
            logger.debug("Cached task data")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    def invalidate(self) -> None:
        """Delete cache file to force fresh read on next fetch."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.debug("Task cache invalidated")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")


# Shortcuts writes dates as localized text (e.g. German "28.09.2026, 00:00"); accept the
# shapes seen so far and fail loudly on anything else rather than silently dropping dates.
_DATE_FORMATS = ("%d.%m.%Y, %H:%M", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")


def _parse_date(value: str) -> date | None:
    """Parse a Shortcut date string; empty → None."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ThingsUnavailableError(f"unrecognised date format from the Shortcut: {value!r}")


def _to_task(item: dict[str, Any]) -> Task:
    """Convert one exported Things item to a Task.

    Things' Shortcuts actions expose a task's parent (project or area) but not both,
    so ``project`` holds the parent's title and ``area`` stays empty. Tags arrive one
    per line.
    """
    start = _parse_date(item.get("startDate", ""))
    deadline = _parse_date(item.get("deadline", ""))
    tags = [t.strip() for t in str(item.get("tags") or "").splitlines() if t.strip()]
    return Task(
        title=str(item.get("title") or ""),
        uuid=str(item.get("id") or ""),
        notes=str(item.get("notes") or ""),
        due_date=deadline.isoformat() if deadline else "",
        when_date=start.isoformat() if start else "",
        tags=", ".join(tags),
        project=str(item.get("parent") or ""),
        area="",
    )


def _split_scheduled(tasks: list[Task], today: date) -> tuple[list[Task], list[Task]]:
    """Today = start date on or before today (incl. overdue), Upcoming = later (things.py semantics)."""
    today_tasks = [t for t in tasks if t.when_date and date.fromisoformat(t.when_date) <= today]
    upcoming = [t for t in tasks if t.when_date and date.fromisoformat(t.when_date) > today]
    return today_tasks, upcoming


def fetch_tasks(things3: Things3Settings, use_cache: bool = True) -> dict[str, list[Task]]:
    """
    Fetch Inbox, Today and Upcoming tasks from Things 3 via the export Shortcut.

    Args:
        things3: Things 3 settings (``lists_to_include`` selects Inbox/Today/Upcoming).
        use_cache: Whether to use cached data if available.

    Returns:
        Dictionary with task lists (inbox, today, upcoming).

    Raises:
        ThingsUnavailableError: the Shortcut couldn't be run or returned unusable data.
            Nothing is cached in that case, so the next call retries.
    """
    cache = TaskSyncCache(cache_ttl_seconds=things3.cache_ttl_seconds)

    if use_cache:
        cached = cache.get()
        if cached:
            return {
                "inbox": [Task(**t) for t in cached.get("inbox", [])],
                "today": [Task(**t) for t in cached.get("today", [])],
                "upcoming": [Task(**t) for t in cached.get("upcoming", [])],
            }

    export = run_export()
    inbox = [_to_task(i) for i in export["inbox"]]
    today, upcoming = _split_scheduled([_to_task(i) for i in export["scheduled"]], date.today())

    wanted = set(things3.lists_to_include)
    tasks_data: dict[str, list[Task]] = {
        "inbox": inbox if "Inbox" in wanted else [],
        "today": today if "Today" in wanted else [],
        "upcoming": upcoming if "Upcoming" in wanted else [],
    }
    unsupported = wanted - {"Inbox", "Today", "Upcoming"}
    if unsupported:
        logger.warning("Things lists not supported by the export and skipped: %s", ", ".join(sorted(unsupported)))
    for key, task_list in tasks_data.items():
        logger.info(f"Fetched {len(task_list)} tasks from {key}")

    cache.set({key: [asdict(t) for t in task_list] for key, task_list in tasks_data.items()})
    return tasks_data


def _format_task_line(task: Task) -> str:
    """Format a single task as a markdown line with metadata."""
    meta_parts = []
    if task.due_date:
        meta_parts.append(f"Due: {task.due_date}")
    if task.tags:
        meta_parts.append(f"Tags: {task.tags}")
    # No task ID: nothing reads it until Things writes exist (ADR-037), and it cost ~19% of tasks.md

    meta_str = f" [{' | '.join(meta_parts)}]" if meta_parts else ""
    line = f"- {task.title}{meta_str}"

    if task.notes:
        truncated = task.notes[:150].replace("\n", " ")
        if len(task.notes) > 150:
            truncated += "..."
        line += f"\n  {truncated}"

    return line


def _format_section(tasks: list[Task], max_tasks: int) -> list[str]:
    """Format a list section grouped by area > project > tasks."""
    lines: list[str] = []
    tasks_to_show = tasks[:max_tasks]

    # Group by area, then project
    grouped: dict[str, dict[str, list[Task]]] = {}
    for task in tasks_to_show:
        area = task.area or ""
        project = task.project or ""
        grouped.setdefault(area, {}).setdefault(project, []).append(task)

    # Sort: named areas first, empty ("Uncategorized") last
    sorted_areas = sorted(grouped.keys(), key=lambda a: (a == "", a))

    for area in sorted_areas:
        # The Shortcut export has no areas; only label the no-area group when named areas exist too
        if area or len(sorted_areas) > 1:
            lines.append(f"### {area or 'Uncategorized'}")

        projects = grouped[area]
        sorted_projects = sorted(projects.keys(), key=lambda p: (p == "", p))

        for project in sorted_projects:
            if project:
                lines.append(f"#### {project}")
            for task in projects[project]:
                lines.append(_format_task_line(task))

        lines.append("")

    if len(tasks) > max_tasks:
        lines.append(f"*(+{len(tasks) - max_tasks} more)*\n")

    return lines


def format_tasks_as_markdown(
    inbox_tasks: list[Task],
    today_tasks: list[Task],
    upcoming_tasks: list[Task],
    max_tasks: int = 50,
) -> str:
    """
    Format tasks as markdown for context file.

    Tasks are grouped by area > project with rich metadata.

    Args:
        inbox_tasks: Tasks from inbox
        today_tasks: Tasks for today
        upcoming_tasks: Upcoming tasks
        max_tasks: Maximum tasks per section

    Returns:
        Markdown formatted string
    """
    sections = []

    # Header
    sections.append("# Tasks from Things 3")
    sections.append(f"\n*Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    sections.append("\n*When presenting tasks, always include all tags in [brackets] next to each task.*\n")

    # Today section
    if today_tasks:
        sections.append("## Today")
        sections.extend(_format_section(today_tasks, max_tasks))

    # Upcoming section
    if upcoming_tasks:
        sections.append("## Upcoming")
        sections.extend(_format_section(upcoming_tasks, max_tasks))

    # Inbox section
    if inbox_tasks:
        sections.append("## Inbox")
        sections.extend(_format_section(inbox_tasks, max_tasks))

    if not today_tasks and not upcoming_tasks and not inbox_tasks:
        sections.append("\n*No tasks found.*\n")

    return "\n".join(sections)


def sync_tasks_to_file(output_path: Path, things3: Things3Settings) -> bool:
    """
    Synchronize tasks from Things 3 to markdown file.

    Args:
        output_path: Path to write tasks.md file.
        things3: Things 3 settings.

    Returns:
        True if sync successful, False otherwise.
    """
    if not things3.enabled:
        logger.debug("Things 3 integration disabled")
        return False

    if not things3.sync_on_startup:
        logger.debug("Sync on startup disabled")
        return False

    try:
        # Fetch tasks (uses cache if available)
        tasks_data = fetch_tasks(things3)
    except ThingsUnavailableError as e:
        # Keep the previous tasks.md: its "Last synced" line stays true, and the model
        # isn't told "No tasks found" when the truth is "couldn't read Things".
        logger.warning(f"Things tasks not refreshed: {e}. Keeping the last tasks.md.")
        return False
    except Exception as e:
        # Never break startup over task sync; same rule: don't overwrite tasks.md
        logger.error(f"Things tasks not refreshed (unexpected error): {e}. Keeping the last tasks.md.")
        return False

    try:
        # Format as markdown
        markdown = format_tasks_as_markdown(
            inbox_tasks=tasks_data.get("inbox", []),
            today_tasks=tasks_data.get("today", []),
            upcoming_tasks=tasks_data.get("upcoming", []),
            max_tasks=things3.max_tasks_per_list,
        )

        # Write to file (the folder may not exist yet, e.g. ~/Library/Caches/JARVIS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)
        logger.info(f"Synced tasks to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to sync tasks: {e}")
        # Don't fail startup - just skip task sync
        return False
