"""Tests for apps.gui.main — the jarvis-gui entry point wiring.

Only the settings → auth wiring is covered here; uvicorn.run is stubbed so no
server starts.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from apps.gui import main as gui_main
from apps.gui.server.auth import TOKEN_ENV_VAR, TokenRedactingFilter


@pytest.fixture
def stub_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, object]]]:
    calls: list[dict[str, object]] = []

    def _run(app: object, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(gui_main.uvicorn, "run", _run)
    yield calls
    # main() attaches a redacting filter to a global logger; don't leak it.
    access = logging.getLogger("uvicorn.access")
    for f in [f for f in access.filters if isinstance(f, TokenRedactingFilter)]:
        access.removeFilter(f)


def test_main_reads_the_token_from_the_configured_token_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_server: list[dict[str, object]],
) -> None:
    """gui.token_file from config/local.yaml decides where the token lives."""
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    project_root = tmp_path / "repo"
    (project_root / "config").mkdir(parents=True)
    token_path = tmp_path / "03 Resources" / "JARVIS" / "data" / ".gui_token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("configured-token\n", encoding="utf-8")
    (project_root / "config" / "local.yaml").write_text(f'gui:\n  token_file: "{token_path}"\n', encoding="utf-8")
    monkeypatch.setattr(gui_main, "get_project_root", lambda: project_root)

    assert gui_main.main(["--no-browser"]) == 0

    out = capsys.readouterr().out
    assert "Sign in:  http://127.0.0.1:8123/auth?token=configured-token\n" in out
    assert stub_server == [{"host": "127.0.0.1", "port": 8123, "log_level": "info"}]
    assert not (project_root / "data").exists()
