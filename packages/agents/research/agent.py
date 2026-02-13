"""
Research agent — analysis, synthesis, and structured answers.
"""

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse


class ResearchAgent(BaseAgent):
    """Specialized agent for research, analysis, and synthesis."""

    def __init__(self, llm_client: LLMClient, model: str = "anthropic/claude-sonnet-4"):
        system_prompt = self.load_prompt("system")
        config = AgentConfig(
            name="research",
            description="Analysis, synthesis, and structured answers",
            model=model,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        messages = self.get_messages_for_api()
        return self.llm_client.chat_stream(messages)
