"""Cost ledger and spend limits (AON-01)."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from packages.core.cost_ledger import ESTIMATE_MARGIN, CostLedger, weighted_cost
from packages.core.llm_client import LLMClient, StreamToolResult, TokenUsage
from packages.core.pricing import ModelPricing
from packages.core.stream_handler import StreamHandler
from packages.core.tools.base import ToolDefinition, ToolRegistry
from packages.telemetry.metrics import MetricsTracker


def _record(ledger: CostLedger, cost: float, billed: bool = True, purpose: str = "turn") -> None:
    ledger.record(
        purpose=purpose,
        model="m",
        prompt_tokens=100,
        completion_tokens=10,
        cache_read_tokens=40,
        cost_usd=cost,
        billed=billed,
    )


def _lines(ledger: CostLedger) -> list[dict]:
    files = sorted(ledger.directory.glob("*.jsonl"))
    return [json.loads(line) for f in files for line in f.read_text(encoding="utf-8").splitlines()]


# ==================== CostLedger ====================


@pytest.mark.unit
class TestCostLedger:
    def test_record_appends_one_line_with_session(self, tmp_path):
        ledger = CostLedger(tmp_path / "ledger", lambda: "conv_1")

        _record(ledger, 0.25)
        _record(ledger, 0.5, billed=False, purpose="evaluate")

        rows = _lines(ledger)
        assert [(r["session_id"], r["purpose"], r["cost_usd"], r["usage_source"]) for r in rows] == [
            ("conv_1", "turn", 0.25, "billed"),
            ("conv_1", "evaluate", 0.5, "estimated"),
        ]
        assert (rows[0]["model"], rows[0]["prompt_tokens"], rows[0]["cache_read_tokens"]) == ("m", 100, 40)

    def test_month_spend_weights_estimates(self, tmp_path):
        ledger = CostLedger(tmp_path)
        _record(ledger, 1.0, billed=True)
        _record(ledger, 2.0, billed=False)

        assert ledger.month_spend() == 1.0 + 2.0 * ESTIMATE_MARGIN

    def test_month_spend_skips_broken_lines_and_missing_month(self, tmp_path):
        ledger = CostLedger(tmp_path)
        _record(ledger, 0.5)
        month_file = next(tmp_path.glob("*.jsonl"))
        with month_file.open("a", encoding="utf-8") as f:
            f.write('{"cost_usd": "x"\n')

        assert ledger.month_spend() == 0.5
        assert ledger.month_spend("1999-01") == 0.0

    def test_failed_write_is_logged_not_raised(self, tmp_path, caplog):
        blocker = tmp_path / "ledger"
        blocker.write_text("a file, not a directory")

        _record(CostLedger(blocker), 0.5)

        assert "Cost ledger not written" in caplog.text

    def test_weighted_cost(self):
        assert weighted_cost(2.0, "billed") == 2.0
        assert weighted_cost(2.0, "estimated") == 3.0

    def test_record_response_billed_and_estimated(self, tmp_path):
        ledger = CostLedger(tmp_path)
        billed = SimpleNamespace(
            model="openrouter/anthropic/claude-opus-5.5",
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200, cost=0.25),
        )
        ledger.record_response(billed, purpose="evaluate", model="fallback")

        row = _lines(ledger)[0]
        assert (row["purpose"], row["model"], row["cost_usd"], row["usage_source"]) == (
            "evaluate",
            "openrouter/anthropic/claude-opus-5.5",
            0.25,
            "billed",
        )
        assert (row["prompt_tokens"], row["completion_tokens"]) == (1000, 200)


# ==================== StreamHandler limits ====================


def _response(tool_calls=None, content=""):
    usage = Mock(spec=["prompt_tokens", "completion_tokens", "total_tokens", "prompt_tokens_details"])
    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens = 1000, 0, 1000
    usage.prompt_tokens_details = None
    choice = Mock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    response = Mock()
    response.choices = [choice]
    response.usage = usage
    return response


def _tool_call(n: int):
    call = Mock()
    call.id = f"tc_{n}"
    call.function.name = "read_note"
    call.function.arguments = f'{{"n": {n}}}'  # distinct, so dedup keeps every round
    return call


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="read_note",
            description="Read a note",
            parameters={"type": "object", "properties": {}},
            execute=lambda **kwargs: "note content",
        )
    )
    return registry


def _handler(client, tmp_path, *, max_turn_usd=0.0, monthly_usd=0.0) -> StreamHandler:
    client.ledger = CostLedger(tmp_path, lambda: "conv_1")
    # 1,000 prompt tokens at $0.0004 each: every round costs $0.40, counted $0.60 as an estimate
    pricing = ModelPricing(prompt_cost=0.0004, completion_cost=0.0, model_id="m")
    handler = StreamHandler(client, MetricsTracker(), pricing, "m", streaming=False)
    handler.max_turn_usd = max_turn_usd
    handler.monthly_usd = monthly_usd
    return handler


@pytest.mark.unit
class TestTurnCeiling:
    def test_loop_stops_before_next_call_once_over_limit(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.side_effect = [_response([_tool_call(i)]) for i in range(5)]
        handler = _handler(client, tmp_path, max_turn_usd=1.0)

        result = handler.stream([{"role": "user", "content": "go"}], tool_registry=_registry(), max_iterations=5)

        # Round 1 counts $0.60, round 2 $1.20 ≥ $1.00: no third call
        assert client.complete.call_count == 2
        assert result.text == (
            "Stopped: this turn reached about $1.20 of the $1.00 per-turn limit (budget.max_turn_usd). "
            "Ask again to continue."
        )
        assert len(result.tool_messages) == 4  # both rounds' tool calls and results are kept

    def test_streaming_loop_stops_too(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.stream_with_tool_detection.side_effect = [
            StreamToolResult(tool_calls=[_tool_call(i)], usage=TokenUsage(prompt_tokens=1000, total_tokens=1000))
            for i in range(5)
        ]
        handler = _handler(client, tmp_path, max_turn_usd=1.0)
        handler.streaming = True

        result = handler.stream([{"role": "user", "content": "go"}], tool_registry=_registry(), max_iterations=5)

        assert client.stream_with_tool_detection.call_count == 2
        assert result.text.startswith("Stopped: this turn reached about $1.20 of the $1.00 per-turn limit")

    def test_no_limit_runs_until_answer(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.side_effect = [_response([_tool_call(0)]), _response([_tool_call(1)]), _response(content="ok")]
        handler = _handler(client, tmp_path)

        result = handler.stream([{"role": "user", "content": "go"}], tool_registry=_registry())

        assert client.complete.call_count == 3
        assert result.text == "ok"

    def test_turn_is_recorded_in_ledger(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response(content="answer")
        handler = _handler(client, tmp_path)

        handler.stream([{"role": "user", "content": "hi"}])

        rows = _lines(client.ledger)
        assert [(r["purpose"], r["session_id"], r["cost_usd"], r["usage_source"]) for r in rows] == [
            ("turn", "conv_1", pytest.approx(0.4), "estimated")
        ]


@pytest.mark.unit
class TestMonthlyBudget:
    def _over_budget(self, tmp_path, client):
        handler = _handler(client, tmp_path, monthly_usd=1.0)
        _record(client.ledger, 2.0)  # billed $2.00 > $1.00
        return handler

    def test_refused_turn_makes_no_call(self, tmp_path):
        client = Mock(spec=LLMClient)
        handler = self._over_budget(tmp_path, client)
        handler.on_budget_exceeded = Mock(return_value=False)

        result = handler.stream([{"role": "user", "content": "hi"}])

        client.complete.assert_not_called()
        handler.on_budget_exceeded.assert_called_once_with(2.0, 1.0)
        assert result.text == "Not sent: this month's spend ($2.00) is over the $1.00 budget."

    def test_accepted_once_per_session(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response(content="ok")
        handler = self._over_budget(tmp_path, client)
        handler.on_budget_exceeded = Mock(return_value=True)

        handler.stream([{"role": "user", "content": "one"}])
        handler.stream([{"role": "user", "content": "two"}])

        assert handler.on_budget_exceeded.call_count == 1
        assert client.complete.call_count == 2

    def test_without_callback_warns_once_and_continues(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response(content="ok")
        handler = self._over_budget(tmp_path, client)
        notices: list[str] = []
        handler.on_budget_notice = notices.append

        handler.stream([{"role": "user", "content": "one"}])
        handler.stream([{"role": "user", "content": "two"}])

        assert notices == ["Monthly budget: $2.00 of $1.00 used (budget.monthly_usd)."]
        assert client.complete.call_count == 2

    def test_warns_at_80_percent(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response(content="ok")
        handler = _handler(client, tmp_path, monthly_usd=1.0)
        _record(client.ledger, 0.85)
        notices: list[str] = []
        handler.on_budget_notice = notices.append

        handler.stream([{"role": "user", "content": "hi"}])

        assert notices == ["Monthly budget: $0.85 of $1.00 used."]

    def test_below_80_percent_is_silent(self, tmp_path):
        client = Mock(spec=LLMClient)
        client.complete.return_value = _response(content="ok")
        handler = _handler(client, tmp_path, monthly_usd=1.0)
        _record(client.ledger, 0.5)
        notices: list[str] = []
        handler.on_budget_notice = notices.append

        handler.stream([{"role": "user", "content": "hi"}])

        assert notices == []
