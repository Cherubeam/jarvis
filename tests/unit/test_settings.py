"""Unit tests for ``packages.core.settings``.

Covers each section's model independently. End-to-end YAML-loading
parity is covered later in PR-8a (commit 8 wires the YAML source loader).
"""

import pytest
from pydantic import ValidationError

from packages.core.settings import (
    CliSettings,
    DeveloperSettings,
    EvaluationSettings,
    MCPServerSettings,
    MCPSettings,
    ModelPresets,
    ModelsSettings,
    ObsidianDailyNotesSettings,
    ObsidianSettings,
    ObsidianWritingSettings,
    ObsidianWritingTargetSettings,
    OutcomesSettings,
    PathsSettings,
    RagSettings,
    RoutingSettings,
    Settings,
    SummarizationSettings,
    Things3Settings,
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


class TestThings3Settings:
    def test_defaults_match_default_yaml(self) -> None:
        t = Things3Settings()
        assert t.enabled is True
        assert t.sync_on_startup is True
        assert t.cache_ttl_seconds == 300
        assert t.lists_to_include == ["Today", "Upcoming", "Inbox"]
        assert t.max_tasks_per_list == 50

    def test_custom_lists(self) -> None:
        t = Things3Settings(lists_to_include=["Anytime"])
        assert t.lists_to_include == ["Anytime"]


class TestEvaluationSettings:
    def test_defaults_match_default_yaml(self) -> None:
        e = EvaluationSettings()
        assert e.judge_model == "anthropic/claude-opus-4.6"
        assert e.quality_threshold == 0.70
        assert e.results_dir == "tests/golden/results"
        assert e.max_cost_per_run == 1.00
        assert e.warn_cost_threshold == 0.50

    def test_category_thresholds_defaults(self) -> None:
        e = EvaluationSettings()
        assert e.category_thresholds == {
            "reasoning": 0.75,
            "context_recall": 0.70,
            "personalization": 0.70,
            "edge_cases": 0.65,
        }

    def test_threshold_must_be_float(self) -> None:
        with pytest.raises(ValidationError):
            EvaluationSettings(quality_threshold="high")  # type: ignore[arg-type]


class TestRagSettings:
    def test_defaults_match_default_yaml(self) -> None:
        r = RagSettings()
        assert r.enabled is True
        assert r.db_path == "data/rag/chroma"
        assert r.embedding_model == "openrouter/openai/text-embedding-3-small"
        assert r.index_cards is True


class TestRoutingSettings:
    def test_defaults_match_default_yaml(self) -> None:
        r = RoutingSettings()
        assert r.enabled is False
        assert r.simple_threshold == 200
        assert r.complex_threshold == 800

    def test_thresholds_overrideable(self) -> None:
        r = RoutingSettings(simple_threshold=100, complex_threshold=500)
        assert r.simple_threshold == 100
        assert r.complex_threshold == 500


class TestSummarizationSettings:
    def test_defaults_match_default_yaml(self) -> None:
        s = SummarizationSettings()
        assert s.enabled is False
        assert s.token_threshold == 40000
        assert s.keep_recent == 10


class TestObsidianSettings:
    def test_defaults_match_default_yaml(self) -> None:
        o = ObsidianSettings()
        assert o.enabled is False
        assert o.vault_path == ""
        assert o.daily_notes.path_format == "Daily Notes/%Y-%m-%d"
        assert o.writing.blog_dir == ""
        assert o.writing.template_path == ""
        assert o.writing.patterns.target_dir == ""
        assert o.writing.patterns.template_path == ""
        assert o.writing.slip_box.target_dir == ""
        assert o.writing.slip_box.template_path == ""
        assert o.prompts_dir == "data/prompts/obsidian"

    def test_local_yaml_shape(self) -> None:
        o = ObsidianSettings(
            enabled=True,
            vault_path="/Users/me/Vault",
            daily_notes=ObsidianDailyNotesSettings(path_format="06/%Y/%Y-%m-%d"),
            writing=ObsidianWritingSettings(
                blog_dir="03/02 Substack",
                template_path="99/00/(TEMPLATE) Blog Post.md",
                patterns=ObsidianWritingTargetSettings(target_dir="04/06 Patterns"),
                slip_box=ObsidianWritingTargetSettings(
                    target_dir="05 Slip-Box",
                    template_path="99/00/(TEMPLATE) Permanent Note",
                ),
            ),
        )
        assert o.enabled is True
        assert o.vault_path == "/Users/me/Vault"
        assert o.daily_notes.path_format == "06/%Y/%Y-%m-%d"
        assert o.writing.patterns.target_dir == "04/06 Patterns"
        assert o.writing.slip_box.template_path == "99/00/(TEMPLATE) Permanent Note"

    def test_nested_dict_construction(self) -> None:
        o = ObsidianSettings.model_validate(
            {
                "enabled": True,
                "vault_path": "/v",
                "writing": {
                    "patterns": {"target_dir": "p"},
                    "slip_box": {"target_dir": "s"},
                },
            }
        )
        assert o.writing.patterns.target_dir == "p"
        assert o.writing.slip_box.target_dir == "s"
        assert o.writing.blog_dir == ""


class TestMCPServerSettings:
    def test_stdio_requires_command(self) -> None:
        with pytest.raises(ValidationError) as exc:
            MCPServerSettings(transport="stdio")
        assert "stdio transport requires 'command'" in str(exc.value)

    def test_stdio_with_command_ok(self) -> None:
        s = MCPServerSettings(transport="stdio", command="npx", args=["-y", "thing"])
        assert s.command == "npx"
        assert s.args == ["-y", "thing"]
        assert s.timeout_seconds == 30.0
        assert s.url is None

    def test_sse_requires_url(self) -> None:
        with pytest.raises(ValidationError) as exc:
            MCPServerSettings(transport="sse")
        assert "sse transport requires 'url'" in str(exc.value)

    def test_streamable_http_requires_url(self) -> None:
        with pytest.raises(ValidationError) as exc:
            MCPServerSettings(transport="streamable_http")
        assert "streamable_http transport requires 'url'" in str(exc.value)

    def test_sse_with_url_ok(self) -> None:
        s = MCPServerSettings(transport="sse", url="https://x")
        assert s.url == "https://x"
        assert s.command is None

    def test_invalid_transport_raises(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerSettings(transport="grpc")  # type: ignore[arg-type]

    def test_env_and_headers_optional(self) -> None:
        s = MCPServerSettings(
            transport="stdio",
            command="npx",
            env={"TOKEN": "abc"},
        )
        assert s.env == {"TOKEN": "abc"}
        assert s.headers is None


class TestMCPSettings:
    def test_defaults(self) -> None:
        m = MCPSettings()
        assert m.enabled is False
        assert m.servers == {}

    def test_double_underscore_in_name_raises(self) -> None:
        with pytest.raises(ValidationError) as exc:
            MCPSettings(
                enabled=True,
                servers={"foo__bar": MCPServerSettings(transport="stdio", command="x")},
            )
        assert "must not contain '__'" in str(exc.value)

    def test_local_yaml_shape(self) -> None:
        m = MCPSettings.model_validate(
            {
                "enabled": True,
                "servers": {
                    "n8n": {
                        "transport": "stdio",
                        "tool_group": "n8n",
                        "timeout_seconds": 30,
                        "command": "npx",
                        "args": ["-y", "n8n-mcp"],
                        "env": {"N8N_API_URL": "https://x", "N8N_API_KEY": "abc"},
                    }
                },
            }
        )
        assert m.enabled is True
        n8n = m.servers["n8n"]
        assert n8n.transport == "stdio"
        assert n8n.tool_group == "n8n"
        assert n8n.command == "npx"
        assert n8n.env == {"N8N_API_URL": "https://x", "N8N_API_KEY": "abc"}


class TestSettingsAggregator:
    def test_empty_construction_uses_section_defaults(self) -> None:
        settings = Settings()
        assert settings.models.default == "openrouter/qwen/qwen3.5-flash-02-23"
        assert settings.paths.context_dir == "data/context"
        assert settings.cli.colors is True
        assert settings.outcomes.enabled is True
        assert settings.things3.enabled is True
        assert settings.evaluation.judge_model == "anthropic/claude-opus-4.6"
        assert settings.rag.enabled is True
        assert settings.routing.enabled is False
        assert settings.summarization.enabled is False
        assert settings.obsidian.enabled is False
        assert settings.mcp.enabled is False
        assert settings.developer.enabled is True

    def test_partial_section_override_via_dict(self) -> None:
        settings = Settings(models={"streaming": False})  # type: ignore[arg-type]
        assert settings.models.streaming is False
        assert settings.models.default == "openrouter/qwen/qwen3.5-flash-02-23"

    def test_model_dump_round_trip(self) -> None:
        original = Settings()
        rebuilt = Settings(**original.model_dump())
        assert rebuilt.model_dump() == original.model_dump()
