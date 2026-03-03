"""Tactics agent — cross-deck Pip Decks coaching orchestrator."""

from packages.agents.tactics.agent import TacticsAgent

AGENT_META = {
    "name": "tactics",
    "description": "Pip Decks tactics coaching — storytelling, workshops, ideation",
    "command": "/tactics",
    "agent_class": TacticsAgent,
}

__all__ = ["TacticsAgent", "AGENT_META"]
