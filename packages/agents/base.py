"""
Base agent class for JARVIS.

All agents should inherit from BaseAgent and implement the required methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from packages.core.llm_client import LLMClient, StreamingResponse
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.tools.base import ToolDefinition, ToolRegistry
from packages.skills.registry import SkillMeta


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    model: str
    system_prompt: str
    tools: list[ToolDefinition] = field(default_factory=list)
    max_tokens: int | None = None
    temperature: float = 0.7
    max_iterations: int | None = None


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

        # Build tool registry from config
        self.tool_registry = ToolRegistry()
        for tool in config.tools:
            self.tool_registry.register(tool)

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

        registry = self.tool_registry if not self.tool_registry.is_empty() else None
        kwargs: dict = {}
        if self.config.max_iterations is not None:
            kwargs["max_iterations"] = self.config.max_iterations
        return stream_handler.stream(messages, print_chunks=print_chunks, tool_registry=registry, **kwargs)

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
            "tools": [t.name for t in self.config.tools],
        }


class DataDrivenAgent(BaseAgent):
    """Agent instantiated from meta.yaml — no custom Python class needed.

    Implements the standard process_message() that most agents share:
    add the user message to history and stream a response.
    """

    def process_message(self, message: str, context: dict | None = None) -> StreamingResponse:
        self.add_to_history("user", message)
        return self.llm_client.chat_stream(self.get_messages_for_api())

    def run(
        self,
        message: str,
        stream_handler: StreamHandler,
        print_chunks: bool = False,
        messages_override: list[dict] | None = None,
    ) -> StreamResult:
        """Run the agent, passing max_tokens when configured."""
        # Pass agent-configured max_tokens to the stream handler
        if self.config.max_tokens is not None:
            stream_handler.max_tokens = self.config.max_tokens

        return super().run(message, stream_handler, print_chunks, messages_override)


def agent_from_meta(
    meta_path: Path,
    llm_client: LLMClient,
    model: str,
    extra_tools: list[ToolDefinition] | None = None,
    skill_registry: dict | None = None,
    card_search_tool: ToolDefinition | None = None,
    skill_names_override: list[str] | None = None,
    prompt_includes_override: dict[str, str] | None = None,
) -> DataDrivenAgent:
    """Build an agent from a meta.yaml + prompts/system.md.

    Args:
        meta_path: Path to the agent's meta.yaml file.
        llm_client: LLM client for API calls.
        model: Model ID to use.
        extra_tools: Optional tools to register on the agent.
        skill_registry: Optional skill registry for resolving bound skills.
        card_search_tool: Optional card search tool for deck-skills.
        skill_names_override: If set, replaces meta.yaml's skills list.
        prompt_includes_override: Overrides specific placeholder values
            before normal expansion (e.g. {"x": ""} blanks {x} and skips
            its file; {"x": "custom"} replaces the filename for {x}).

    Returns:
        A fully configured DataDrivenAgent.
    """
    with open(meta_path, encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    agent_dir = meta_path.parent
    system_prompt_path = agent_dir / "prompts" / "system.md"
    system_prompt = system_prompt_path.read_text(encoding="utf-8")

    # Resolve prompt_includes: apply overrides before normal expansion
    prompt_includes = dict(meta.get("prompt_includes", {}))
    if prompt_includes_override:
        for placeholder, value in prompt_includes_override.items():
            if value == "":
                system_prompt = system_prompt.replace(f"{{{placeholder}}}", "")
                prompt_includes.pop(placeholder, None)
            else:
                prompt_includes[placeholder] = value

    shared_prompts_dir = Path(__file__).parent / "_shared" / "prompts"
    for placeholder, filename in prompt_includes.items():
        include_path = agent_dir / "prompts" / f"{filename}.md"
        if not include_path.is_file():
            include_path = shared_prompts_dir / f"{filename}.md"
        include_text = include_path.read_text(encoding="utf-8")
        system_prompt = system_prompt.replace(f"{{{placeholder}}}", include_text)

    tools = list(extra_tools) if extra_tools else []

    # Resolve bound skills if declared in meta.yaml
    skill_names = skill_names_override if skill_names_override is not None else meta.get("skills", [])
    if skill_names and skill_registry is not None:
        from packages.skills.resolver import resolve_skills

        resolved = resolve_skills(skill_names, skill_registry, card_search_tool)
        if resolved.prompt_appendix:
            if "{skills}" in system_prompt:
                system_prompt = system_prompt.replace("{skills}", resolved.prompt_appendix)
            else:
                system_prompt += "\n\n" + resolved.prompt_appendix
        tools.extend(resolved.tools)

    config = AgentConfig(
        name=meta["name"],
        description=meta.get("description", ""),
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        temperature=meta.get("temperature", 0.7),
        max_tokens=meta.get("max_tokens"),
        max_iterations=meta.get("max_iterations"),
    )
    return DataDrivenAgent(config, llm_client)
