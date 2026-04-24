"""Unit tests for ``packages.core.settings``.

Covers each section's model independently. End-to-end YAML-loading
parity is covered later in PR-8a (commit 8 wires the YAML source loader).
"""

import pytest
from pydantic import ValidationError

from packages.core.settings import (
    CliSettings,
    DeveloperSettings,
    ModelPresets,
    ModelsSettings,
    OutcomesSettings,
    PathsSettings,
    Settings,
)


class TestModelsSettings:
    def test_defaults_match_default_yaml(self) -> None:
        settings = ModelsSettings()
        assert settings.default == "openrouter/qwen/qwen3.5-flash-02-23"
        assert settings.default_max_tokens == 16384
        assert settings.streaming is True

    def test_presets_default_factory_runs(self) -> None:
        presets = ModelsSettings().presets
        assert presets.fast == "openrouter/google/gemini-2.5-flash"
        assert presets.quality == "openrouter/anthropic/claude-opus-4.6"
        assert presets.balanced == "openrouter/qwen/qwen3.5-flash-02-23"

    def test_override_default_model(self) -> None:
        settings = ModelsSettings(default="anthropic/claude-haiku-4.5")
        assert settings.default == "anthropic/claude-haiku-4.5"

    def test_streaming_can_be_disabled(self) -> None:
        settings = ModelsSettings(streaming=False)
        assert settings.streaming is False

    def test_max_tokens_must_be_int(self) -> None:
        with pytest.raises(ValidationError):
            ModelsSettings(default_max_tokens="lots")  # type: ignore[arg-type]

    def test_presets_overrideable_per_field(self) -> None:
        presets = ModelPresets(fast="openrouter/test/fast")
        assert presets.fast == "openrouter/test/fast"
        assert presets.quality == "openrouter/anthropic/claude-opus-4.6"


class TestPathsSettings:
    def test_defaults(self) -> None:
        paths = PathsSettings()
        assert paths.context_dir == "data/context"
        assert paths.conversations_dir == "data/conversations"
        assert paths.learned_facts == "data/learned_facts.md"
        assert paths.prompt_history_dir == "data/prompt-history"

    def test_override(self) -> None:
        paths = PathsSettings(context_dir="custom/context")
        assert paths.context_dir == "custom/context"


class TestCliSettings:
    def test_defaults(self) -> None:
        cli = CliSettings()
        assert cli.colors is True
        assert cli.history_file == "data/.cli_history"

    def test_disable_colors(self) -> None:
        cli = CliSettings(colors=False)
        assert cli.colors is False


class TestOutcomesSettings:
    def test_defaults_match_default_yaml(self) -> None:
        outcomes = OutcomesSettings()
        assert outcomes.enabled is True
        assert outcomes.dir == "data/outcomes"

    def test_can_be_disabled(self) -> None:
        outcomes = OutcomesSettings(enabled=False)
        assert outcomes.enabled is False


class TestDeveloperSettings:
    def test_defaults_match_default_yaml(self) -> None:
        dev = DeveloperSettings()
        assert dev.enabled is True
        assert dev.scope == [
            "packages/agents/",
            "packages/skills/",
            "data/context/",
            "data/prompts/",
            "config/",
        ]
        assert dev.allowed_extensions == [".md", ".yaml", ".yml"]

    def test_scope_default_is_independent(self) -> None:
        a = DeveloperSettings()
        b = DeveloperSettings()
        a.scope.append("mutated/")
        assert "mutated/" not in b.scope

    def test_scope_override(self) -> None:
        dev = DeveloperSettings(scope=["packages/"])
        assert dev.scope == ["packages/"]


class TestSettingsAggregator:
    def test_empty_construction_uses_section_defaults(self) -> None:
        settings = Settings()
        assert settings.models.default == "openrouter/qwen/qwen3.5-flash-02-23"
        assert settings.paths.context_dir == "data/context"
        assert settings.cli.colors is True
        assert settings.outcomes.enabled is True
        assert settings.developer.enabled is True

    def test_partial_section_override_via_dict(self) -> None:
        settings = Settings(models={"streaming": False})  # type: ignore[arg-type]
        assert settings.models.streaming is False
        assert settings.models.default == "openrouter/qwen/qwen3.5-flash-02-23"

    def test_model_dump_round_trip(self) -> None:
        original = Settings()
        rebuilt = Settings(**original.model_dump())
        assert rebuilt.model_dump() == original.model_dump()
