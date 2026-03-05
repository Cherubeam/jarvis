"""
JARVIS - Main orchestrator agent.

This is the primary agent that coordinates other agents and handles
direct user interactions. It can delegate tasks to specialized agents.
"""

from pathlib import Path

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.context_builder import build_system_prompt
from packages.core.tools.base import ToolDefinition
from packages.core.tools.web_fetch import FETCH_URL_TOOL


class JarvisAgent(BaseAgent):
    """
    Main JARVIS agent - the orchestrator.

    This agent:
    - Handles direct user conversations
    - Incorporates personal context
    - Can delegate to specialized agents (future)
    - Tracks conversation history
    """

    def __init__(
        self,
        llm_client: LLMClient,
        context_dir: Path,
        model: str = "anthropic/claude-sonnet-4",
        extra_tools: list[ToolDefinition] | None = None,
    ):
        """
        Initialize JARVIS.

        Args:
            llm_client: LLM client for API calls
            context_dir: Path to context files
            model: Model to use
            extra_tools: Additional tools to register beyond the defaults
        """
        # Build system prompt from context (soul.md is loaded internally)
        system_prompt = build_system_prompt(context_dir)

        tools = [FETCH_URL_TOOL]
        if extra_tools:
            tools.extend(extra_tools)

        config = AgentConfig(
            name="JARVIS",
            description="Personal AI assistant with context awareness",
            model=model,
            system_prompt=system_prompt,
            tools=tools,
        )

        super().__init__(config, llm_client)
        self.context_dir = context_dir

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
