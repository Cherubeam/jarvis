"""Navigator agent — personal alignment, goal clarity, and structured reviews."""

from packages.agents.navigator.agent import NavigatorAgent

AGENT_META = {
    "name": "navigator",
    "description": "Personal alignment, goal clarity, and structured reviews",
    "command": "/navigator",
    "agent_class": NavigatorAgent,
}

__all__ = ["NavigatorAgent", "AGENT_META"]
