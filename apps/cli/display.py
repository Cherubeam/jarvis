"""
Terminal display module for the JARVIS CLI.

Centralizes all formatting, colored output, and input handling.
Uses rich for styled output and markdown rendering,
prompt_toolkit for robust multi-line paste support.
"""

import re
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text
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
    console.print("Type /exit or /quit to end.\n")


# ---------------------------------------------------------------------------
# Prefixes & labels
# ---------------------------------------------------------------------------

def print_assistant_prefix(agent_name: str = "JARVIS") -> None:
    """Print the assistant label before streaming begins."""
    console.print(f"\n[prompt.assistant]{agent_name}:[/]")


def print_agent_prefix(agent_name: str) -> None:
    """Print a colored agent label for slash-command responses."""
    console.print(f"\n[agent.name][{agent_name}]:[/]")


# ---------------------------------------------------------------------------
# Live streaming display
# ---------------------------------------------------------------------------

def start_live_stream() -> tuple[Live, list[str]]:
    """Create and start a rich.Live context for streaming output.

    Returns (live, buffer) where buffer is a list that accumulates chunks.
    """
    live = Live(Text(""), console=console, refresh_per_second=8, vertical_overflow="crop")
    live.start()
    return live, []


def make_live_chunk_handler(live: Live, buf: list[str]) -> Callable[[str], None]:
    """Return a closure that appends chunks to *buf* and updates the Live display."""
    def handler(chunk: str) -> None:
        buf.append(chunk)
        live.update(Text("".join(buf)))
    return handler


def finish_live_stream(live: Live, full_text: str) -> None:
    """Finish the live display, rendering markdown if detected.

    Replaces the raw streamed text with a rich Markdown rendering in-place
    when markdown syntax is detected; otherwise leaves the plain text as-is.
    """
    if full_text.strip() and _has_markdown(full_text):
        live.update(Markdown(full_text))
    live.stop()


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
    console.print()
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
