"""
Tool interface and registry for JARVIS function calling.
"""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ToolDefinition:
    """Defines a callable tool that can be invoked by the LLM."""

    name: str
    description: str
    parameters: dict  # JSON Schema for the tool's arguments
    execute: Callable[..., str]
    terminal: bool = False  # If True, skip streaming after this tool fires

    def to_litellm_format(self) -> dict:
        """Convert to LiteLLM/OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool by name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool by name. Returns None if not found."""
        return self._tools.get(name)

    def to_litellm_format(self) -> list[dict]:
        """Return all tools in LiteLLM/OpenAI format."""
        return [t.to_litellm_format() for t in self._tools.values()]

    def is_empty(self) -> bool:
        """Return True if no tools are registered."""
        return len(self._tools) == 0
