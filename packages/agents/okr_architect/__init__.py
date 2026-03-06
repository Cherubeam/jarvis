"""OKR Architect agent — design, implement, and track effective OKRs."""

from packages.agents.okr_architect.agent import OKRArchitectAgent

AGENT_META = {
    "name": "okr-architect",
    "description": "Design, implement, and track effective OKRs",
    "command": "/okr-architect",
    "agent_class": OKRArchitectAgent,
}

__all__ = ["OKRArchitectAgent", "AGENT_META"]
