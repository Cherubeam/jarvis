"""OpenRouter Auto Router mode: config, request fields, routing, cost and served-model tracking."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import litellm
import pytest
from pydantic import ValidationError

from apps.cli.main import _price_info, _should_route
from apps.cli.session_factory import session_model_source
from packages.core.llm_client import InsufficientCreditsError, LLMClient, TokenUsage, reported_cost, served_model
from packages.core.model_resolver import AUTO_MODEL_ID, resolve_model, session_extra_body
from packages.core.pricing import ModelPricing
from packages.core.settings import AutoRouterSettings, ModelsSettings, RoutingSettings, Settings, load_config
from packages.core.stream_handler import StreamHandler, StreamResult, served_metadata
from packages.core.tools.base import ToolDefinition, ToolRegistry
from packages.telemetry.metrics import MetricsTracker

ZERO_PRICING = ModelPricing(prompt_cost=0, completion_cost=0, model_id=AUTO_MODEL_ID)  # what LiteLLM lists for auto


def _response(content="", tool_calls=None, model="z-ai/glm-5.3-flash", cost=0.001, tokens=(100, 20)):
    usage = SimpleNamespace(
        prompt_tokens=tokens[0],
        completion_tokens=tokens[1],
        total_tokens=sum(tokens),
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        prompt_tokens_details=None,
        cost=cost,
    )
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model=model)


def _tool_call():
    call = Mock()
    call.id, call.function.name, call.function.arguments = "tc1", "lookup", "{}"
    return call


def _registry():
    registry = ToolRegistry()
    registry.register(ToolDefinition(name="lookup", description="t", parameters={}, execute=lambda: "ok"))
    return registry


def _handler(client, model_id=AUTO_MODEL_ID, pricing=ZERO_PRICING, streaming=True):
    return StreamHandler(client, MetricsTracker(), pricing, model_id, streaming=streaming)


@pytest.mark.unit
class TestConfig:
    def test_defaults_off(self):
        auto = AutoRouterSettings()
        assert auto.enabled is False
        assert auto.cost_tier == "low"
        assert auto.excluded_models == []

    def test_invalid_cost_tier_rejected(self):
        with pytest.raises(ValidationError):
            AutoRouterSettings(cost_tier="cheap")  # type: ignore[arg-type]

    def test_default_yaml_matches_model_defaults(self):
        assert load_config().models.auto_router.model_dump() == AutoRouterSettings().model_dump()

    def test_auto_alias_resolves(self):
        assert resolve_model("auto", ModelsSettings()).model_id == AUTO_MODEL_ID

    def test_session_model_source(self):
        off = ModelsSettings(default="openrouter/openai/gpt-6-luna")
        on = off.model_copy(update={"auto_router": AutoRouterSettings(enabled=True)})
        assert session_model_source(None, off) == "openrouter/openai/gpt-6-luna"
        assert session_model_source(None, on) == "auto"
        assert session_model_source("quality", on) == "quality"  # --model wins


@pytest.mark.unit
class TestSessionExtraBody:
    def test_plugin_block_and_session_id(self):
        body = session_extra_body(ModelsSettings(), session_id="conv-1")[AUTO_MODEL_ID]
        assert body == {"plugins": [{"id": "auto-router", "cost_tier": "low"}], "session_id": "conv-1"}

    def test_excluded_models_included_when_set(self):
        models = ModelsSettings(auto_router=AutoRouterSettings(cost_tier="medium", excluded_models=["google/x"]))
        plugin = session_extra_body(models, "s")[AUTO_MODEL_ID]["plugins"][0]
        assert plugin == {"id": "auto-router", "cost_tier": "medium", "excluded_models": ["google/x"]}

    def test_keeps_other_models_and_does_not_mutate_settings(self):
        models = ModelsSettings()
        before = {k: dict(v) for k, v in models.extra_body.items()}
        body = session_extra_body(models, "s")
        assert models.extra_body == before  # a GUI settings save must not persist the plugin block
        for model_id, fields in before.items():
            assert body[model_id] == fields

    def test_user_extra_body_for_auto_is_kept(self):
        models = ModelsSettings(extra_body={AUTO_MODEL_ID: {"provider": {"max_price": {"prompt": 1}}}})
        body = session_extra_body(models, "s")[AUTO_MODEL_ID]
        assert body["provider"] == {"max_price": {"prompt": 1}}
        assert body["plugins"][0]["id"] == "auto-router"


@pytest.mark.unit
class TestRoutingGuard:
    def _settings(self):
        return Settings(routing=RoutingSettings(enabled=True))

    def test_routes_fixed_model(self):
        assert _should_route(self._settings(), "openrouter/openai/gpt-6-luna", None) is True

    def test_skips_auto(self):
        """Covers the config switch, --model auto and /model auto alike."""
        assert _should_route(self._settings(), AUTO_MODEL_ID, None) is False

    def test_skips_pinned_agent(self):
        agent = SimpleNamespace(config=SimpleNamespace(model_pinned=True))
        assert _should_route(self._settings(), "openrouter/openai/gpt-6-luna", agent) is False

    def test_off_when_routing_disabled(self):
        assert _should_route(Settings(), "openrouter/openai/gpt-6-luna", None) is False

    def test_price_info_for_auto(self):
        assert _price_info(AUTO_MODEL_ID, ZERO_PRICING) == "priced per chosen model"
        assert _price_info("x", None) == "pricing unavailable"


@pytest.mark.unit
class TestUsageAndResponseReaders:
    def test_add_sums_reported_costs(self):
        total = TokenUsage(prompt_tokens=1, reported_cost=0.5) + TokenUsage(prompt_tokens=2, reported_cost=0.25)
        assert total.prompt_tokens == 3
        assert total.reported_cost == 0.75

    def test_add_keeps_cost_when_one_side_reported(self):
        assert (TokenUsage(reported_cost=0.0) + TokenUsage()).reported_cost == 0.0  # 0.0 is a real cost
        assert (TokenUsage() + TokenUsage()).reported_cost is None

    def test_readers_ignore_non_values(self):
        assert reported_cost(SimpleNamespace(cost=0.002)) == 0.002
        assert reported_cost(Mock()) is None
        assert reported_cost(None) is None
        assert served_model(SimpleNamespace(model="openai/gpt-6-luna")) == "openai/gpt-6-luna"
        assert served_model(Mock()) is None

    def test_served_metadata(self):
        assert served_metadata(SimpleNamespace(served_models=["a", "b"])) == {"served_models": ["a", "b"]}
        assert served_metadata(SimpleNamespace(served_models=[])) is None
        assert served_metadata(Mock()) is None


@pytest.mark.unit
class TestStreamHandlerAuto:
    def test_auto_never_streams_and_uses_reported_cost_over_zero_pricing(self):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response("hi", cost=0.0042)
        result = _handler(client).stream([{"role": "user", "content": "hi"}])

        client.chat_stream.assert_not_called()
        assert result.text == "hi"
        assert result.cost_usd == pytest.approx(0.0042)
        assert result.served_models == ["z-ai/glm-5.3-flash"]

    def test_cost_and_models_accumulate_across_tool_loop(self):
        client = Mock(spec=LLMClient)
        client.complete.side_effect = [
            _response(tool_calls=[_tool_call()], model="openai/gpt-6-luna", cost=0.001),
            _response("done", model="z-ai/glm-5.3-flash", cost=0.002),
        ]
        result = _handler(client).stream([{"role": "user", "content": "hi"}], tool_registry=_registry())

        client.stream_with_tool_detection.assert_not_called()
        assert result.cost_usd == pytest.approx(0.003)
        assert result.served_models == ["openai/gpt-6-luna", "z-ai/glm-5.3-flash"]

    def test_same_model_twice_listed_once(self):
        client = Mock(spec=LLMClient)
        client.complete.side_effect = [_response(tool_calls=[_tool_call()]), _response("done")]
        result = _handler(client).stream([{"role": "user", "content": "hi"}], tool_registry=_registry())
        assert result.served_models == ["z-ai/glm-5.3-flash"]

    def test_fixed_model_records_no_served_models(self):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response("hi", model="openai/gpt-6-luna")
        pricing = ModelPricing(prompt_cost=1e-7, completion_cost=5e-7, model_id="m")
        result = _handler(client, model_id="openrouter/openai/gpt-6-luna", pricing=pricing, streaming=False).stream(
            [{"role": "user", "content": "hi"}]
        )
        assert result.served_models == []
        assert result.cost_usd == pytest.approx(0.001)  # reported cost wins for any non-streaming call

    def test_fixed_model_still_streams(self):
        client = Mock(spec=LLMClient)
        client.chat_stream.return_value = Mock(
            __iter__=lambda self: iter(["a"]), usage=TokenUsage(prompt_tokens=1), raw_response=None
        )
        _handler(client, model_id="openrouter/openai/gpt-6-luna", pricing=None).stream(
            [{"role": "user", "content": "x"}]
        )
        client.chat_stream.assert_called_once()
        client.complete.assert_not_called()


@pytest.mark.unit
class TestCompleteCreditErrors:
    def test_402_becomes_insufficient_credits_error(self):
        error = litellm.APIError(  # type: ignore[attr-defined]
            status_code=402,
            message="This request requires more credits, or fewer max_tokens. You requested up to 16384 tokens, "
            "but can only afford 5000.",
            llm_provider="openrouter",
            model="m",
        )
        client = LLMClient(api_keys={"openrouter": "k"}, default_model=AUTO_MODEL_ID)
        with patch("litellm.completion", side_effect=error), pytest.raises(InsufficientCreditsError) as exc:
            client.complete([{"role": "user", "content": "hi"}], max_tokens=16384)
        assert exc.value.affordable == 5000


@pytest.mark.unit
def test_stats_line_names_auto_choice(capsys):
    from apps.cli.display import print_usage_stats

    result = Mock(spec=StreamResult)
    result.metrics = SimpleNamespace(ttft_ms=10, total_latency_ms=20)
    result.usage = TokenUsage(total_tokens=5)
    result.cost_usd = 0.001
    result.served_models = ["openai/gpt-6-luna", "z-ai/glm-5.3-flash"]
    print_usage_stats(result)
    assert "Model: auto → openai/gpt-6-luna, z-ai/glm-5.3-flash" in capsys.readouterr().out
