"""
Developer agent — JARVIS's self-improvement agent.

Python-class agent because it needs custom run() to pass max_iterations=20
for extended agentic loops when making multi-step code changes.
"""

from packages.agents.base import BaseAgent, AgentConfig
from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.tools.base import ToolDefinition


class DeveloperAgent(BaseAgent):
    """Developer agent for JARVIS self-improvement.

    Extends BaseAgent with a higher max_iterations limit (20 vs default 5)
    to support multi-step workflows: read → branch → write → test → commit.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "openrouter/anthropic/claude-sonnet-4.6",
        extra_tools: list[ToolDefinition] | None = None,
    ):
        system_prompt = self.load_prompt("system")

        tools: list[ToolDefinition] = []
        if extra_tools:
            tools.extend(extra_tools)

        config = AgentConfig(
            name="developer",
            description="JARVIS self-improvement agent",
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            temperature=0.3,  # Lower temperature for precise code work
            max_tokens=4096,
        )
        super().__init__(config, llm_client)

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        messages = self.get_messages_for_api()
        return self.llm_client.chat_stream(messages)

    def run(
        self,
        message: str,
        stream_handler: StreamHandler,
        print_chunks: bool = False,
        messages_override: list[dict] | None = None,
    ) -> StreamResult:
        """Run with extended iteration limit for multi-step development workflows."""
        if messages_override is not None:
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                *messages_override,
                {"role": "user", "content": message},
            ]
        else:
            self.add_to_history("user", message)
            messages = self.get_messages_for_api()

        registry = self.tool_registry if not self.tool_registry.is_empty() else None
        return stream_handler.stream(
            messages, print_chunks=print_chunks,
            tool_registry=registry, max_iterations=20,
        )
