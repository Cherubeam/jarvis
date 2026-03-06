"""
Pattern Language Expert agent — design, evolve, and apply pattern languages.
"""

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse


class PatternLanguageExpertAgent(BaseAgent):
    """Specialized agent for designing and evolving pattern languages."""

    def __init__(self, llm_client: LLMClient, model: str = "anthropic/claude-sonnet-4"):
        system_prompt = self.load_prompt("system")
        config = AgentConfig(
            name="pattern-language-expert",
            description="Design, evolve, and apply pattern languages and pattern libraries",
            model=model,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        messages = self.get_messages_for_api()
        return self.llm_client.chat_stream(messages)
