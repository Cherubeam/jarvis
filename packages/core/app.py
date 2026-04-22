"""
Shared application bootstrap — extracted from apps/cli/main.py.

Provides config loading, component initialization, and agent setup
that can be reused by CLI, Web UI, and worker processes.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from packages.agents.base import agent_from_meta
from packages.agents.registry import AgentMeta, discover_agents
from packages.core.llm_client import LLMClient
from packages.core.model_resolver import collect_api_keys, resolve_model
from packages.core.pricing import ModelPricing, get_model_pricing
from packages.core.stream_handler import StreamHandler
from packages.skills.registry import discover_skills
from packages.telemetry.metrics import MetricsTracker


def get_project_root() -> Path:
    """Get the project root directory (two levels up from packages/core/)."""
    return Path(__file__).parent.parent.parent


def load_config(project_root: Path | None = None) -> dict:
    """Load configuration from YAML files and environment.

    Args:
        project_root: Project root directory. Auto-detected if None.

    Returns:
        Merged config dict with ``_paths.jarvis_dir`` set.
    """
    jarvis_dir = project_root or get_project_root()

    load_dotenv(jarvis_dir / ".env")

    default_config_path = jarvis_dir / "config" / "default.yaml"
    local_config_path = jarvis_dir / "config" / "local.yaml"

    if default_config_path.exists():
        with open(default_config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    if local_config_path.exists():
        with open(local_config_path) as f:
            local_config = yaml.safe_load(f) or {}
            config.update(local_config)

    config["_paths"] = {"jarvis_dir": jarvis_dir}
    return config


def init_llm_client(config: dict, model_override: str | None = None) -> tuple[LLMClient, str, ModelPricing | None]:
    """Initialize LLM client with model resolution and pricing.

    Args:
        config: Application config dict.
        model_override: CLI model flag or None for config default.

    Returns:
        Tuple of (LLMClient, resolved_model_id, pricing_or_None).
    """
    api_keys = collect_api_keys()
    models_config = config.get("models", {})
    model_source = model_override or models_config.get("default", "openrouter/anthropic/claude-sonnet-4.6")
    resolved = resolve_model(model_source, config)

    client = LLMClient(api_keys=api_keys, default_model=resolved.model_id)
    pricing = get_model_pricing(resolved.model_id)

    return client, resolved.model_id, pricing


def init_stream_handler(
    client: LLMClient,
    model_id: str,
    pricing: ModelPricing | None,
    config: dict,
    on_tool_call: Callable[[str], None] | None = None,
    on_event: Callable[..., None] | None = None,
    instance_id: str = "",
) -> tuple[StreamHandler, MetricsTracker]:
    """Create a StreamHandler and MetricsTracker pair.

    Returns:
        Tuple of (StreamHandler, MetricsTracker).
    """
    metrics_tracker = MetricsTracker()
    handler = StreamHandler(
        client,
        metrics_tracker,
        pricing,
        model_id,
        on_tool_call=on_tool_call,
        max_tokens=config.get("models", {}).get("default_max_tokens"),
        on_event=on_event,
        instance_id=instance_id,
    )
    return handler, metrics_tracker


def discover_all_agents_and_skills() -> tuple[dict[str, AgentMeta], dict]:
    """Discover all registered agents and skills.

    Returns:
        Tuple of (agent_registry, skill_registry).
    """
    return discover_agents(), discover_skills()


def instantiate_agent(
    meta: AgentMeta,
    client: LLMClient,
    model_id: str,
    extra_tools: list | None = None,
    skill_registry: dict | None = None,
    card_search_tool: Any = None,
) -> Any:
    """Create an agent from AgentMeta via agent_from_meta()."""
    if meta.meta_path is None:
        raise ValueError(f"AgentMeta {meta.name!r} has no meta_path; cannot instantiate")
    return agent_from_meta(
        meta.meta_path,
        client,
        model_id,
        extra_tools=extra_tools or None,
        skill_registry=skill_registry,
        card_search_tool=card_search_tool,
    )
