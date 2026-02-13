"""
Agent registry — discovers and indexes agents by scanning subdirectories.

Each agent folder must export an ``AGENT_META`` dict from its ``__init__.py``:

    AGENT_META = {
        "name": "writing",
        "description": "Refined prose, editing, and rewriting",
        "command": "/write",
        "agent_class": WritingAgent,
    }

JARVIS is excluded from discovery (it is the orchestrator, not a delegate).
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_AGENTS_PACKAGE = "packages.agents"
_AGENTS_DIR = Path(__file__).parent

# Folders to skip during discovery
_SKIP_DIRS = {"__pycache__", "jarvis"}


@dataclass(frozen=True)
class AgentMeta:
    """Metadata for a discovered agent."""
    name: str
    description: str
    command: str
    agent_class: type[BaseAgent]


def discover_agents() -> dict[str, AgentMeta]:
    """Scan ``packages/agents/*/`` for folders exporting ``AGENT_META``.

    Returns:
        dict keyed by agent name, values are AgentMeta instances.
    """
    agents: dict[str, AgentMeta] = {}

    for child in sorted(_AGENTS_DIR.iterdir()):
        if not child.is_dir() or child.name in _SKIP_DIRS or child.name.startswith("_"):
            continue

        init_file = child / "__init__.py"
        if not init_file.is_file():
            continue

        module_name = f"{_AGENTS_PACKAGE}.{child.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception:
            logger.warning("Failed to import agent module %s", module_name, exc_info=True)
            continue

        meta_dict = getattr(module, "AGENT_META", None)
        if meta_dict is None:
            continue

        try:
            meta = AgentMeta(
                name=meta_dict["name"],
                description=meta_dict["description"],
                command=meta_dict["command"],
                agent_class=meta_dict["agent_class"],
            )
        except (KeyError, TypeError) as exc:
            logger.warning("Invalid AGENT_META in %s: %s", module_name, exc)
            continue

        agents[meta.name] = meta

    return agents


def get_by_command(command: str, agents: dict[str, AgentMeta] | None = None) -> AgentMeta | None:
    """Look up an agent by its slash command.

    Args:
        command: The slash command string (e.g. ``"/write"``).
        agents: Pre-discovered agents dict. If *None*, calls
            :func:`discover_agents` on the fly.

    Returns:
        The matching AgentMeta, or *None* if no agent handles this command.
    """
    if agents is None:
        agents = discover_agents()

    for meta in agents.values():
        if meta.command == command:
            return meta
    return None
