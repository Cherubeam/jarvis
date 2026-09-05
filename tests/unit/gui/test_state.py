"""Tests for apps.gui.server.state — GuiSession, build_gui_session, and the
deferred confirmation handler.

build_session() is always stubbed: the real one loads config, builds the agent
registry and spawns MCP subprocesses.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from apps.gui.server import state as state_module
from apps.gui.server.state import GuiSession, _DeferredConfirmationHandler, build_gui_session


def _components(
    *,
    model_id: str | None = "anthropic/claude-sonnet-4.5",
    vault_config: Any = None,
    conversations_dir: Path | None = None,
    agent_count: int = 2,
) -> SimpleNamespace:
    return SimpleNamespace(
        conversation_id="conv_abc123",
        model_id=model_id,
        provider="anthropic",
        conversations_dir=conversations_dir or Path("/tmp/conversations"),
        vault_config=vault_config,
        agent_registry={f"agent_{i}": object() for i in range(agent_count)},
        logger=SimpleNamespace(session_start=datetime(2026, 4, 23, 12, 30, 45)),
    )


def _session(**kwargs: Any) -> GuiSession:
    return GuiSession(components=_components(**kwargs), started_at="12:30")


# ---------------------------------------------------------------------------
# session_meta — exact shape, since the client and /api/conversations depend on it


def test_session_meta_exact_shape() -> None:
    meta = _session(conversations_dir=Path("/data/conversations")).session_meta()

    assert meta == {
        "id": "conv_abc123",
        "file_id": "2026-04-23_12-30-45",
        "model": "anthropic/claude-sonnet-4.5",
        "model_short": "claude-sonnet-4.5",
        "provider": "anthropic",
        "conversation_path": "/data/conversations/2026/2026-04-23_12-30-45.json",
        "vault": None,
        "started_at": "12:30",
        "agents_count": 2,
    }


def test_file_id_uses_the_logger_session_start_not_the_conversation_id() -> None:
    """The path is derived from logger.session_start — the docstring records
    that an earlier version derived it from conversation_id and was wrong."""
    session = _session()
    session.components.logger.session_start = datetime(2025, 12, 31, 23, 59, 59)

    meta = session.session_meta()
    assert meta["file_id"] == "2025-12-31_23-59-59"
    assert meta["conversation_path"].endswith("/2025/2025-12-31_23-59-59.json")
    assert "conv_abc123" not in meta["conversation_path"]


def test_conversation_path_is_bucketed_by_year() -> None:
    session = _session(conversations_dir=Path("/data/conversations"))
    session.components.logger.session_start = datetime(2027, 1, 1, 0, 0, 0)
    assert session.session_meta()["conversation_path"] == "/data/conversations/2027/2027-01-01_00-00-00.json"


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("anthropic/claude-sonnet-4.5", "claude-sonnet-4.5"),
        ("openrouter/qwen/qwen3.5-flash", "qwen3.5-flash"),  # last segment wins
        ("local-model", "local-model"),  # no slash — unchanged
        (None, None),  # falsy — returned as-is, not "None"
        ("", ""),
    ],
)
def test_model_short(model_id: str | None, expected: str | None) -> None:
    assert _session(model_id=model_id).session_meta()["model_short"] == expected


def test_vault_is_none_without_a_vault_config() -> None:
    assert _session(vault_config=None).session_meta()["vault"] is None


def test_vault_is_none_for_an_empty_vault_path() -> None:
    """An empty path must normalise to None, not to the empty string."""
    config = SimpleNamespace(vault_path="")
    assert _session(vault_config=config).session_meta()["vault"] is None


def test_vault_is_the_stringified_path() -> None:
    config = SimpleNamespace(vault_path=Path("/Users/me/vault"))
    assert _session(vault_config=config).session_meta()["vault"] == "/Users/me/vault"


def test_agents_count_tracks_the_registry() -> None:
    assert _session(agent_count=7).session_meta()["agents_count"] == 7


# ---------------------------------------------------------------------------
# GuiSession defaults


def test_gui_session_defaults() -> None:
    session = _session()
    assert session.queue is None
    assert session.confirmation is None
    assert session.cancel_event is None
    assert session.last_agent_session is None
    assert session.in_flight is False
    assert session.conversation_index is None


def test_in_flight_locks_are_per_instance() -> None:
    assert _session().in_flight_lock is not _session().in_flight_lock


# ---------------------------------------------------------------------------
# _DeferredConfirmationHandler


def test_unbound_present_diff_warns_and_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    handler = _DeferredConfirmationHandler()
    with caplog.at_level(logging.WARNING, logger="apps.gui.server.state"):
        handler.present_diff(MagicMock())
    assert any("no bound GUI handler" in r.getMessage() for r in caplog.records)


def test_unbound_get_confirmation_rejects() -> None:
    """No client to ask means the write must be refused, never assumed."""
    assert _DeferredConfirmationHandler().get_confirmation() is False


def test_bound_handler_receives_present_diff() -> None:
    handler = _DeferredConfirmationHandler()
    target = MagicMock()
    diff = MagicMock()

    handler.bind(target)
    handler.present_diff(diff)

    target.present_diff.assert_called_once_with(diff)


def test_bound_handler_receives_the_prompt_and_returns_its_verdict() -> None:
    handler = _DeferredConfirmationHandler()
    target = MagicMock()
    target.get_confirmation.return_value = True

    handler.bind(target)
    assert handler.get_confirmation("Write this note?") is True
    target.get_confirmation.assert_called_once_with("Write this note?")


def test_bound_handler_forwards_the_default_prompt() -> None:
    handler = _DeferredConfirmationHandler()
    target = MagicMock()
    target.get_confirmation.return_value = False

    handler.bind(target)
    assert handler.get_confirmation() is False
    target.get_confirmation.assert_called_once_with("Apply this change?")


def test_unbind_restores_the_rejecting_behaviour() -> None:
    handler = _DeferredConfirmationHandler()
    target = MagicMock()
    target.get_confirmation.return_value = True

    handler.bind(target)
    handler.unbind()

    assert handler.get_confirmation() is False
    target.get_confirmation.assert_not_called()


def test_bind_replaces_the_previous_target() -> None:
    handler = _DeferredConfirmationHandler()
    first, second = MagicMock(), MagicMock()
    second.get_confirmation.return_value = True

    handler.bind(first)
    handler.bind(second)
    handler.get_confirmation()

    first.get_confirmation.assert_not_called()
    second.get_confirmation.assert_called_once()


# ---------------------------------------------------------------------------
# build_gui_session


@freeze_time("2026-04-23 14:05:00")
def test_build_gui_session_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = object()
    components = SimpleNamespace()
    captured: dict[str, Any] = {}

    def fake_build_session(args: Any, cfg: Any, handler: Any, **kwargs: Any) -> SimpleNamespace:
        captured["args"] = args
        captured["settings"] = cfg
        captured["handler"] = handler
        captured["kwargs"] = kwargs
        return components

    monkeypatch.setattr(state_module, "load_config", lambda: settings)
    monkeypatch.setattr(state_module, "build_session", fake_build_session)

    session = build_gui_session()

    assert captured["settings"] is settings
    assert captured["args"].model is None
    assert captured["args"].agent is None
    assert captured["args"].auto_confirm is False
    assert captured["kwargs"] == {
        "on_tool_call": None,
        "client_label": "gui",
        "auto_confirm": False,
    }
    assert session.components is components
    # started_at comes from time.strftime("%H:%M"). Compare against the same
    # frozen clock rather than a hardcoded literal: freezegun freezes UTC while
    # the source formats local time, so a literal would be offset-dependent.
    # The format string here is the test's own, so a "%M:%H" mutant still dies.
    assert session.started_at == time.strftime("%H:%M")
    assert len(session.started_at) == 5
    assert session.started_at[2] == ":"


def test_build_gui_session_attaches_the_deferred_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bridge rebinds this per turn — if it isn't attached, every vault
    write is silently rejected."""
    handlers: list[Any] = []

    def fake_build_session(args: Any, cfg: Any, handler: Any, **kwargs: Any) -> SimpleNamespace:
        handlers.append(handler)
        return SimpleNamespace()

    monkeypatch.setattr(state_module, "load_config", lambda: object())
    monkeypatch.setattr(state_module, "build_session", fake_build_session)

    session = build_gui_session()

    assert isinstance(handlers[0], _DeferredConfirmationHandler)
    assert session.components._deferred_handler is handlers[0]


def test_build_gui_session_does_not_prebind_a_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh session must reject writes until a turn binds a real handler."""
    monkeypatch.setattr(state_module, "load_config", lambda: object())
    monkeypatch.setattr(
        state_module,
        "build_session",
        lambda args, cfg, handler, **kwargs: SimpleNamespace(),
    )

    session = build_gui_session()
    assert session.components._deferred_handler.get_confirmation() is False
    assert session.confirmation is None
