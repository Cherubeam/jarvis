"""Writing agent — write and edit in Marco's authentic voice."""

from packages.agents.writing.agent import WritingAgent

AGENT_META = {
    "name": "writing",
    "description": "Write and edit in Marco's authentic voice",
    "command": "/write",
    "agent_class": WritingAgent,
}

__all__ = ["WritingAgent", "AGENT_META"]
