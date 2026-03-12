"""
Obsidian Note Creator agent — extract atomic evergreen notes from conversations or material.
"""

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse


class ObsidianNoteCreatorAgent(BaseAgent):
    """Specialized agent for extracting atomic evergreen notes into Obsidian-compatible Markdown."""

    def __init__(self, llm_client: LLMClient, model: str = "anthropic/claude-sonnet-4"):
        system_prompt = self.load_prompt("system")
        config = AgentConfig(
            name="obsidian-note-creator",
            description="Extract atomic evergreen notes from conversations or material",
            model=model,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        messages = self.get_messages_for_api()
        return self.llm_client.chat_stream(messages)
