"""
Things 3 write tools — create, complete, and update tasks via URL scheme.

Uses things-py URL scheme helpers (not direct DB writes).
Operations are best-effort: Things 3 processes URLs asynchronously
with no confirmation back to the caller.
"""

import logging
import subprocess
import sys

from packages.core.tools.base import ToolDefinition
from packages.integrations.things3.task_sync import TaskSyncCache

logger = logging.getLogger(__name__)


def _open_things_url(url: str) -> bool:
    """Open a things:/// URL via macOS open command. Returns True on success."""
    result = subprocess.run(["open", url], capture_output=True)
    return result.returncode == 0


def make_things3_tools(config: dict) -> list[ToolDefinition]:
    """Create Things 3 write tools.

    Args:
        config: The things3 section of the config dict.

    Returns:
        List of ToolDefinitions. Empty list on non-macOS platforms.
    """
    if sys.platform != "darwin":
        logger.info("Things 3 tools skipped: macOS only")  # pragma: no mutate
        return []

    import things  # type: ignore[unreachable]

    cache = TaskSyncCache(cache_ttl_seconds=config.get("cache_ttl_seconds", 300))
    tools: list[ToolDefinition] = []

    # --- create_task ---

    def _create_task(
        title: str,
        notes: str = "",
        when: str = "",
        deadline: str = "",
        tags: str = "",
        list_name: str = "",
    ) -> str:
        params: dict[str, str] = {"title": title}
        if notes:
            params["notes"] = notes
        if when:
            params["when"] = when
        if deadline:
            params["deadline"] = deadline
        if tags:
            params["tags"] = tags
        if list_name:
            params["list"] = list_name

        url = things.url(command="add", **params)

        if _open_things_url(url):
            cache.invalidate()
            detail = f" in '{list_name}'" if list_name else ""
            return (
                f"Requested task creation for '{title}'{detail}. "  # pragma: no mutate
                "Changes may take a moment to appear in the task list."  # pragma: no mutate
            )
        return "Error: failed to open Things URL. Is Things 3 installed?"  # pragma: no mutate

    tools.append(
        ToolDefinition(
            name="create_task",
            description=(  # pragma: no mutate
                "Create a new task in Things 3 (best-effort, no confirmation from Things). "
                "Use 'when' for scheduling (e.g. 'today', 'tomorrow', '2026-04-10'). "
                "Use 'deadline' for due dates. Tags are comma-separated. "
                "Use 'list_name' to assign to a project or area."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title (required).",  # pragma: no mutate
                    },
                    "notes": {
                        "type": "string",
                        "description": "Task notes or details.",  # pragma: no mutate
                    },
                    "when": {
                        "type": "string",
                        "description": "When to schedule: 'today', 'tomorrow', 'evening', 'anytime', 'someday', or a date string.",  # pragma: no mutate
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format.",  # pragma: no mutate
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tag names (e.g. 'work,urgent').",  # pragma: no mutate
                    },
                    "list_name": {
                        "type": "string",
                        "description": "Project or area name to add the task to.",  # pragma: no mutate
                    },
                },
                "required": ["title"],
            },
            execute=_create_task,
        )
    )

    # --- complete_task ---

    def _complete_task(uuid: str) -> str:
        if not uuid or not uuid.strip():
            return "Error: uuid is required."  # pragma: no mutate
        uuid = uuid.strip()
        url = things.url(uuid=uuid, command="update", completed=True)

        if _open_things_url(url):
            cache.invalidate()
            return (
                f"Requested completion of task {uuid}. "  # pragma: no mutate
                "Changes may take a moment to appear in the task list."  # pragma: no mutate
            )
        return "Error: failed to open Things URL. Is Things 3 installed?"  # pragma: no mutate

    tools.append(
        ToolDefinition(
            name="complete_task",
            description=(  # pragma: no mutate
                "Mark a Things 3 task as complete by its UUID (best-effort, no confirmation from Things). "
                "Use the ID from the task list in context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "The UUID of the task to complete.",  # pragma: no mutate
                    },
                },
                "required": ["uuid"],
            },
            execute=_complete_task,
        )
    )

    # --- update_task ---

    def _update_task(
        uuid: str,
        title: str = "",
        notes: str = "",
        when: str = "",
        deadline: str = "",
        tags: str = "",
    ) -> str:
        if not uuid or not uuid.strip():
            return "Error: uuid is required."  # pragma: no mutate
        uuid = uuid.strip()
        params: dict[str, str | bool] = {"id": uuid}
        if title:
            params["title"] = title
        if notes:
            params["notes"] = notes
        if when:
            params["when"] = when
        if deadline:
            params["deadline"] = deadline
        if tags:
            params["tags"] = tags

        url = things.url(command="update", **params)

        if _open_things_url(url):
            cache.invalidate()
            return (
                f"Requested update for task {uuid}. "  # pragma: no mutate
                "Changes may take a moment to appear in the task list."  # pragma: no mutate
            )
        return "Error: failed to open Things URL. Is Things 3 installed?"  # pragma: no mutate

    tools.append(
        ToolDefinition(
            name="update_task",
            description=(  # pragma: no mutate
                "Update a Things 3 task by its UUID (best-effort, no confirmation from Things). "
                "Only provided fields are changed. Use the ID from the task list in context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "The UUID of the task to update.",  # pragma: no mutate
                    },
                    "title": {
                        "type": "string",
                        "description": "New task title.",  # pragma: no mutate
                    },
                    "notes": {
                        "type": "string",
                        "description": "New task notes.",  # pragma: no mutate
                    },
                    "when": {
                        "type": "string",
                        "description": "New schedule: 'today', 'tomorrow', 'evening', 'anytime', 'someday', or a date.",  # pragma: no mutate
                    },
                    "deadline": {
                        "type": "string",
                        "description": "New due date in YYYY-MM-DD format.",  # pragma: no mutate
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tag names to set.",  # pragma: no mutate
                    },
                },
                "required": ["uuid"],
            },
            execute=_update_task,
        )
    )

    return tools
