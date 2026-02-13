"""Writing agent — refined prose, editing, and rewriting."""

from packages.agents.writing.agent import WritingAgent

AGENT_META = {
    "name": "writing",
    "description": "Refined prose, editing, and rewriting",
    "command": "/write",
    "agent_class": WritingAgent,
}

__all__ = ["WritingAgent", "AGENT_META"]
