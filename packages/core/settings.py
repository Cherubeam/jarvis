"""Typed configuration for JARVIS.

Replaces dict-based ``load_config`` with a ``pydantic-settings`` model.
Loaded from ``config/default.yaml`` deep-merged with ``config/local.yaml``.
See ADR-032 in ``docs/product/decisions.md``.
"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``.

    Semantics (unchanged from ``apps.cli.main._deep_merge``):
    - Nested dicts merge key-by-key.
    - Lists replace wholesale (not concatenated) — matches user expectation
      for keys like ``mcp.servers`` or ``developer.scope``.
    - Any non-dict override replaces the base value at that key.

    Returns a new dict; inputs are not mutated.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def read_yaml_layers(default_path: Path, local_path: Path | None = None) -> dict[str, Any]:
    """Read ``default.yaml`` and optionally deep-merge ``local.yaml`` on top.

    Missing files are treated as empty dicts. Returns the merged dict the
    ``Settings`` model will consume. Keeps filesystem I/O isolated from
    model construction so callers can supply their own dicts in tests.
    """
    if default_path.exists():
        with default_path.open() as f:
            merged = yaml.safe_load(f) or {}
    else:
        merged = {}

    if local_path and local_path.exists():
        with local_path.open() as f:
            local = yaml.safe_load(f) or {}
        merged = deep_merge(merged, local)

    return merged


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


class Things3Settings(BaseModel):
    """Things 3 task integration."""

    enabled: bool = Field(default=True, description="Sync Things 3 tasks into JARVIS context.")
    sync_on_startup: bool = Field(
        default=True,
        description="Refresh tasks each time the CLI starts (otherwise only on demand).",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="How long cached task data remains valid before re-sync.",
    )
    lists_to_include: list[str] = Field(
        default_factory=lambda: ["Today", "Upcoming", "Inbox"],
        description="Things 3 list names to pull into context.",
    )
    max_tasks_per_list: int = Field(
        default=50,
        description="Cap per list to keep context windows from bloating.",
    )


class EvaluationSettings(BaseModel):
    """LLM-as-judge evaluation settings."""

    judge_model: str = Field(
        default="anthropic/claude-opus-4.6",
        description="LiteLLM-routable model id used for grading golden conversations.",
    )
    quality_threshold: float = Field(
        default=0.70,
        description="Minimum mean score (0-1) below which a run fails.",
    )
    category_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "reasoning": 0.75,
            "context_recall": 0.70,
            "personalization": 0.70,
            "edge_cases": 0.65,
        },
        description="Per-category overrides for quality_threshold.",
    )
    results_dir: str = Field(
        default="tests/golden/results",
        description="Directory where evaluation runs persist their results.",
    )
    max_cost_per_run: float = Field(
        default=1.00,
        description="USD ceiling above which an evaluation run aborts mid-flight.",
    )
    warn_cost_threshold: float = Field(
        default=0.50,
        description="USD threshold that triggers a warning but continues the run.",
    )


class RagSettings(BaseModel):
    """RAG layer — conversation recall via ChromaDB + LiteLLM embeddings."""

    enabled: bool = Field(
        default=True,
        description="Enable retrieval over past conversations and indexed cards.",
    )
    db_path: str = Field(
        default="data/rag/chroma",
        description="Filesystem path for the ChromaDB persistent store.",
    )
    embedding_model: str = Field(
        default="openrouter/openai/text-embedding-3-small",
        description="LiteLLM-routable embedding model id used for indexing and queries.",
    )
    index_cards: bool = Field(
        default=True,
        description="Index deck-skill cards alongside conversations when RAG is enabled.",
    )


class RoutingSettings(BaseModel):
    """Intelligent model routing — route by query complexity."""

    enabled: bool = Field(
        default=False,
        description="Route simple queries to fast models and complex ones to quality models.",
    )
    simple_threshold: int = Field(
        default=200,
        description="Character count below which a query is classified as simple.",
    )
    complex_threshold: int = Field(
        default=800,
        description="Character count above which a query is classified as complex.",
    )


class SummarizationSettings(BaseModel):
    """History summarization — compress old turns to limit token use."""

    enabled: bool = Field(
        default=False,
        description="Compress old conversation history once a token threshold is exceeded.",
    )
    token_threshold: int = Field(
        default=40000,
        description="Approximate token count that triggers summarization.",
    )
    keep_recent: int = Field(
        default=10,
        description="Number of recent messages preserved verbatim after summarization.",
    )


class ObsidianDailyNotesSettings(BaseModel):
    """Daily-notes path conventions inside the vault."""

    path_format: str = Field(
        default="Daily Notes/%Y-%m-%d",
        description="strftime template (relative to vault_path) used for daily notes.",
    )


class ObsidianWritingTargetSettings(BaseModel):
    """Per-writing-mode target directory + template within the vault."""

    target_dir: str = Field(
        default="",
        description="Vault-relative directory where this writing mode saves new notes.",
    )
    template_path: str = Field(
        default="",
        description="Vault-relative path to the markdown template seeded into new notes.",
    )


class ObsidianWritingSettings(BaseModel):
    """Writing-mode targets for blog, patterns, and slip-box."""

    blog_dir: str = Field(
        default="",
        description="Vault-relative directory where blog drafts are written.",
    )
    template_path: str = Field(
        default="",
        description="Vault-relative path to the blog post template.",
    )
    patterns: ObsidianWritingTargetSettings = Field(
        default_factory=ObsidianWritingTargetSettings,
        description="Pattern-card writing target inside the vault.",
    )
    slip_box: ObsidianWritingTargetSettings = Field(
        default_factory=ObsidianWritingTargetSettings,
        description="Permanent-note (slip-box) writing target inside the vault.",
    )


class ObsidianSettings(BaseModel):
    """Obsidian vault integration."""

    enabled: bool = Field(default=False, description="Enable Obsidian vault read/write tools.")
    vault_path: str = Field(
        default="",
        description="Absolute filesystem path to the user's Obsidian vault.",
    )
    daily_notes: ObsidianDailyNotesSettings = Field(
        default_factory=ObsidianDailyNotesSettings,
        description="Daily-notes path conventions.",
    )
    writing: ObsidianWritingSettings = Field(
        default_factory=ObsidianWritingSettings,
        description="Per-mode writing targets within the vault.",
    )
    prompts_dir: str = Field(
        default="data/prompts/obsidian",
        description="Project-relative directory storing per-vault editable prompt overrides.",
    )


class MCPServerSettings(BaseModel):
    """One MCP (Model Context Protocol) server entry.

    Mirrors the validation that ``packages.integrations.mcp.config.MCPServerConfig``
    used to perform: transport must be a known value, stdio requires a
    ``command``, sse/streamable_http require a ``url``. Server names must
    not contain ``__`` because that's the namespace separator inside tool
    names exposed to agents.
    """

    transport: Literal["stdio", "sse", "streamable_http"] = Field(
        description="Wire protocol used to talk to this server.",
    )
    tool_group: str = Field(
        default="",
        description=("Tool group name agents reference in meta.yaml. Defaults to the server name when empty."),
    )
    timeout_seconds: float = Field(
        default=30.0,
        description="Per-request timeout for this server.",
    )
    command: str | None = Field(
        default=None,
        description="Executable for stdio transport (required when transport=stdio).",
    )
    args: list[str] = Field(
        default_factory=list,
        description="Command-line arguments passed to the stdio command.",
    )
    env: dict[str, str] | None = Field(
        default=None,
        description="Environment variables injected into the stdio process.",
    )
    cwd: str | None = Field(
        default=None,
        description="Working directory for the stdio process.",
    )
    url: str | None = Field(
        default=None,
        description="HTTP endpoint for sse / streamable_http transports.",
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description="HTTP headers sent on every request to sse / streamable_http servers.",
    )

    @model_validator(mode="after")
    def _validate_transport_fields(self) -> "MCPServerSettings":
        if self.transport == "stdio" and not self.command:
            raise ValueError("stdio transport requires 'command'.")
        if self.transport in ("sse", "streamable_http") and not self.url:
            raise ValueError(f"{self.transport} transport requires 'url'.")
        return self


class MCPSettings(BaseModel):
    """MCP integration — connect to external MCP tool servers."""

    enabled: bool = Field(
        default=False,
        description="Master switch for the MCP subsystem.",
    )
    servers: dict[str, MCPServerSettings] = Field(
        default_factory=dict,
        description="Server name -> server config. Names must not contain '__'.",
    )

    @model_validator(mode="after")
    def _validate_server_names(self) -> "MCPSettings":
        for name in self.servers:
            if "__" in name:
                raise ValueError(
                    f"MCP server name '{name}' must not contain '__' (reserved as namespace separator in tool names)."
                )
        return self


class AccessRuleSettings(BaseModel):
    """One filesystem access rule.

    Pure-YAML half of ``packages.core.filesystem_access.AccessRule``.
    The ``FilesystemGuard`` runtime wrapper consumes a list of these and
    enforces most-specific-path-wins resolution at call time. Path
    expansion / resolution stays in the runtime wrapper to keep this
    schema portable.
    """

    path: str = Field(
        description="Filesystem path (~ allowed) the rule applies to.",
    )
    access: Literal["deny", "read", "write", "read-write"] = Field(
        description="Permission level granted to subpaths of 'path'.",
    )


class FilesystemSettings(BaseModel):
    """Per-path filesystem access rules consumed by FilesystemGuard."""

    access_rules: list[AccessRuleSettings] = Field(
        default_factory=list,
        description=("List of path/access rules. Most-specific path wins; missing paths default to deny."),
    )


class CortexSettings(BaseModel):
    """Cortex — shared semantic vault search service."""

    enabled: bool = Field(
        default=False,
        description="Route semantic vault searches to a running Cortex service.",
    )
    base_url: str = Field(
        default="http://127.0.0.1:8100",
        description="HTTP endpoint where the Cortex service is listening.",
    )
    timeout_seconds: int = Field(
        default=10,
        description="Per-request timeout when calling the Cortex service.",
    )


class ReadwiseSettings(BaseModel):
    """Readwise integration — reading list, highlights, and persona."""

    enabled: bool = Field(default=False, description="Enable Readwise tools and persona ingestion.")
    cache_ttl_seconds: int = Field(
        default=300,
        description="How long Readwise CLI tool results stay cached.",
    )


class PatternCardImageGenerationSettings(BaseModel):
    """API-based image generation settings for the pattern card generator.

    Mirrors ``packages.core.card_renderer.ImageGenerationConfig``. The
    runtime dataclass will be removed in a later commit once the renderer
    consumes this typed model directly.
    """

    enabled: bool = Field(
        default=False,
        description="Generate pattern card images via the LiteLLM image API instead of placeholders.",
    )
    model: str = Field(
        default="gemini/imagen-4.0-generate-001",
        description="LiteLLM-routable image model id.",
    )
    size: str = Field(
        default="1536x640",
        description="Output image dimensions as 'WIDTHxHEIGHT'.",
    )
    max_images_per_run: int = Field(
        default=10,
        description="Cap on images generated per invocation to bound cost.",
    )


class PatternCardsSettings(BaseModel):
    """Pattern card generator output + image-generation knobs."""

    output_dir: str = Field(
        default="data/pattern-cards",
        description="Directory where rendered pattern cards are written.",
    )
    image_generation: PatternCardImageGenerationSettings = Field(
        default_factory=PatternCardImageGenerationSettings,
        description="API image-generation knobs for pattern cards.",
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
    things3: Things3Settings = Field(default_factory=Things3Settings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    rag: RagSettings = Field(default_factory=RagSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    summarization: SummarizationSettings = Field(default_factory=SummarizationSettings)
    obsidian: ObsidianSettings = Field(default_factory=ObsidianSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    filesystem: FilesystemSettings = Field(default_factory=FilesystemSettings)
    cortex: CortexSettings = Field(default_factory=CortexSettings)
    readwise: ReadwiseSettings = Field(default_factory=ReadwiseSettings)
    pattern_cards: PatternCardsSettings = Field(default_factory=PatternCardsSettings)
    developer: DeveloperSettings = Field(default_factory=DeveloperSettings)

    jarvis_dir: Path = Field(
        default_factory=Path.cwd,
        exclude=True,
        description=("Project root directory. Runtime-injected by load_typed_config; never loaded from YAML."),
    )


def get_project_root() -> Path:
    """Project root inferred from this module's location."""
    return Path(__file__).resolve().parent.parent.parent


def load_typed_config(project_root: Path | None = None) -> Settings:
    """Load default.yaml + local.yaml from ``<project_root>/config/`` into Settings.

    The runtime-only ``jarvis_dir`` field is injected after construction so the
    pydantic schema stays purely YAML-shaped.
    """
    root = project_root if project_root is not None else get_project_root()
    config_dir = root / "config"
    merged = read_yaml_layers(config_dir / "default.yaml", config_dir / "local.yaml")
    settings = Settings.model_validate(merged)
    settings.jarvis_dir = root
    return settings
