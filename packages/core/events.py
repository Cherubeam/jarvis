"""
Typed event dataclasses for decoupled streaming output.

These events allow multiple consumers (CLI, Web UI, activity feed)
to subscribe to agent output without tight coupling to print() or callbacks.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A chunk of streaming text from an LLM response."""

    text: str
    instance_id: str = ""


@dataclass(frozen=True)
class ToolCallStarted:
    """An agent is invoking a tool."""

    tool_name: str
    tool_call_id: str = ""
    arguments: str = ""
    instance_id: str = ""


@dataclass(frozen=True)
class ToolResult:
    """Result from a tool execution."""

    tool_name: str
    result: str
    tool_call_id: str = ""
    instance_id: str = ""


@dataclass(frozen=True)
class UsageReport:
    """Token usage and cost for a completed LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    instance_id: str = ""


@dataclass(frozen=True)
class DelegationRequested:
    """An agent requested delegation to another agent."""

    target_agent: str
    task: str
    context: str = ""
    instance_id: str = ""


@dataclass(frozen=True)
class AgentStarted:
    """An agent instance has started processing."""

    instance_id: str
    role: str
    task: str = ""


@dataclass(frozen=True)
class AgentFinished:
    """An agent instance has completed processing."""

    instance_id: str
    role: str
    status: str = "completed"  # "completed", "failed", "cancelled"
    result_text: str = ""
    cost_usd: float = 0.0
    error: str = ""


# Union type for all events
Event = (
    TextChunk
    | ToolCallStarted
    | ToolResult
    | UsageReport
    | DelegationRequested
    | AgentStarted
    | AgentFinished
)
