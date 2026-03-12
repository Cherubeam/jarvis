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
from packages.core.tools.web_fetch import FETCH_URL_TOOL

_DELEGATION_DIRECTIVE = """
## Agent Delegation
You can read vault notes directly with `read_note`, `search_notes`, and
`read_daily_note`. Delegate to specialized agents for creative tasks:
- **writing**: creative writing, editing, content evaluation, blog posts
- **tactics**: tactics search, combining tactics into workflows or ideas
- **obsidian-note-creator**: extract atomic evergreen notes from conversations or material

Use `delegate_to_agent` when a task is better handled by a specialist.
When delegating, call `delegate_to_agent` immediately — do NOT use other
tools (like recall or fetch) first. The specialized agent has its own tools.

When delegating, include a `context` parameter summarizing any relevant
background from YOUR conversation with the user — key details, preferences,
and constraints mentioned before this delegation. The full conversation
history from any prior agent session is passed separately and automatically.
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

        tools = [FETCH_URL_TOOL]
        if extra_tools:
            tools.extend(extra_tools)

        # Set up delegation if agents are available
        self._delegation_state = DelegationState()
        if available_agents:
            delegate_tool = make_delegate_tool(available_agents, self._delegation_state)
            tools.append(delegate_tool)
            system_prompt += _DELEGATION_DIRECTIVE

        config = AgentConfig(
            name="JARVIS",
            description="Personal AI assistant with context awareness",
            model=model,
            system_prompt=system_prompt,
            tools=tools,
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
