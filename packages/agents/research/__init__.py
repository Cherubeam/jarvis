"""Research agent — analysis, synthesis, and structured answers."""

from packages.agents.research.agent import ResearchAgent

AGENT_META = {
    "name": "research",
    "description": "Analysis, synthesis, and structured answers",
    "command": "/research",
    "agent_class": ResearchAgent,
}

__all__ = ["ResearchAgent", "AGENT_META"]
