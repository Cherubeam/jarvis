"""
Writing agent — write and edit in Marco's authentic voice.
"""

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.tools.base import ToolDefinition


class WritingAgent(BaseAgent):
    """Specialized agent for writing, editing, and rewriting text."""

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "anthropic/claude-sonnet-4",
        extra_tools: list[ToolDefinition] | None = None,
    ):
        system_template = self.load_prompt("system")
        voice_profile = self.load_prompt("voice-profile")
        anti_patterns = self.load_prompt("anti-patterns")
        system_prompt = system_template.replace(
            "{voice_profile}", voice_profile
        ).replace("{anti_patterns}", anti_patterns)
        config = AgentConfig(
            name="writing",
            description="Write and edit in Marco's authentic voice",
            model=model,
            system_prompt=system_prompt,
            tools=extra_tools or [],
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        messages = self.get_messages_for_api()
        return self.llm_client.chat_stream(messages)
