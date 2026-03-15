"""
Agent registry — discovers and indexes agents by scanning subdirectories.

All delegate agents are data-driven: each folder contains a ``meta.yaml``
with name, description, command, and optional tool_groups / skills / prompt_includes.

JARVIS is excluded from discovery (it is the orchestrator, not a delegate).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

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
    meta_path: Path | None = None
    vault_writing: str | None = None
    tool_groups: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


def _discover_from_meta_yaml(child: Path) -> AgentMeta | None:
    """Try to discover an agent from meta.yaml in the given directory."""
    meta_file = child / "meta.yaml"
    if not meta_file.is_file():
        return None

    try:
        with open(meta_file, encoding="utf-8") as f:
            meta_dict = yaml.safe_load(f)
    except Exception:
        logger.warning("Failed to parse meta.yaml in %s", child.name, exc_info=True)
        return None

    if not meta_dict or "name" not in meta_dict:
        logger.warning("Invalid meta.yaml in %s: missing 'name'", child.name)
        return None

    return AgentMeta(
        name=meta_dict["name"],
        description=meta_dict.get("description", ""),
        command=meta_dict.get("command", f"/{meta_dict['name']}"),
        meta_path=meta_file,
        vault_writing=meta_dict.get("vault_writing"),
        tool_groups=tuple(meta_dict.get("tools", [])),
        skills=tuple(meta_dict.get("skills", [])),
    )



def discover_agents() -> dict[str, AgentMeta]:
    """Scan ``packages/agents/*/`` for agent folders with ``meta.yaml``.

    Returns:
        dict keyed by agent name, values are AgentMeta instances.
    """
    agents: dict[str, AgentMeta] = {}

    for child in sorted(_AGENTS_DIR.iterdir()):
        if not child.is_dir() or child.name in _SKIP_DIRS or child.name.startswith("_"):
            continue

        meta = _discover_from_meta_yaml(child)
        if meta is None:
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
