"""
Task synchronization module for Things 3 integration.

Uses things.py to read the Things 3 SQLite database directly,
eliminating AppleScript timeouts and localization issues.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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
                return data["tasks"]
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


def _to_task(t: dict[str, Any]) -> Task:
    """Convert a things.py task dict to a Task dataclass."""
    return Task(
        title=t.get("title", ""),
        uuid=t.get("uuid", ""),
        notes=t.get("notes", "") or "",
        due_date=t.get("deadline", "") or "",
        when_date=t.get("start_date", "") or "",
        tags=", ".join(t.get("tags", []) or []),
        project=t.get("project_title", "") or "",
        area=t.get("area_title", "") or "",
    )


def fetch_tasks(config: dict[str, Any], use_cache: bool = True) -> dict[str, list[Task]]:
    """
    Fetch tasks from Things 3 via SQLite (things.py).

    Args:
        config: Configuration dictionary with Things 3 settings
        use_cache: Whether to use cached data if available

    Returns:
        Dictionary with task lists (inbox, today, upcoming)
    """
    cache = TaskSyncCache(cache_ttl_seconds=config.get("cache_ttl_seconds", 300))

    # Check cache first
    if use_cache:
        cached = cache.get()
        if cached:
            return {
                "inbox": [Task(**t) for t in cached.get("inbox", [])],
                "today": [Task(**t) for t in cached.get("today", [])],
                "upcoming": [Task(**t) for t in cached.get("upcoming", [])],
            }

    import things

    tasks_data: dict[str, list[Task]] = {"inbox": [], "today": [], "upcoming": []}
    lists_to_include = config.get("lists_to_include", [])

    try:
        if "Inbox" in lists_to_include:
            tasks_data["inbox"] = [_to_task(t) for t in things.inbox()]
            logger.info(f"Fetched {len(tasks_data['inbox'])} tasks from Inbox")

        if "Today" in lists_to_include:
            tasks_data["today"] = [_to_task(t) for t in things.today()]
            logger.info(f"Fetched {len(tasks_data['today'])} tasks from Today")

        if "Upcoming" in lists_to_include:
            tasks_data["upcoming"] = [_to_task(t) for t in things.upcoming()]
            logger.info(f"Fetched {len(tasks_data['upcoming'])} tasks from Upcoming")

    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")

    # Cache results
    cache_data: dict[str, list[dict[str, Any]]] = {}
    for key, task_list in tasks_data.items():
        cache_data[key] = [
            {
                "title": t.title,
                "uuid": t.uuid,
                "notes": t.notes,
                "due_date": t.due_date,
                "when_date": t.when_date,
                "tags": t.tags,
                "project": t.project,
                "area": t.area,
            }
            for t in task_list
        ]
    cache.set(cache_data)

    return tasks_data


def _format_task_line(task: Task) -> str:
    """Format a single task as a markdown line with metadata."""
    meta_parts = []
    if task.due_date:
        meta_parts.append(f"Due: {task.due_date}")
    if task.tags:
        meta_parts.append(f"Tags: {task.tags}")
    if task.uuid:
        meta_parts.append(f"ID: {task.uuid}")

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
        area_heading = area if area else "Uncategorized"
        lines.append(f"### {area_heading}")

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


def sync_tasks_to_file(output_path: Path, config: dict[str, Any]) -> bool:
    """
    Synchronize tasks from Things 3 to markdown file.

    Args:
        output_path: Path to write tasks.md file
        config: Configuration dictionary with Things 3 settings

    Returns:
        True if sync successful, False otherwise
    """
    # Check if Things 3 integration is enabled
    if not config.get("things3", {}).get("enabled", False):
        logger.debug("Things 3 integration disabled")
        return False

    # Check if sync on startup is enabled
    if not config.get("things3", {}).get("sync_on_startup", True):
        logger.debug("Sync on startup disabled")
        return False

    try:
        # Fetch tasks (uses cache if available)
        tasks_data = fetch_tasks(config.get("things3", {}))

        # Format as markdown
        markdown = format_tasks_as_markdown(
            inbox_tasks=tasks_data.get("inbox", []),
            today_tasks=tasks_data.get("today", []),
            upcoming_tasks=tasks_data.get("upcoming", []),
            max_tasks=config.get("things3", {}).get("max_tasks_per_list", 50),
        )

        # Write to file
        output_path.write_text(markdown)
        logger.info(f"Synced tasks to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to sync tasks: {e}")
        # Don't fail startup - just skip task sync
        return False
