"""
Task synchronization module for Things 3 integration.

Phase A (Current): Uses direct AppleScript with automatic language detection
to fetch tasks from Things 3. This bypasses the MCP server to handle localized
list names (e.g., "Eingang" instead of "Inbox" in German).

Phase B (Future): Will integrate with mcp-server-things3 for interactive
task management (add, complete, search tasks) once the MCP server supports
localized list names or we add a localization wrapper.

Architecture:
- MCPThings3Client class is preserved for Phase B compatibility
- detect_things3_language() auto-detects localized list names
- fetch_tasks_applescript_direct() handles direct AppleScript calls
- fetch_tasks_async() orchestrates fetching with caching
"""

import asyncio
import json
import logging
import subprocess
import sys
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
    notes: str = ""
    due_date: str = ""
    when_date: str = ""
    tags: str = ""
    project: str = ""


class TaskSyncCache:
    """Simple file-based cache for task data to avoid repeated MCP calls."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_file = Path.home() / ".cache" / "jarvis" / "tasks_cache.json"
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> dict | None:
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

    def set(self, tasks: dict) -> None:
        """Cache tasks with timestamp."""
        try:
            data = {"timestamp": datetime.now().isoformat(), "tasks": tasks}
            self.cache_file.write_text(json.dumps(data, indent=2))
            logger.debug("Cached task data")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")


class MCPThings3Client:
    """Client for communicating with mcp-server-things3 via stdio using MCP SDK."""

    def __init__(self, server_command: str = "mcp-server-things3"):
        """
        Initialize the MCP Things3 client.

        Args:
            server_command: Command to start the MCP server (default: mcp-server-things3)
        """
        self.server_command = server_command
        self.session = None
        self.read_stream = None
        self.write_stream = None

    def _find_server_executable(self) -> str:
        """Find the mcp-server-things3 executable in the venv."""
        # Try to find in current venv
        venv_bin = Path(__file__).parent.parent.parent / ".venv" / "bin" / "mcp-server-things3"
        if venv_bin.exists():
            return str(venv_bin)

        # Use Python module directly
        python_executable = sys.executable
        return python_executable

    async def connect(self) -> None:
        """Start the MCP server and initialize session."""
        try:
            from mcp.client.stdio import StdioServerParameters, stdio_client
            from mcp.client.session import ClientSession

            # Find server executable
            server_cmd = self._find_server_executable()

            # For venv installation, use the script directly
            venv_bin = Path(__file__).parent.parent.parent / ".venv" / "bin" / "mcp-server-things3"
            if venv_bin.exists():
                server_params = StdioServerParameters(
                    command=str(venv_bin),
                    args=[],
                )
            else:
                # Fallback to Python module
                server_path = Path("/tmp/mcp-things3/src")
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "mcp_server_things3.server"],
                    env={**subprocess.os.environ, "PYTHONPATH": str(server_path)},
                )

            # Create stdio client context
            self.read_stream, self.write_stream = await stdio_client(server_params).__aenter__()
            self.session = ClientSession(self.read_stream, self.write_stream)
            await self.session.__aenter__()

            # Initialize the session
            await self.session.initialize()

            logger.debug("MCP session initialized")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise RuntimeError(f"Could not connect to mcp-server-things3: {e}")

    async def call_tool(self, tool_name: str, arguments: dict | None = None) -> str:
        """
        Call an MCP tool and return the response.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments (optional)

        Returns:
            Tool response as string
        """
        if not self.session:
            await self.connect()

        try:
            # Call tool using MCP session
            result = await self.session.call_tool(tool_name, arguments or {})

            # Extract text content from response
            if result.content and len(result.content) > 0:
                return result.content[0].text

            return ""
        except Exception as e:
            logger.error(f"MCP tool call failed: {e}")
            raise RuntimeError(f"MCP tool error: {e}")

    async def close(self) -> None:
        """Close the MCP server connection."""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self.read_stream and self.write_stream:
                # The context manager handles cleanup
                pass
            logger.debug("MCP session closed")
        except Exception as e:
            logger.warning(f"Error closing MCP session: {e}")


def parse_task_response(response: str) -> list[Task]:
    """
    Parse task response from MCP server into Task objects.

    Args:
        response: Raw text response from MCP server

    Returns:
        List of Task objects
    """
    tasks = []

    if not response or "No todos found" in response:
        return tasks

    # Parse simple bullet-point format from server
    # Format: • Title (Due: date, When: date)
    lines = response.split("\n")
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("•"):
            continue

        # Extract title and metadata
        content = line[1:].strip()  # Remove bullet point

        # Simple parsing - extract title before parentheses
        if "(" in content:
            title = content[: content.index("(")].strip()
            # Could extract dates if needed, but for context we keep it simple
            tasks.append(Task(title=title))
        else:
            tasks.append(Task(title=content))

    return tasks


def format_tasks_as_markdown(
    inbox_tasks: list[Task],
    today_tasks: list[Task],
    upcoming_tasks: list[Task],
    max_tasks: int = 50,
) -> str:
    """
    Format tasks as markdown for context file.

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
    sections.append(f"\n*Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    # Today section
    if today_tasks:
        sections.append("## Today")
        for task in today_tasks[:max_tasks]:
            sections.append(f"- {task.title}")
        if len(today_tasks) > max_tasks:
            sections.append(f"  *(+{len(today_tasks) - max_tasks} more)*")
        sections.append("")

    # Upcoming section
    if upcoming_tasks:
        sections.append("## Upcoming")
        for task in upcoming_tasks[:max_tasks]:
            sections.append(f"- {task.title}")
        if len(upcoming_tasks) > max_tasks:
            sections.append(f"  *(+{len(upcoming_tasks) - max_tasks} more)*")
        sections.append("")

    # Inbox section
    if inbox_tasks:
        sections.append("## Inbox")
        for task in inbox_tasks[:max_tasks]:
            sections.append(f"- {task.title}")
        if len(inbox_tasks) > max_tasks:
            sections.append(f"  *(+{len(inbox_tasks) - max_tasks} more)*")
        sections.append("")

    if not today_tasks and not upcoming_tasks and not inbox_tasks:
        sections.append("\n*No tasks found.*\n")

    return "\n".join(sections)


def detect_things3_language() -> dict[str, str]:
    """
    Auto-detect Things 3 list names by querying the app.
    Returns mapping of English names to localized names.

    Returns:
        Dictionary mapping English list names to localized names
    """
    try:
        # Get all list names from Things 3
        script = 'tell application "Things3" to get name of every list'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )

        list_names = [name.strip() for name in result.stdout.strip().split(",")]

        # Common translations for Things 3 lists
        # We'll try to match based on known patterns
        translations = {
            "Inbox": None,
            "Today": None,
            "Upcoming": None,
        }

        # Known translations by language
        known_translations = {
            # German
            "Eingang": "Inbox",
            "Heute": "Today",
            "Geplant": "Upcoming",
            # French
            "Boîte de réception": "Inbox",
            "Aujourd'hui": "Today",
            "À venir": "Upcoming",
            # Spanish
            "Recibidos": "Inbox",
            "Hoy": "Today",
            "Próximamente": "Upcoming",
            # Italian
            "In arrivo": "Inbox",
            "Oggi": "Today",
            "Prossimamente": "Upcoming",
        }

        # Match localized names to English equivalents
        for list_name in list_names:
            if list_name in known_translations:
                english_name = known_translations[list_name]
                translations[english_name] = list_name

        # Default to English if not found
        for key in translations:
            if translations[key] is None:
                translations[key] = key

        logger.info(f"Detected Things 3 list names: {translations}")
        return translations

    except Exception as e:
        logger.warning(f"Failed to detect Things 3 language, using English defaults: {e}")
        # Default to English
        return {"Inbox": "Inbox", "Today": "Today", "Upcoming": "Upcoming"}


