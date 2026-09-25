"""Per-agent models: meta.yaml `model:` → pinned agent → StreamHandler.using_model()."""

from unittest.mock import Mock

import pytest
import yaml

from apps.cli.session_factory import instantiate_agent
from packages.agents.registry import AgentMeta, _discover_from_meta_yaml
from packages.core.llm_client import LLMClient
from packages.core.pricing import ModelPricing
from packages.core.settings import ModelPresets, ModelsSettings
from packages.core.stream_handler import StreamHandler, StreamResult
from packages.telemetry.metrics import MetricsTracker

SESSION = "openrouter/openai/gpt-6-luna"
QUALITY = "openrouter/anthropic/claude-opus-5.5"
MODELS = ModelsSettings(default=SESSION, presets=ModelPresets(fast=SESSION, balanced=SESSION, quality=QUALITY))


def _agent_dir(tmp_path, **meta):
    d = tmp_path / "agent"
    (d / "prompts").mkdir(parents=True)
    (d / "prompts" / "system.md").write_text("You are a test agent.")
    (d / "meta.yaml").write_text(yaml.dump({"name": "reviewer", "description": "d", **meta}))
    return d


def _handler(model_id=SESSION, max_tokens=16384):
    client = LLMClient(api_keys={}, default_model=model_id)
    pricing = ModelPricing(prompt_cost=1e-7, completion_cost=5e-7, model_id=model_id)
    return StreamHandler(client, MetricsTracker(), pricing, model_id, max_tokens=max_tokens)


@pytest.mark.unit
class TestMetaYamlModel:
    def test_registry_reads_model(self, tmp_path):
        meta = _discover_from_meta_yaml(_agent_dir(tmp_path, model="quality"))
        assert meta is not None and meta.model == "quality"

    def test_registry_model_defaults_to_none(self, tmp_path):
        meta = _discover_from_meta_yaml(_agent_dir(tmp_path))
        assert meta is not None and meta.model is None

    def test_preset_resolves_and_pins(self, tmp_path):
        meta = _discover_from_meta_yaml(_agent_dir(tmp_path, model="quality"))
        agent = instantiate_agent(meta, Mock(spec=LLMClient), SESSION, models=MODELS)
        assert agent.config.model == QUALITY
        assert agent.config.model_pinned is True

    def test_literal_model_id_pins(self, tmp_path):
        meta = _discover_from_meta_yaml(_agent_dir(tmp_path, model="openrouter/z-ai/glm-5.3"))
        agent = instantiate_agent(meta, Mock(spec=LLMClient), SESSION, models=MODELS)
        assert agent.config.model == "openrouter/z-ai/glm-5.3"
        assert agent.config.model_pinned is True

    def test_without_model_uses_session_model_unpinned(self, tmp_path):
        meta = _discover_from_meta_yaml(_agent_dir(tmp_path))
        agent = instantiate_agent(meta, Mock(spec=LLMClient), SESSION, models=MODELS)
        assert agent.config.model == SESSION
        assert agent.config.model_pinned is False

    def test_preset_resolves_against_loaded_config_not_builtin_defaults(self, tmp_path):
        custom = MODELS.model_copy(update={"presets": ModelPresets(quality="openrouter/test/custom-quality")})
        meta = _discover_from_meta_yaml(_agent_dir(tmp_path, model="quality"))
        agent = instantiate_agent(meta, Mock(spec=LLMClient), SESSION, models=custom)
        assert agent.config.model == "openrouter/test/custom-quality"

    def test_meta_without_path_raises(self):
        with pytest.raises(ValueError, match="no meta_path"):
            instantiate_agent(AgentMeta(name="x", description="", command="/x"), Mock(spec=LLMClient), SESSION)


@pytest.mark.unit
class TestUsingModel:
    def test_switches_and_restores(self):
        handler = _handler()
        original_pricing = handler.pricing
        with handler.using_model(QUALITY):
            assert handler.model_id == QUALITY
            assert handler.client.default_model == QUALITY
            assert handler.pricing is not original_pricing
        assert handler.model_id == SESSION
        assert handler.client.default_model == SESSION
        assert handler.pricing is original_pricing

    def test_restores_after_exception(self):
        handler = _handler()
        with pytest.raises(RuntimeError), handler.using_model(QUALITY):
            raise RuntimeError("boom")
        assert handler.model_id == SESSION
        assert handler.client.default_model == SESSION

    def test_same_model_keeps_pricing(self):
        handler = _handler()
        original_pricing = handler.pricing
        with handler.using_model(SESSION):
            assert handler.pricing is original_pricing


@pytest.mark.unit
class TestPinnedAgentRun:
    def _run(self, tmp_path, handler, **meta):
        seen: dict[str, object] = {}

        def fake_stream(messages, **kwargs):
            seen["model"] = handler.model_id
            seen["client_model"] = handler.client.default_model
            seen["max_tokens"] = handler.max_tokens
            return Mock(spec=StreamResult)

        handler.stream = fake_stream  # type: ignore[method-assign]
        agent = instantiate_agent(
            _discover_from_meta_yaml(_agent_dir(tmp_path, **meta)), handler.client, SESSION, models=MODELS
        )
        agent.run("hi", handler)
        return seen

    def test_pinned_agent_runs_on_its_model_then_restores(self, tmp_path):
        handler = _handler()
        seen = self._run(tmp_path, handler, model="quality")
        assert seen["model"] == QUALITY
        assert seen["client_model"] == QUALITY  # nested tool calls (evaluate_content) follow
        assert handler.model_id == SESSION

    def test_unpinned_agent_keeps_the_current_model(self, tmp_path):
        """Routing may have switched the handler; an unpinned agent must not undo that."""
        handler = _handler(model_id="openrouter/routed/model")
        seen = self._run(tmp_path, handler)
        assert seen["model"] == "openrouter/routed/model"

    def test_agent_max_tokens_is_restored_after_run(self, tmp_path):
        handler = _handler(max_tokens=16384)
        seen = self._run(tmp_path, handler, max_tokens=4096)
        assert seen["max_tokens"] == 4096
        assert handler.max_tokens == 16384

    def test_credit_reduction_during_run_is_kept(self, tmp_path):
        handler = _handler(max_tokens=16384)

        def reducing_stream(messages, **kwargs):
            handler.max_tokens = 1000  # _try_with_credit_fallback lowered it
            return Mock(spec=StreamResult)

        handler.stream = reducing_stream  # type: ignore[method-assign]
        agent = instantiate_agent(
            _discover_from_meta_yaml(_agent_dir(tmp_path, max_tokens=4096)), handler.client, SESSION, models=MODELS
        )
        agent.run("hi", handler)
        assert handler.max_tokens == 1000


@pytest.mark.unit
class TestPinnedModelLabel:
    def test_label_for_pinned_agent(self, tmp_path):
        from apps.cli.main import _pinned_model_label

        meta = _discover_from_meta_yaml(_agent_dir(tmp_path, model="quality"))
        agent = instantiate_agent(meta, Mock(spec=LLMClient), SESSION, models=MODELS)
        assert _pinned_model_label(agent) == "claude-opus-5.5 via openrouter"

    def test_no_label_for_unpinned_agent(self, tmp_path):
        from apps.cli.main import _pinned_model_label

        agent = instantiate_agent(_discover_from_meta_yaml(_agent_dir(tmp_path)), Mock(spec=LLMClient), SESSION)
        assert _pinned_model_label(agent) is None
