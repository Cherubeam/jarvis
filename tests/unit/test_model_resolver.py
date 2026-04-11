"""
Unit tests for model_resolver module.

Tests preset resolution, literal model IDs, provider inference, and API key collection.
"""

import os
import pytest
from unittest.mock import patch

from packages.core.model_resolver import (
    ResolvedModel,
    infer_provider,
    resolve_model,
    collect_api_keys,
    get_api_key,
)


@pytest.mark.unit
class TestInferProvider:
    """Tests for infer_provider()."""

    def test_openrouter_prefix(self):
        assert infer_provider("openrouter/anthropic/claude-sonnet-4.6") == "openrouter"

    def test_anthropic_prefix(self):
        assert infer_provider("anthropic/claude-sonnet-4.6") == "anthropic"

    def test_openai_prefix(self):
        assert infer_provider("openai/gpt-4o") == "openai"

    def test_google_prefix(self):
        assert infer_provider("google/gemini-2.5-flash") == "google"

    def test_bare_model_defaults_to_openai(self):
        """Bare model names (no prefix) default to openai per LiteLLM convention."""
        assert infer_provider("gpt-4o") == "openai"

    def test_nested_prefix_takes_first_segment(self):
        assert infer_provider("openrouter/google/gemini-2.5-flash") == "openrouter"


@pytest.mark.unit
class TestResolveModel:
    """Tests for resolve_model()."""

    def test_preset_resolution(self):
        config = {
            "models": {
                "default": "openrouter/anthropic/claude-sonnet-4.6",
                "presets": {
                    "fast": "openrouter/google/gemini-2.5-flash",
                    "quality": "openrouter/anthropic/claude-opus-4.6",
                },
            }
        }
        result = resolve_model("fast", config)
        assert result.model_id == "openrouter/google/gemini-2.5-flash"
        assert result.provider == "openrouter"
        assert "gemini-2.5-flash" in result.display_name

    def test_literal_model_id_passthrough(self):
        config = {"models": {"presets": {}}}
        result = resolve_model("anthropic/claude-sonnet-4.6", config)
        assert result.model_id == "anthropic/claude-sonnet-4.6"
        assert result.provider == "anthropic"

    def test_unknown_preset_treated_as_literal(self):
        config = {"models": {"presets": {"fast": "some/model"}}}
        result = resolve_model("openai/gpt-4o", config)
        assert result.model_id == "openai/gpt-4o"
        assert result.provider == "openai"

    def test_empty_config(self):
        result = resolve_model("openrouter/anthropic/claude-sonnet-4.6", {})
        assert result.model_id == "openrouter/anthropic/claude-sonnet-4.6"
        assert result.provider == "openrouter"

    def test_display_name_format(self):
        result = resolve_model("openrouter/anthropic/claude-sonnet-4.6", {})
        assert result.display_name == "anthropic/claude-sonnet-4.6 via openrouter"

    def test_bare_model_display_name(self):
        result = resolve_model("gpt-4o", {})
        assert result.display_name == "gpt-4o via openai"


@pytest.mark.unit
class TestCollectApiKeys:
    """Tests for collect_api_keys()."""

    def test_collects_set_keys(self):
        env = {
            "OPENROUTER_API_KEY": "sk-or-123",
            "ANTHROPIC_API_KEY": "sk-ant-456",
        }
        with patch.dict(os.environ, env, clear=False):
            keys = collect_api_keys()
        assert keys["openrouter"] == "sk-or-123"
        assert keys["anthropic"] == "sk-ant-456"

    def test_skips_unset_keys(self):
        env = {"OPENROUTER_API_KEY": "sk-or-123"}
        with patch.dict(os.environ, env, clear=False):
            # Remove other keys if present
            for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
                os.environ.pop(var, None)
            keys = collect_api_keys()
        assert "openrouter" in keys
        assert "anthropic" not in keys

    def test_empty_when_no_keys_set(self):
        api_vars = [
            "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY", "GOOGLE_API_KEY",
        ]
        with patch.dict(os.environ, {}, clear=False):
            for var in api_vars:
                os.environ.pop(var, None)
            keys = collect_api_keys()
        assert keys == {}


@pytest.mark.unit
class TestGetApiKey:
    """Tests for get_api_key()."""

    def test_returns_key_when_present(self):
        keys = {"openrouter": "sk-123", "anthropic": "sk-456"}
        assert get_api_key("openrouter", keys) == "sk-123"

    def test_returns_none_when_missing(self):
        keys = {"openrouter": "sk-123"}
        assert get_api_key("anthropic", keys) is None
