"""
Base agent class for JARVIS.

All agents should inherit from BaseAgent and implement the required methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from packages.core.llm_client import LLMClient, StreamingResponse


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
        """
        Initialize the agent.

        Args:
            config: Agent configuration
            llm_client: LLM client for API calls
        """
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
