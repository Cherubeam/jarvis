"""
Model resolution: presets, provider inference, and API key management.

Translates user-facing model names (presets like "fast" or literal IDs like
"openrouter/anthropic/claude-sonnet-4.6") into LiteLLM-routable model strings.
"""

import os
from dataclasses import dataclass
from typing import Any

from packages.core.settings import ModelsSettings

# OpenRouter's Auto Router in LiteLLM format; "auto" resolves to it (see models.auto_router)
AUTO_MODEL_ID = "openrouter/openrouter/auto"


def session_extra_body(models: ModelsSettings, session_id: str) -> dict[str, dict[str, Any]]:
    """Per-model request fields for a session: models.extra_body plus the Auto Router block.

    Returns a new dict; ``models.extra_body`` is never modified (the GUI saves settings back).
    The auto block is present whether or not auto_router.enabled, so ``/model auto`` works too.
    """
    auto = models.auto_router
    plugin: dict[str, Any] = {"id": "auto-router", "cost_tier": auto.cost_tier}
    if auto.excluded_models:
        plugin["excluded_models"] = list(auto.excluded_models)
    auto_body = {"plugins": [plugin], "session_id": session_id}
    return {**models.extra_body, AUTO_MODEL_ID: {**models.extra_body.get(AUTO_MODEL_ID, {}), **auto_body}}


@dataclass
class ResolvedModel:
    """A fully resolved model ready for LiteLLM routing."""

    model_id: str  # LiteLLM-routable ID (e.g. "openrouter/anthropic/claude-sonnet-4.6")
    provider: str  # "openrouter", "anthropic", "openai", etc.
    display_name: str  # For UI (e.g. "claude-sonnet-4.6 via openrouter")


# Known providers and their env var names
_PROVIDER_API_KEY_VARS: dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def infer_provider(model_id: str) -> str:
    """Extract the provider from a LiteLLM model ID.

    LiteLLM convention: the first path segment is the provider prefix.
    E.g. "openrouter/anthropic/claude-sonnet-4.6" -> "openrouter"
         "anthropic/claude-sonnet-4.6"            -> "anthropic"
         "gpt-4o"                                 -> "openai"  (no prefix = OpenAI)
    """
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    # No prefix — LiteLLM treats bare model names as OpenAI
    return "openai"


def resolve_model(name_or_preset: str, models: ModelsSettings) -> ResolvedModel:
    """Resolve a preset name or literal model ID into a ResolvedModel.

    Checks presets first, then treats input as a literal LiteLLM model ID.
    """
    presets = models.presets.model_dump()

    # Check if it's a preset name
    model_id = AUTO_MODEL_ID if name_or_preset == "auto" else presets.get(name_or_preset, name_or_preset)

    provider = infer_provider(model_id)

    # Build a human-readable display name
    # Strip provider prefix for display, keep the rest
    if "/" in model_id:
        short_name = model_id.split("/", 1)[1]
    else:
        short_name = model_id
    display_name = f"{short_name} via {provider}"

    return ResolvedModel(
        model_id=model_id,
        provider=provider,
        display_name=display_name,
    )


def collect_api_keys() -> dict[str, str]:
    """Scan environment variables for known provider API keys.

    Returns a dict mapping provider name -> API key (only for keys that exist).
    """
    keys: dict[str, str] = {}
    for provider, env_var in _PROVIDER_API_KEY_VARS.items():
        value = os.getenv(env_var)
        if value:
            keys[provider] = value
    return keys


def get_api_key(provider: str, api_keys: dict[str, str]) -> str | None:
    """Get the API key for a given provider."""
    return api_keys.get(provider)
