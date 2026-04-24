"""Typed configuration for JARVIS.

Replaces dict-based ``load_config`` with a ``pydantic-settings`` model.
Loaded from ``config/default.yaml`` deep-merged with ``config/local.yaml``.
See ADR-032 in ``docs/product/decisions.md``.
"""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ModelPresets(BaseModel):
    """Named model aliases used across agents."""

    fast: str = Field(
        default="openrouter/google/gemini-2.5-flash",
        description="Cheap, low-latency model for simple turns.",
    )
    quality: str = Field(
        default="openrouter/anthropic/claude-opus-4.6",
        description="Highest-capability model for complex reasoning.",
    )
    balanced: str = Field(
        default="openrouter/qwen/qwen3.5-flash-02-23",
        description="Mid-tier model balancing cost and quality.",
    )


class ModelsSettings(BaseModel):
    """LLM model defaults and named presets."""

    default: str = Field(
        default="openrouter/qwen/qwen3.5-flash-02-23",
        description="LiteLLM-routable model id used when no preset is requested.",
    )
    default_max_tokens: int = Field(
        default=16384,
        description="Maximum response tokens when an agent does not override.",
    )
    streaming: bool = Field(
        default=True,
        description="Stream model output token-by-token. Disable for OpenRouter prompt caching.",
    )
    presets: ModelPresets = Field(
        default_factory=ModelPresets,
        description="Named model aliases consumed by agents and the model router.",
    )


class PathsSettings(BaseModel):
    """Project-relative data paths."""

    context_dir: str = Field(
        default="data/context",
        description="Directory holding user/personal context markdown files.",
    )
    conversations_dir: str = Field(
        default="data/conversations",
        description="Root directory for persisted conversation logs (organized by year).",
    )
    learned_facts: str = Field(
        default="data/learned_facts.md",
        description="Markdown file capturing facts JARVIS has learned about the user.",
    )
    prompt_history_dir: str = Field(
        default="data/prompt-history",
        description="Directory for snapshots of edited agent prompts.",
    )


class CliSettings(BaseModel):
    """Interactive CLI display preferences."""

    colors: bool = Field(default=True, description="Enable Rich color output in the CLI.")
    history_file: str = Field(
        default="data/.cli_history",
        description="File where prompt-toolkit persists CLI input history.",
    )


class OutcomesSettings(BaseModel):
    """Outcome tracking — closed loop on advice JARVIS gives."""

    enabled: bool = Field(
        default=True,
        description="Auto-capture concrete recommendations and surface them in /outcomes.",
    )
    dir: str = Field(
        default="data/outcomes",
        description="Directory under which tracked outcomes are persisted as markdown.",
    )


class DeveloperSettings(BaseModel):
    """Developer agent — JARVIS self-improvement."""

    enabled: bool = Field(
        default=True,
        description="Expose the developer agent that can edit JARVIS's own configuration files.",
    )
    scope: list[str] = Field(
        default_factory=lambda: [
            "packages/agents/",
            "packages/skills/",
            "data/context/",
            "data/prompts/",
            "config/",
        ],
        description="Project-relative directories the developer agent is allowed to edit.",
    )
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".md", ".yaml", ".yml"],
        description="File extensions the developer agent is allowed to edit.",
    )


class Settings(BaseSettings):
    """Top-level JARVIS configuration model.

    Sections will be added incrementally during PR-8a. Once complete this
    model will replace the dict returned by ``apps.cli.main.load_config``.
    """

    models: ModelsSettings = Field(default_factory=ModelsSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    cli: CliSettings = Field(default_factory=CliSettings)
    outcomes: OutcomesSettings = Field(default_factory=OutcomesSettings)
    developer: DeveloperSettings = Field(default_factory=DeveloperSettings)
