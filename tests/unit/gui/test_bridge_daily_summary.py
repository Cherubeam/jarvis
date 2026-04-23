"""Tests for the /daily-summary branch in apps.gui.server.bridge.run_turn."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.gui.server.bridge import run_turn
from packages.core.daily_summary import DailySummaryError, DailySummaryFailure, DailySummaryRequest
from packages.core.llm_client import TokenUsage
from packages.core.stream_handler import StreamResult


@dataclass
class _FakeMetrics:
    ttft_ms: int = 120
    total_latency_ms: int = 800
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def record_history_tokens(self, _n: int) -> None:  # for parity
        pass


_SENTINEL_VAULT: Any = object()


def _make_session(tmp_path: Path, vault_config: Any = _SENTINEL_VAULT) -> SimpleNamespace:
    """Build a minimal GuiSession-shaped object for the bridge."""
    if vault_config is _SENTINEL_VAULT:
        vault_config = MagicMock()
    stream_handler = MagicMock()
    stream_handler.max_tokens = None
    stream_handler.on_chunk = None
    stream_handler.on_event = None

    # stream_handler.stream returns a minimal StreamResult.
    stream_handler.stream.return_value = StreamResult(
        text="summary text",
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        cost_usd=0.001,
        metrics=SimpleNamespace(ttft_ms=120, total_latency_ms=800),
        tool_messages=[],
    )

    logger_obj = MagicMock()
    logger_obj.get_messages_for_api.return_value = []
    logger_obj.session_start = MagicMock()
    logger_obj.session_start.strftime = MagicMock(return_value="2026-04-23_12-00-00")
    logger_obj.current_conversation = []
    logger_obj.metrics = _FakeMetrics()

    components = SimpleNamespace(
        agent_name="JARVIS",
        stream_handler=stream_handler,
        config={"_paths": {"jarvis_dir": tmp_path}},
        vault_config=vault_config,
        system_prompt="SYS",
        logger=logger_obj,
        active_agent=MagicMock(),
        context_metadata=None,
        _deferred_handler=None,
    )
    session = SimpleNamespace(
        components=components,
        confirmation=None,
        conversation_index=None,
    )
    return session


def _drain(queue: Queue) -> list[dict]:
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


@pytest.mark.asyncio
async def test_invalid_date_emits_error_and_turn_finished(tmp_path: Path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    await run_turn(session, "/daily-summary not-a-date", q)

    events = _drain(q)
    kinds = [e["type"] for e in events]
    assert kinds == ["user", "error", "turn_finished"]
    assert "not-a-date" in events[1]["message"]
    session.components.stream_handler.stream.assert_not_called()


@pytest.mark.asyncio
async def test_build_failure_emits_error(tmp_path: Path):
    session = _make_session(tmp_path, vault_config=None)
    q: Queue[dict] = Queue(maxsize=64)

    with patch(
        "apps.gui.server.bridge.JarvisAgent.get_daily_note_instructions",
        return_value="DAILY",
    ):
        await run_turn(session, "/daily-summary", q)

    events = _drain(q)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "user"
    assert "error" in kinds
    assert "turn_finished" in kinds
    # vault-not-configured path — stream was never invoked
    session.components.stream_handler.stream.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_streams_and_writes_vault(tmp_path: Path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    build_result = DailySummaryRequest(
        messages=[{"role": "system", "content": "x"}, {"role": "user", "content": "y"}],
        note_path=Path("/vault/2026-04-18.md"),
        target_date=None,
    )

    write_result = SimpleNamespace(success=True, message="Appended to daily note")

    with (
        patch(
            "apps.gui.server.bridge.JarvisAgent.get_daily_note_instructions",
            return_value="DAILY",
        ),
        patch(
            "apps.gui.server.bridge.build_daily_summary_request",
            return_value=build_result,
        ),
        patch(
            "apps.gui.server.bridge.append_to_daily_note",
            return_value=write_result,
        ) as mock_append,
    ):
        await run_turn(session, "/daily-summary", q)

    events = _drain(q)
    kinds = [e["type"] for e in events]
    assert "user" in kinds
    assert "thinking_start" in kinds
    assert "thinking_end" in kinds
    assert "text" in kinds
    # system event from write_result.message
    system_events = [e for e in events if e["type"] == "system"]
    assert any("Appended to daily note" in (e.get("text") or "") for e in system_events)
    assert "totals" in kinds
    assert kinds[-1] == "turn_finished"

    # Vault write called with (text, vault_config, confirmation, None)
    mock_append.assert_called_once()
    args = mock_append.call_args.args
    assert args[0] == "summary text"
    assert args[3] is None  # target_date

    # Logger got the bare command, not the payload.
    first_add = session.components.logger.add_message.call_args_list[0]
    assert first_add.args[:2] == ("user", "/daily-summary")


@pytest.mark.asyncio
async def test_happy_path_passes_parsed_date(tmp_path: Path):
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    build_result = DailySummaryRequest(
        messages=[{"role": "system", "content": "x"}],
        note_path=Path("/vault/2026-04-18.md"),
        target_date="2026-04-18",
    )
    write_result = SimpleNamespace(success=True, message="ok")

    with (
        patch(
            "apps.gui.server.bridge.JarvisAgent.get_daily_note_instructions",
            return_value="DAILY",
        ),
        patch(
            "apps.gui.server.bridge.build_daily_summary_request",
            return_value=build_result,
        ) as mock_build,
        patch(
            "apps.gui.server.bridge.append_to_daily_note",
            return_value=write_result,
        ) as mock_append,
    ):
        await run_turn(session, "/daily-summary 2026-04-18", q)

    _, kwargs = mock_build.call_args
    assert kwargs["target_date"] == "2026-04-18"
    # append_to_daily_note(text, vault, conf, target_date) positional
    assert mock_append.call_args.args[3] == "2026-04-18"


@pytest.mark.asyncio
async def test_stream_exception_emits_error_and_turn_finished(tmp_path: Path):
    session = _make_session(tmp_path)
    session.components.stream_handler.stream.side_effect = RuntimeError("llm down")
    q: Queue[dict] = Queue(maxsize=64)

    build_result = DailySummaryRequest(
        messages=[{"role": "system", "content": "x"}],
        note_path=Path("/vault/x.md"),
        target_date=None,
    )

    with (
        patch(
            "apps.gui.server.bridge.JarvisAgent.get_daily_note_instructions",
            return_value="DAILY",
        ),
        patch(
            "apps.gui.server.bridge.build_daily_summary_request",
            return_value=build_result,
        ),
        patch(
            "apps.gui.server.bridge.append_to_daily_note",
        ) as mock_append,
    ):
        await run_turn(session, "/daily-summary", q)

    events = _drain(q)
    kinds = [e["type"] for e in events]
    assert "error" in kinds
    assert kinds[-1] == "turn_finished"
    mock_append.assert_not_called()


@pytest.mark.asyncio
async def test_max_tokens_capped_at_4096_during_stream(tmp_path: Path):
    """Verify the handler.max_tokens is 4096 while streaming and restored afterwards."""
    session = _make_session(tmp_path)
    handler = session.components.stream_handler
    handler.max_tokens = 2048  # prior value

    observed: dict[str, Any] = {}

    def _fake_stream(messages, print_chunks=False):
        observed["max_tokens_during"] = handler.max_tokens
        observed["on_chunk_during"] = handler.on_chunk
        return StreamResult(
            text="t",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            cost_usd=0.0,
            metrics=SimpleNamespace(ttft_ms=0, total_latency_ms=0),
            tool_messages=[],
        )

    handler.stream.side_effect = _fake_stream

    build_result = DailySummaryRequest(
        messages=[{"role": "system", "content": "x"}],
        note_path=Path("/vault/x.md"),
        target_date=None,
    )
    write_result = SimpleNamespace(success=True, message="ok")

    with (
        patch(
            "apps.gui.server.bridge.JarvisAgent.get_daily_note_instructions",
            return_value="DAILY",
        ),
        patch(
            "apps.gui.server.bridge.build_daily_summary_request",
            return_value=build_result,
        ),
        patch(
            "apps.gui.server.bridge.append_to_daily_note",
            return_value=write_result,
        ),
    ):
        await run_turn(session, "/daily-summary", Queue(maxsize=64))

    assert observed["max_tokens_during"] == 4096
    assert observed["on_chunk_during"] is None
    # Restored afterwards
    assert handler.max_tokens == 2048


@pytest.mark.asyncio
async def test_non_daily_summary_text_falls_through(tmp_path: Path):
    """Regular chat text must NOT take the daily-summary branch."""
    session = _make_session(tmp_path)
    q: Queue[dict] = Queue(maxsize=64)

    # active_agent.run is what run_turn falls through to. Make it a no-op-ish.
    session.components.active_agent.run.return_value = StreamResult(
        text="hi",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        cost_usd=0.0,
        metrics=SimpleNamespace(ttft_ms=0, total_latency_ms=0),
        tool_messages=[],
    )
    session.components.agent_registry = {}
    session.components.client = MagicMock()
    session.components.config = {"summarization": {"enabled": False}, "_paths": {"jarvis_dir": tmp_path}}

    with patch("apps.gui.server.bridge.build_daily_summary_request") as mock_build:
        await run_turn(session, "hello there", q)

    # Builder was never called — regular-chat path used.
    mock_build.assert_not_called()
    # active_agent.run WAS called.
    session.components.active_agent.run.assert_called_once()


def test_parse_daily_summary_command_branches():
    from packages.core.daily_summary import parse_daily_summary_command

    # re-exercise the branches here to lock the bridge's parser contract
    assert parse_daily_summary_command("/daily-summary") == (None, None)
    target, failure = parse_daily_summary_command("/daily-summary 2026-04-18")
    assert target == "2026-04-18" and failure is None
    _, failure = parse_daily_summary_command("/daily-summary bad")
    assert isinstance(failure, DailySummaryFailure)
    assert failure.error == DailySummaryError.INVALID_DATE
