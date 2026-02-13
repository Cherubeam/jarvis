"""Clarity agent — explains complex ideas simply."""

from packages.agents.clarity.agent import ClarityAgent

AGENT_META = {
    "name": "clarity",
    "description": "Explains complex ideas simply",
    "command": "/clarity",
    "agent_class": ClarityAgent,
}

__all__ = ["ClarityAgent", "AGENT_META"]
