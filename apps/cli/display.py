"""
Terminal display module for the JARVIS CLI.

Centralizes all formatting, colored output, and input handling.
Uses rich for styled output and markdown rendering,
prompt_toolkit for robust multi-line paste support.
"""

import re
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.theme import Theme

from packages.core.pricing import format_cost
from packages.core.stream_handler import StreamResult

# ---------------------------------------------------------------------------
# Theme & console
# ---------------------------------------------------------------------------

JARVIS_THEME = Theme({
    "prompt.you": "bold green",
    "prompt.assistant": "bold cyan",
    "agent.name": "bold cyan",
    "stats": "dim",
    "error": "bold red",
    "system": "dim yellow",
    "tool": "dim magenta",
})

console = Console(theme=JARVIS_THEME, highlight=False)

# ---------------------------------------------------------------------------
# Markdown detection heuristic
# ---------------------------------------------------------------------------

_MARKDOWN_PATTERNS = re.compile(
    r"(?m)"
    r"(?:^```)"          # fenced code block
    r"|(?:^#{1,6}\s)"    # ATX heading
    r"|(?:\*\*.+?\*\*)"  # bold
    r"|(?:^- )"          # unordered list
    r"|(?:^\d+\.\s)"     # ordered list
    r"|(?:`[^`]+`)"      # inline code
)


def _has_markdown(text: str) -> bool:
    """Return True if *text* looks like it contains markdown formatting."""
    return bool(_MARKDOWN_PATTERNS.search(text))


# ---------------------------------------------------------------------------
# Startup & banners
# ---------------------------------------------------------------------------

def print_startup(
    agent_name: str,
    model_id: str,
    price_info: str,
    commands: list[str] | None = None,
) -> None:
    """Print the styled startup banner."""
    console.print("Personal Assistant", style="bold")
    console.print(
        f"Agent: [agent.name]{agent_name}[/] | Model: {model_id} {price_info}",
    )
    if commands:
        console.print(f"Commands: {' '.join(commands)}")
    console.print("Type 'quit' or 'exit' to end. Ctrl+C also works.\n")


# ---------------------------------------------------------------------------
# Prefixes & labels
# ---------------------------------------------------------------------------

def print_assistant_prefix(agent_name: str = "JARVIS") -> None:
    """Print the assistant label before streaming begins."""
    console.print(f"\n[prompt.assistant]{agent_name}:[/] ", end="")


def print_agent_prefix(agent_name: str) -> None:
    """Print a colored agent label for slash-command responses."""
    console.print(f"\n[agent.name][{agent_name}]:[/] ", end="")


# ---------------------------------------------------------------------------
# Post-stream markdown rendering
# ---------------------------------------------------------------------------

def render_response(text: str) -> None:
    """Render the completed response, optionally with markdown formatting.

    After streaming finishes (raw chunks already on screen), this function
    moves the cursor back, clears the raw text, and reprints with rich
    Markdown rendering — but only when the response actually contains
    markdown syntax.  Plain-text answers are left as-is with just a
    trailing newline.
    """
    if not text.strip():
        print()
        return

    if not _has_markdown(text):
        # Plain text — just add a trailing newline after the streamed output
        print("\n")
        return

    # Count lines of the raw streamed output so we can overwrite them.
    # +1 accounts for the partial line that didn't end with \n.
    raw_lines = text.count("\n") + 1

    # Move cursor up and clear each line
    for _ in range(raw_lines):
        sys.stdout.write("\033[A\033[2K")
    sys.stdout.flush()

    console.print(Markdown(text))
    print()


# ---------------------------------------------------------------------------
# Stats & feedback
# ---------------------------------------------------------------------------

def print_usage_stats(result: StreamResult) -> None:
    """Print dim-styled token usage, cost, and latency stats."""
    ttft_str = f"TTFT: {result.metrics.ttft_ms:.0f}ms"
    latency_str = f"Total: {result.metrics.total_latency_ms:.0f}ms"
    if result.cost_usd > 0:
        line = f"[{result.usage.total_tokens:,} tokens | {format_cost(result.cost_usd)} | {ttft_str} | {latency_str}]"
    else:
        line = f"[{result.usage.total_tokens:,} tokens | {ttft_str} | {latency_str}]"
    console.print(line, style="stats")


def print_separator() -> None:
    """Print a blank line to visually separate sections."""
    print()


def print_tool_feedback(tool_name: str) -> None:
    """Print styled feedback when a tool is invoked."""
    console.print(f"[tool][Tool: {tool_name}][/]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(message, style="error")


def print_system(message: str) -> None:
    """Print a system/informational message."""
    console.print(message, style="system")


# ---------------------------------------------------------------------------
# Input handling (prompt_toolkit)
# ---------------------------------------------------------------------------

def create_prompt_session(history_file: str | None = None):
    """Create a prompt_toolkit PromptSession with optional file history.

    Returns a PromptSession configured for robust paste handling.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    kwargs: dict = {}
    if history_file:
        path = Path(history_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        kwargs["history"] = FileHistory(str(path))

    return PromptSession(**kwargs)


def prompt_user(session) -> str:
    """Prompt the user for input using prompt_toolkit.

    Returns the stripped user input.
    Raises EOFError on Ctrl-D.
    """
    from prompt_toolkit.formatted_text import HTML

    return session.prompt(HTML("<ansigreen><b>You: </b></ansigreen>")).strip()
