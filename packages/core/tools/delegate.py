"""
Agent delegation tools — allows JARVIS to hand off tasks to specialized
agents or trigger multi-agent workflows.
"""

from dataclasses import dataclass, field

from packages.core.tools.base import ToolDefinition


@dataclass
class DelegationState:
    """Mutable state set by the delegate tool during the agentic loop."""
    agent_name: str | None = None
    task: str | None = None
    context: str | None = None
    workflow_name: str | None = None
    workflow_inputs: dict[str, str] | None = None


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

    def _delegate(agent_name: str, task: str, context: str = "") -> str:
        if agent_name not in agent_names:
            return f"Unknown agent '{agent_name}'. Available: {', '.join(agent_names)}"
        state.agent_name = agent_name
        state.task = task
        state.context = context or None
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
                "context": {
                    "type": "string",
                    "description": (
                        "Relevant conversation context for the agent. "
                        "Summarize key details, preferences, and constraints "
                        "the user mentioned that are relevant to this task."
                    ),
                },
            },
            "required": ["agent_name", "task"],
        },
        execute=_delegate,
        terminal=True,
    )


def make_workflow_tool(
    available_workflows: list[dict],
    state: DelegationState,
) -> ToolDefinition:
    """Create a workflow tool that triggers multi-agent workflows.

    Args:
        available_workflows: List of dicts with "name" and "description" keys.
        state: Mutable DelegationState — set when the tool is called.

    Returns:
        A ToolDefinition for workflow triggering.
    """
    workflow_names = [w["name"] for w in available_workflows]

    def _run_workflow(workflow_name: str, inputs: str = "{}") -> str:
        import json

        if workflow_name not in workflow_names:
            return f"Unknown workflow '{workflow_name}'. Available: {', '.join(workflow_names)}"

        try:
            parsed_inputs = json.loads(inputs) if isinstance(inputs, str) else inputs
        except json.JSONDecodeError:
            return f"Invalid inputs JSON: {inputs}"

        state.workflow_name = workflow_name
        state.workflow_inputs = parsed_inputs
        return f"Triggering workflow '{workflow_name}'."

    workflow_descriptions = "\n".join(
        f"- {w['name']}: {w.get('description', 'No description')}"
        for w in available_workflows
    )

    return ToolDefinition(
        name="run_workflow",
        description=(
            "Trigger a multi-agent workflow. Use when a task requires "
            "coordinated work across multiple specialized agents.\n\n"
            f"Available workflows:\n{workflow_descriptions}"
        ),
        parameters={
            "type": "object",
            "properties": {
                "workflow_name": {
                    "type": "string",
                    "description": "Name of the workflow to run.",
                    "enum": workflow_names,
                },
                "inputs": {
                    "type": "string",
                    "description": (
                        "JSON object with input variables for the workflow. "
                        "E.g., '{\"topic\": \"Quantum Computing\"}'"
                    ),
                },
            },
            "required": ["workflow_name"],
        },
        execute=_run_workflow,
        terminal=True,
    )
