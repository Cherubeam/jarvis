"""
Tactics agent — cross-deck Pip Decks coaching orchestrator.

Searches across all indexed deck-skill cards via RAG and provides
multi-turn coaching for storytelling, workshops, ideation, and more.
"""

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.tools.base import ToolDefinition


class TacticsAgent(BaseAgent):
    """Cross-deck Pip Decks coaching agent.

    Uses the ``search_tactics`` tool (injected via ``extra_tools``) to find
    relevant cards across all decks and coaches the user through applying them.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "anthropic/claude-sonnet-4",
        extra_tools: list[ToolDefinition] | None = None,
    ):
        system_prompt = self.load_prompt("system")

        tools: list[ToolDefinition] = []
        if extra_tools:
            tools.extend(extra_tools)

        config = AgentConfig(
            name="tactics",
            description="Pip Decks tactics coaching — storytelling, workshops, ideation",
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            temperature=0.7,
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        messages = self.get_messages_for_api()
        return self.llm_client.chat_stream(messages)
