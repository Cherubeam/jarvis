"""
Base agent class for JARVIS.

All agents should inherit from BaseAgent and implement the required methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.stream_handler import StreamHandler, StreamResult


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    model: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.7


class BaseAgent(ABC):
    """
    Base class for JARVIS agents.

    Agents are specialized assistants that can be orchestrated by JARVIS.
    Each agent has its own system prompt, tools, and capabilities.

    Subclasses must implement:
    - process_message: Handle a user message and return a response
    """

    def __init__(self, config: AgentConfig, llm_client: LLMClient):
        self.config = config
        self.llm_client = llm_client
        self.conversation_history: list[dict] = []

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.config.name

    @property
    def description(self) -> str:
        """Get agent description."""
        return self.config.description

    @classmethod
    def load_prompt(cls, name: str) -> str:
        """Load a prompt file from the agent's prompts/ directory.

        Looks for ``prompts/<name>.md`` relative to the file that defines
        the concrete agent subclass.

        Args:
            name: Prompt file name without extension.

        Returns:
            Prompt text content.

        Raises:
            FileNotFoundError: If prompt file does not exist.
        """
        import inspect
        # Walk the MRO to find the first concrete subclass file
        agent_file = inspect.getfile(cls)
        prompts_dir = Path(agent_file).parent / "prompts"
        path = prompts_dir / f"{name}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    @abstractmethod
    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        """
        Process a user message and return a streaming response.

        Args:
            message: User's message
            context: Optional context dict

        Returns:
            StreamingResponse yielding response chunks
        """
        pass

    def run(
        self,
        message: str,
        stream_handler: StreamHandler,
        print_chunks: bool = False,
        messages_override: list[dict] | None = None,
    ) -> StreamResult:
        """Run the agent on a user message, streaming the response.

        This is the primary entry point for the CLI. It builds the
        message list, calls stream_handler.stream(), and returns a
        StreamResult.

        Args:
            message: The user's input text.
            stream_handler: StreamHandler for streaming + metrics.
            print_chunks: Print response chunks to stdout.
            messages_override: If provided, use these as conversation
                history instead of the agent's internal history.
                The agent will append the user message to this list
                before building the API payload.

        Returns:
            StreamResult with the full response text, usage, and cost.
        """
        if messages_override is not None:
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                *messages_override,
                {"role": "user", "content": message},
            ]
        else:
            self.add_to_history("user", message)
            messages = self.get_messages_for_api()

        return stream_handler.stream(messages, print_chunks=print_chunks)

    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content
        })

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []

    def get_messages_for_api(self) -> list[dict]:
        """Get messages formatted for API call."""
        return [
            {"role": "system", "content": self.config.system_prompt},
            *self.conversation_history
        ]

    def to_dict(self) -> dict:
        """Serialize agent to dictionary."""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "model": self.config.model,
            "tools": self.config.tools,
        }
