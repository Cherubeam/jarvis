"""Developer agent — JARVIS self-improvement via codebase awareness."""

from packages.agents.developer.agent import DeveloperAgent

AGENT_META = {
    "name": "developer",
    "description": "JARVIS self-improvement agent — reads codebase, creates branches, writes data-driven files, runs tests, commits changes",
    "command": "/develop",
    "agent_class": DeveloperAgent,
}

__all__ = ["DeveloperAgent", "AGENT_META"]
