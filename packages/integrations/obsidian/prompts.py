"""
Prompt loader for Obsidian integration.

Loads .md prompt files from data/prompts/obsidian/ at runtime.
Prompts are NOT included in the main system prompt — only loaded
on demand when generating vault content.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default prompts directory relative to project root
_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "prompts" / "obsidian"


def load_obsidian_prompt(
    prompt_name: str, prompts_dir: Path | None = None
) -> str:
    """Load a prompt file by name.

    Args:
        prompt_name: Name of the prompt file (without .md extension).
        prompts_dir: Override for prompts directory. Defaults to
            data/prompts/obsidian/ relative to project root.

    Returns:
        Prompt text content.

    Raises:
        FileNotFoundError: If prompt file does not exist.
    """
    directory = prompts_dir or _DEFAULT_PROMPTS_DIR
    path = directory / f"{prompt_name}.md"

    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    return path.read_text(encoding="utf-8")


def get_daily_note_instructions(prompts_dir: Path | None = None) -> str:
    """Load the daily note entry prompt.

    Convenience wrapper for loading the daily_note_entry prompt.
    """
    return load_obsidian_prompt("daily_note_entry", prompts_dir)
