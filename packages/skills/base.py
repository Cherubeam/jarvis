"""
Base skill class for JARVIS.

Skills are vendor-portable task specifications driven by SKILL.md files.
They operate in two modes:

- **SKILL.md only**: The markdown body becomes the system prompt, run through
  StreamHandler. No Python code needed.
- **SKILL.md + skill.py**: Custom execution logic via a SkillExecutor subclass.

The SKILL.md format matches Claude's native specification: YAML frontmatter
with ``name`` and ``description``, plus a markdown body that serves as both
the capability spec and the prompt.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path

from packages.core.context_builder import parse_frontmatter
from packages.core.llm_client import LLMClient
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.core.tools.base import ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class SkillConfig:
    """Configuration for a skill, parsed from SKILL.md + optional skill.py."""

    name: str
    description: str
    system_prompt: str
    command: str
    path: Path
    tools: list[ToolDefinition] = field(default_factory=list)
    model: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7


class BaseSkill:
    """
    Base class for JARVIS skills.

    Skills are task-specific workflows driven by a portable SKILL.md spec.
    Simple skills need only a SKILL.md file. Skills requiring custom execution
    logic can provide a ``skill.py`` with a ``SkillExecutor`` subclass.
    """

    def __init__(self, config: SkillConfig, llm_client: LLMClient):
        self.config = config
        self.llm_client = llm_client

        self.tool_registry = ToolRegistry()
        for tool in config.tools:
            self.tool_registry.register(tool)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def description(self) -> str:
        return self.config.description

    @property
    def command(self) -> str:
        return self.config.command

    def run(
        self,
        message: str,
        stream_handler: StreamHandler,
        print_chunks: bool = False,
        messages_override: list[dict] | None = None,
    ) -> StreamResult:
        """Run the skill on user input, streaming the response.

        Args:
            message: The user's input text.
            stream_handler: StreamHandler for streaming + metrics.
            print_chunks: Print response chunks to stdout.
            messages_override: If provided, use as conversation history.

        Returns:
            StreamResult with the full response text, usage, and cost.
        """
        messages = [
            {"role": "system", "content": self.config.system_prompt},
        ]
        if messages_override:
            messages.extend(messages_override)
        messages.append({"role": "user", "content": message})

        registry = self.tool_registry if not self.tool_registry.is_empty() else None
        return stream_handler.stream(
            messages, print_chunks=print_chunks, tool_registry=registry
        )

    @classmethod
    def from_skill_md(
        cls,
        skill_dir: Path,
        llm_client: LLMClient,
        model: str | None = None,
    ) -> BaseSkill:
        """Factory: build a skill from a SKILL.md file.

        If the skill directory also contains a ``skill.py`` with a
        ``SKILL_CONFIG`` dict, those settings (tools, model, command override,
        temperature, max_tokens) are merged into the config.

        Args:
            skill_dir: Directory containing SKILL.md (and optional skill.py).
            llm_client: LLM client for API calls.
            model: Override model (takes precedence over skill.py config).

        Returns:
            A BaseSkill instance ready to run.
        """
        skill_md_path = skill_dir / "SKILL.md"
        raw = skill_md_path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(raw)

        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "")
        command = f"/{name}"

        tools: list[ToolDefinition] = []
        skill_model = None
        max_tokens = 4096
        temperature = 0.7

        # Check for optional skill.py with SKILL_CONFIG
        skill_py = skill_dir / "skill.py"
        if skill_py.is_file():
            try:
                spec_module = _import_skill_module(skill_dir)
                skill_config_dict = getattr(spec_module, "SKILL_CONFIG", {})

                if "command" in skill_config_dict:
                    command = skill_config_dict["command"]
                if "tools" in skill_config_dict:
                    tools = skill_config_dict["tools"]
                if "model" in skill_config_dict:
                    skill_model = skill_config_dict["model"]
                if "max_tokens" in skill_config_dict:
                    max_tokens = skill_config_dict["max_tokens"]
                if "temperature" in skill_config_dict:
                    temperature = skill_config_dict["temperature"]
            except Exception:
                logger.warning(
                    "Failed to load skill.py for %s", name, exc_info=True
                )

        config = SkillConfig(
            name=name,
            description=description,
            system_prompt=body.strip(),
            command=command,
            path=skill_dir,
            tools=tools,
            model=model or skill_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return cls(config, llm_client)


def _import_skill_module(skill_dir: Path):
    """Import a skill's skill.py module by path.

    Uses absolute() instead of resolve() so symlinked skill directories
    keep their logical path within the packages/ tree. The actual file is
    loaded via spec_from_file_location so Python finds the real module on
    disk regardless of symlink indirection.
    """
    # absolute() preserves symlinks; resolve() follows them
    parts = skill_dir.absolute().parts
    try:
        pkg_idx = parts.index("packages")
    except ValueError:
        raise ImportError(f"Cannot determine module path for {skill_dir}")

    module_name = ".".join(parts[pkg_idx:]) + ".skill"
    skill_py = skill_dir / "skill.py"
    spec = importlib.util.spec_from_file_location(module_name, skill_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {skill_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