def fetch_tasks_applescript_direct(list_name: str) -> list[Task]:
    """
    Fetch tasks directly via AppleScript.

    Args:
        list_name: Name of the Things 3 list (e.g., "Eingang", "Heute", "Geplant")

    Returns:
        List of Task objects
    """
    try:
        # AppleScript to get task titles with custom delimiter
        # Use ||| as delimiter since it's unlikely to appear in task titles
        script = f'''
        tell application "Things3"
            set taskList to {{}}
            set todoList to to dos of list "{list_name}"
            repeat with t in todoList
                set taskTitle to name of t
                set end of taskList to taskTitle
            end repeat
            set AppleScript's text item delimiters to "|||"
            set taskString to taskList as string
            set AppleScript's text item delimiters to ""
            return taskString
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        # Parse delimiter-separated task titles
        output = result.stdout.strip()
        if not output or output == "":
            return []

        # Split by our custom delimiter
        task_titles = [title.strip() for title in output.split("|||")]
        return [Task(title=title) for title in task_titles if title]

    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout fetching tasks from {list_name}")
        return []
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to fetch tasks from {list_name}: {e.stderr}")
        return []
    except Exception as e:
        logger.warning(f"Error fetching tasks from {list_name}: {e}")
        return []


async def fetch_tasks_async(
    config: dict, use_cache: bool = True
) -> dict[str, list[Task]]:
    """
    Fetch tasks from Things 3 with automatic language detection.

    This function auto-detects the Things 3 language and uses the appropriate
    list names. It uses direct AppleScript for Phase A, but maintains the
    architecture for future MCP integration in Phase B.

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

    # Auto-detect Things 3 language and get localized list names
    # This ensures we work with any language (German, French, Spanish, etc.)
    list_name_map = detect_things3_language()

    tasks_data = {"inbox": [], "today": [], "upcoming": []}

    try:
        lists_to_include = config.get("lists_to_include", [])

        # Fetch inbox
        if "Inbox" in lists_to_include:
            localized_name = list_name_map.get("Inbox", "Inbox")
            tasks_data["inbox"] = fetch_tasks_applescript_direct(localized_name)
            logger.info(
                f"Fetched {len(tasks_data['inbox'])} tasks from {localized_name} (Inbox)"
            )

        # Fetch today
        if "Today" in lists_to_include:
            localized_name = list_name_map.get("Today", "Today")
            tasks_data["today"] = fetch_tasks_applescript_direct(localized_name)
            logger.info(
                f"Fetched {len(tasks_data['today'])} tasks from {localized_name} (Today)"
            )

        # Fetch upcoming
        if "Upcoming" in lists_to_include:
            localized_name = list_name_map.get("Upcoming", "Upcoming")
            tasks_data["upcoming"] = fetch_tasks_applescript_direct(localized_name)
            logger.info(
                f"Fetched {len(tasks_data['upcoming'])} tasks from {localized_name} (Upcoming)"
            )

    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")

    # Cache results
    cache_data = {
        "inbox": [{"title": t.title} for t in tasks_data["inbox"]],
        "today": [{"title": t.title} for t in tasks_data["today"]],
        "upcoming": [{"title": t.title} for t in tasks_data["upcoming"]],
    }
    cache.set(cache_data)

    return tasks_data


def sync_tasks_to_file(output_path: Path, config: dict) -> bool:
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
        tasks_data = asyncio.run(fetch_tasks_async(config.get("things3", {})))

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
