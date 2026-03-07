"""
Agent delegation tool — allows JARVIS to hand off tasks to specialized agents.
"""

from dataclasses import dataclass, field

from packages.core.tools.base import ToolDefinition


@dataclass
class DelegationState:
    """Mutable state set by the delegate tool during the agentic loop."""
    agent_name: str | None = None
    task: str | None = None


def make_delegate_tool(
    available_agents: list[dict],
    state: DelegationState,
) -> ToolDefinition:
    """Create a delegation tool that routes tasks to specialized agents.

    Args:
        available_agents: List of dicts with "name" and "description" keys.
        state: Mutable DelegationState — set when the tool is called.

    Returns:
        A ToolDefinition for agent delegation.
    """
    agent_names = [a["name"] for a in available_agents]

    def _delegate(agent_name: str, task: str) -> str:
        if agent_name not in agent_names:
            return f"Unknown agent '{agent_name}'. Available: {', '.join(agent_names)}"
        state.agent_name = agent_name
        state.task = task
        return f"Delegating to {agent_name} agent."

    return ToolDefinition(
        name="delegate_to_agent",
        description=(
            "Delegate a task to a specialized agent. Use when the user's request "
            "is better handled by a domain expert."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent to delegate to.",
                    "enum": agent_names,
                },
                "task": {
                    "type": "string",
                    "description": "The full task description to pass to the agent.",
                },
            },
            "required": ["agent_name", "task"],
        },
        execute=_delegate,
        terminal=True,
    )
