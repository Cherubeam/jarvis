"""
JARVIS - Main orchestrator agent.

This is the primary agent that coordinates other agents and handles
direct user interactions. It can delegate tasks to specialized agents.
"""

from pathlib import Path

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.context_builder import build_system_prompt
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.tools.base import ToolDefinition
from packages.core.tools.delegate import DelegationState, make_delegate_tool

_SPECIAL_HINTS: dict[str, str] = {
    "developer": " (uses a git sandbox — creates branches, commits safely, never pushes)",
}


def _build_delegation_directive(available_agents: list[dict]) -> str:
    """Build the delegation directive dynamically from discovered agents.

    Args:
        available_agents: List of dicts with "name" and "description" keys.

    Returns:
        Directive string to append to the system prompt.
    """
    if not available_agents:
        return ""

    agent_lines = []
    for agent in sorted(available_agents, key=lambda a: a["name"]):
        hint = _SPECIAL_HINTS.get(agent["name"], "")
        agent_lines.append(f"- **{agent['name']}**: {agent['description']}{hint}")

    agent_list = "\n".join(agent_lines)

    return f"""
## Agent Delegation

You have specialized agents available:
{agent_list}

### Delegation Protocol

**CRITICAL: If the user's request clearly maps to an agent's specialty,
delegate on your FIRST turn. Do NOT spend turns researching, reading notes,
or calling vault tools before delegating.**

When delegating, call `delegate_to_agent` as your ONLY tool call.
Do not call any other tool in the same turn.

**WRONG** (never do this):
1. User asks to prepare an article for publishing
2. You call search_notes or read_note to find it first
3. Then call delegate_to_agent

**RIGHT** (always do this):
1. User asks to prepare an article for publishing
2. You call delegate_to_agent immediately with the article title in the task

The specialist agent has its own vault access tools and will read whatever
it needs. Your job is to delegate with a clear task description, not to
pre-fetch content.

Only use your own vault tools when the request does NOT match any agent's
specialty, or when you need to answer a question yourself.

When delegating, include a `context` parameter summarizing any relevant
background from YOUR conversation with the user — key details, preferences,
and constraints mentioned before this delegation.
"""


class JarvisAgent(BaseAgent):
    """
    Main JARVIS agent - the orchestrator.

    This agent:
    - Handles direct user conversations
    - Incorporates personal context
    - Can delegate to specialized agents
    - Tracks conversation history
    """

    def __init__(
        self,
        llm_client: LLMClient,
        context_dir: Path,
        model: str = "anthropic/claude-sonnet-4",
        extra_tools: list[ToolDefinition] | None = None,
        available_agents: list[dict] | None = None,
    ):
        """
        Initialize JARVIS.

        Args:
            llm_client: LLM client for API calls
            context_dir: Path to context files
            model: Model to use
            extra_tools: Additional tools to register beyond the defaults
            available_agents: List of {"name": ..., "description": ...} for delegation
        """
        # Build system prompt from context (soul.md is loaded internally)
        system_prompt = build_system_prompt(context_dir)

        tools = []
        if extra_tools:
            tools.extend(extra_tools)

        # Set up delegation if agents are available
        self._delegation_state = DelegationState()
        if available_agents:
            delegate_tool = make_delegate_tool(available_agents, self._delegation_state)
            tools.append(delegate_tool)
            system_prompt += _build_delegation_directive(available_agents)

        config = AgentConfig(
            name="JARVIS",
            description="Personal AI assistant with context awareness",
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            max_iterations=15,
        )

        super().__init__(config, llm_client)
        self.context_dir = context_dir

    def run(
        self,
        message: str,
        stream_handler: StreamHandler,
        print_chunks: bool = False,
        messages_override: list[dict] | None = None,
    ) -> StreamResult:
        """Run JARVIS, then check for delegation."""
        # Reset delegation state before each run
        self._delegation_state.agent_name = None
        self._delegation_state.task = None
        self._delegation_state.context = None

        result = super().run(message, stream_handler, print_chunks, messages_override)

        # Propagate delegation info to the result
        if self._delegation_state.agent_name:
            result.delegate_to = self._delegation_state.agent_name
            result.delegate_task = self._delegation_state.task
            result.delegate_context = self._delegation_state.context

        return result

    @classmethod
    def get_daily_note_instructions(cls) -> str:
        """Load the daily note entry prompt."""
        return cls.load_prompt("daily_note_entry")

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        """
        Process a user message and return a streaming response.

        Args:
            message: User's message
            context: Optional additional context

        Returns:
            StreamingResponse yielding response chunks
        """
        # Add user message to history
        self.add_to_history("user", message)

        # Build messages for API
        messages = self.get_messages_for_api()

        # Get streaming response
        return self.llm_client.chat_stream(messages)

    def refresh_context(self):
        """Reload context files and rebuild system prompt."""
        self.config.system_prompt = build_system_prompt(self.context_dir)
