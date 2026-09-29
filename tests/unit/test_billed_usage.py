"""Tests for replacing streamed usage estimates with OpenRouter's billed records."""

from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from packages.core import billed_usage
from packages.core.billed_usage import fetch_billed_usage
from packages.core.llm_client import TokenUsage, _attach_generation_id
from packages.core.memory import ConversationLogger
from packages.core.stream_handler import served_metadata

pytestmark = pytest.mark.unit


def _record(prompt: int, completion: int, cost: float, cached: int = 0) -> dict:
    return {
        "data": {
            "native_tokens_prompt": prompt,
            "native_tokens_completion": completion,
            "native_tokens_cached": cached,
            "total_cost": cost,
        }
    }


def _client(responses: dict[str, list[httpx.Response]]) -> httpx.Client:
    """Serve queued responses per generation id; records each request."""

    def handler(request: httpx.Request) -> httpx.Response:
        return responses[request.url.params["id"]].pop(0)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(billed_usage.time, "sleep", lambda _s: None)


def test_sums_billed_records_across_calls():
    client = _client(
        {
            "gen-1": [httpx.Response(200, json=_record(3931, 60, 0.016924, cached=100))],
            "gen-2": [httpx.Response(200, json=_record(1000, 40, 0.005))],
        }
    )
    usage = fetch_billed_usage(["gen-1", "gen-2"], "key", client=client)
    assert usage is not None
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (4931, 100, 5031)
    assert usage.cache_read_tokens == 100
    assert usage.reported_cost == pytest.approx(0.021924)
    assert usage.generation_ids == ["gen-1", "gen-2"]


def test_retries_while_the_record_is_not_ready():
    client = _client(
        {"gen-1": [httpx.Response(404), httpx.Response(404), httpx.Response(200, json=_record(10, 5, 0.1))]}
    )
    usage = fetch_billed_usage(["gen-1"], "key", client=client, deadline_s=10)
    assert usage is not None and usage.reported_cost == 0.1


def test_gives_up_after_the_deadline(monkeypatch):
    clock = iter(range(0, 1000, 3))  # every monotonic() call advances 3 s
    monkeypatch.setattr(billed_usage.time, "monotonic", lambda: next(clock))
    client = _client({"gen-1": [httpx.Response(404)] * 20})
    assert fetch_billed_usage(["gen-1"], "key", client=client, deadline_s=8) is None


def test_all_or_nothing_when_one_record_fails():
    client = _client(
        {
            "gen-1": [httpx.Response(200, json=_record(10, 5, 0.1))],
            "gen-2": [httpx.Response(500)],
        }
    )
    assert fetch_billed_usage(["gen-1", "gen-2"], "key", client=client) is None


def test_record_without_cost_is_rejected():
    client = _client({"gen-1": [httpx.Response(200, json={"data": {"native_tokens_prompt": 10}})]})
    assert fetch_billed_usage(["gen-1"], "key", client=client) is None


def test_network_error_falls_back():
    def boom(request):
        raise httpx.ConnectError("offline")

    client = httpx.Client(transport=httpx.MockTransport(boom))
    assert fetch_billed_usage(["gen-1"], "key", client=client) is None


def test_default_asks_once_without_waiting():
    client = _client({"gen-1": [httpx.Response(404), httpx.Response(200, json=_record(10, 5, 0.1))]})
    assert fetch_billed_usage(["gen-1"], "key", client=client) is None


def test_no_ids_no_lookup():
    assert fetch_billed_usage([], "key") is None


# --- capture and accumulation ---


@pytest.mark.parametrize(
    ("model", "expected"),
    [("openrouter/anthropic/claude-opus-5.5", ["gen-1"]), ("anthropic/claude-opus-5.5", [])],
)
def test_generation_id_recorded_for_openrouter_only(model, expected):
    usage = TokenUsage()
    _attach_generation_id(usage, "gen-1", model)
    assert usage.generation_ids == expected


def test_usage_addition_keeps_all_generation_ids():
    total = TokenUsage(generation_ids=["a"]) + TokenUsage(generation_ids=["b", "c"])
    assert total.generation_ids == ["a", "b", "c"]


# --- log metadata ---


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (TokenUsage(total_tokens=10, reported_cost=0.1), {"usage_source": "billed"}),
        (TokenUsage(total_tokens=10), {"usage_source": "estimated"}),
        (
            TokenUsage(total_tokens=10, generation_ids=["gen-1"]),
            {"usage_source": "estimated", "generation_ids": ["gen-1"]},
        ),
    ],
)
def test_log_metadata_says_where_usage_came_from(usage, expected):
    assert served_metadata(SimpleNamespace(usage=usage)) == expected


# --- ConversationLogger reconciliation ---


def _logger(tmp_path, key="key") -> ConversationLogger:
    log = ConversationLogger(tmp_path)
    log.billing_api_key = key
    log.add_message("user", "hi")
    log.add_message(
        "assistant",
        "estimated turn",
        prompt_tokens=2615,
        completion_tokens=20,
        total_tokens=2635,
        cost_usd=0.0109,
        metadata={"usage_source": "estimated", "generation_ids": ["gen-1"]},
    )
    log.add_message(
        "assistant",
        "billed turn",
        prompt_tokens=100,
        completion_tokens=10,
        total_tokens=110,
        cost_usd=0.001,
        metadata={"usage_source": "billed"},
    )
    return log


_BILLED = TokenUsage(
    prompt_tokens=3931, completion_tokens=60, total_tokens=3991, cache_read_tokens=5, reported_cost=0.0169
)


def test_logger_swaps_estimate_for_billed_record_and_fixes_totals(tmp_path):
    log = _logger(tmp_path)
    with patch("packages.core.billed_usage.fetch_billed_usage", return_value=_BILLED) as fetch:
        assert log.reconcile_billed_usage() == 1
    fetch.assert_called_once_with(["gen-1"], "key", deadline_s=0.0)

    msg = log.current_conversation[1]
    assert msg["usage"]["prompt_tokens"] == 3931
    assert msg["usage"]["cost_usd"] == 0.0169
    assert msg["metadata"]["usage_source"] == "billed"
    assert log.metrics.total_prompt_tokens == 3931 + 100
    assert isinstance(log.metrics.total_prompt_tokens, int)  # stays an int in the JSON
    assert log.metrics.total_cost_usd == pytest.approx(0.0169 + 0.001)
    assert log.metrics.total_cache_read_tokens == 5


def test_logger_keeps_estimate_until_record_is_published(tmp_path):
    log = _logger(tmp_path)
    with patch("packages.core.billed_usage.fetch_billed_usage", return_value=None):
        assert log.reconcile_billed_usage() == 0
    assert log.current_conversation[1]["metadata"]["usage_source"] == "estimated"
    assert log.metrics.total_cost_usd == pytest.approx(0.0109 + 0.001)


def test_logger_without_key_does_nothing(tmp_path):
    log = _logger(tmp_path, key=None)
    with patch("packages.core.billed_usage.fetch_billed_usage") as fetch:
        assert log.reconcile_billed_usage() == 0
    fetch.assert_not_called()


def test_session_summary_marks_remaining_estimates(tmp_path, capsys):
    log = _logger(tmp_path)
    log._print_session_summary()
    out = capsys.readouterr().out
    assert "Session: ~" in out
    assert "1 turn(s) still estimated" in out
    assert "scripts/backfill_billed_usage.py" in out
