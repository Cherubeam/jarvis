"""Scripts and importers take their default data paths from settings (HUB-03).

Each test points the script's PROJECT_ROOT at a tmp project whose
config/local.yaml moves paths.* elsewhere, then checks the path the script
actually used. Explicit flags keep their old meaning: the importers and the
backfill resolve a relative flag against the working directory, the analyze
scripts against the project root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import (
    analyze_context,
    analyze_costs,
    backfill_billed_usage,
    import_chatgpt,
    import_claude,
)


def _project(tmp_path: Path, local_yaml: str = "") -> Path:
    """A tmp project root with only a config/local.yaml (no default.yaml)."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "config" / "local.yaml").write_text(local_yaml, encoding="utf-8")
    return root


def _moved_paths(tmp_path: Path) -> tuple[Path, str]:
    """Absolute conversations dir outside the project — with a space, like the real target."""
    target = tmp_path / "03 Resources" / "JARVIS" / "data" / "conversations"
    return target, f'paths:\n  conversations_dir: "{target}"\n'


# ---------------------------------------------------------------------------
# Importers (import_claude / import_chatgpt)


class _ImportRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            total=0,
            imported=0,
            updated=0,
            skipped_filter=0,
            skipped_existing=0,
            skipped_archived=0,
            errors=0,
            error_details=[],
        )


@pytest.fixture(params=[import_claude, import_chatgpt], ids=["claude", "chatgpt"])
def importer(request: pytest.FixtureRequest) -> ModuleType:
    module: ModuleType = request.param
    return module


def test_importer_defaults_to_configured_conversations_dir(
    importer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, local_yaml = _moved_paths(tmp_path)
    monkeypatch.setattr(importer, "PROJECT_ROOT", _project(tmp_path, local_yaml))
    recorder = _ImportRecorder()
    monkeypatch.setattr(importer, "import_conversations", recorder)
    source = tmp_path / "conversations.json"
    source.write_text("[]", encoding="utf-8")

    assert importer.main([str(source), "--dry-run"]) == 0

    assert [c["target_dir"] for c in recorder.calls] == [target]


def test_importer_default_without_override_is_data_conversations(
    importer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr(importer, "PROJECT_ROOT", root)
    recorder = _ImportRecorder()
    monkeypatch.setattr(importer, "import_conversations", recorder)
    source = tmp_path / "conversations.json"
    source.write_text("[]", encoding="utf-8")

    assert importer.main([str(source), "--dry-run"]) == 0

    assert [c["target_dir"] for c in recorder.calls] == [root / "data" / "conversations"]


def test_importer_explicit_target_dir_wins(
    importer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, local_yaml = _moved_paths(tmp_path)
    monkeypatch.setattr(importer, "PROJECT_ROOT", _project(tmp_path, local_yaml))
    recorder = _ImportRecorder()
    monkeypatch.setattr(importer, "import_conversations", recorder)
    source = tmp_path / "conversations.json"
    source.write_text("[]", encoding="utf-8")

    assert importer.main([str(source), "--target-dir", "some/relative/dir"]) == 0

    # A relative flag is taken as given (cwd-relative), exactly as before.
    assert [c["target_dir"] for c in recorder.calls] == [Path("some/relative/dir")]


# ---------------------------------------------------------------------------
# backfill_billed_usage


def _backfill_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backfill_billed_usage, "collect_api_keys", lambda: {})
    monkeypatch.setattr(backfill_billed_usage, "get_api_key", lambda provider, keys: "test-key")
    monkeypatch.setattr(
        backfill_billed_usage,
        "reconcile_estimated_messages",
        lambda messages, api_key, deadline_s: (1, {"total_cost_usd": 0.25}),
    )


def _write_log(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps({"messages": []}), encoding="utf-8")


def test_backfill_defaults_to_configured_conversations_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target, local_yaml = _moved_paths(tmp_path)
    root = _project(tmp_path, local_yaml)
    monkeypatch.setattr(backfill_billed_usage, "PROJECT_ROOT", root)
    _backfill_stubs(monkeypatch)
    _write_log(target / "2026", "moved.json")
    _write_log(root / "data" / "conversations" / "2026", "in-repo.json")

    assert backfill_billed_usage.main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert out == (
        "moved.json: 1 message(s), cost +0.2500 USD\nWould update 1 message(s) in 1 file(s); cost +0.2500 USD\n"
    )


def test_backfill_explicit_dir_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target, local_yaml = _moved_paths(tmp_path)
    monkeypatch.setattr(backfill_billed_usage, "PROJECT_ROOT", _project(tmp_path, local_yaml))
    _backfill_stubs(monkeypatch)
    _write_log(target, "moved.json")
    explicit = tmp_path / "explicit"
    _write_log(explicit, "explicit.json")

    assert backfill_billed_usage.main(["--dry-run", "--dir", str(explicit)]) == 0

    assert capsys.readouterr().out.splitlines()[0] == "explicit.json: 1 message(s), cost +0.2500 USD"


# ---------------------------------------------------------------------------
# analyze_costs / analyze_context
#
# Both fail fast with the resolved conversations path when it does not exist,
# which makes the resolved path observable without real conversation data.


@pytest.fixture(params=[analyze_costs, analyze_context], ids=["costs", "context"])
def analyzer(request: pytest.FixtureRequest) -> ModuleType:
    module: ModuleType = request.param
    return module


def test_analyzer_defaults_to_configured_conversations_dir(
    analyzer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target, local_yaml = _moved_paths(tmp_path)
    monkeypatch.setattr(analyzer, "PROJECT_ROOT", _project(tmp_path, local_yaml))

    assert analyzer.main([]) == 1

    assert capsys.readouterr().out == f"Error: Conversations directory not found: {target}\n"


def test_analyzer_default_without_override_is_data_conversations(
    analyzer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr(analyzer, "PROJECT_ROOT", root)

    assert analyzer.main([]) == 1

    assert capsys.readouterr().out == f"Error: Conversations directory not found: {root / 'data' / 'conversations'}\n"


def test_analyzer_explicit_relative_dir_stays_project_relative(
    analyzer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _, local_yaml = _moved_paths(tmp_path)
    root = _project(tmp_path, local_yaml)
    monkeypatch.setattr(analyzer, "PROJECT_ROOT", root)

    assert analyzer.main(["--conversations-dir", "other/convs"]) == 1

    assert capsys.readouterr().out == f"Error: Conversations directory not found: {root / 'other' / 'convs'}\n"


def _one_conversation(directory: Path) -> None:
    directory.mkdir(parents=True)
    conversation = {
        "conversation_id": "c1",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    }
    (directory / "c1.json").write_text(json.dumps(conversation), encoding="utf-8")


def test_analyze_context_defaults_to_configured_context_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conversations = tmp_path / "moved" / "conversations"
    context = tmp_path / "moved" / "context"
    _one_conversation(conversations)
    context.mkdir()
    root = _project(tmp_path, f'paths:\n  conversations_dir: "{conversations}"\n  context_dir: "{context}"\n')
    monkeypatch.setattr(analyze_context, "PROJECT_ROOT", root)
    seen: list[Path | None] = []

    def _record(convs: list[dict[str, Any]], context_dir: Path | None) -> Any:
        seen.append(context_dir)
        raise SystemExit(0)

    monkeypatch.setattr(analyze_context, "analyze_context_utilization", _record)

    with pytest.raises(SystemExit):
        analyze_context.main([])

    assert seen == [context]


def test_analyze_context_explicit_context_dir_stays_project_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversations = tmp_path / "moved" / "conversations"
    _one_conversation(conversations)
    root = _project(tmp_path, f'paths:\n  conversations_dir: "{conversations}"\n')
    (root / "ctx").mkdir()
    monkeypatch.setattr(analyze_context, "PROJECT_ROOT", root)
    seen: list[Path | None] = []

    def _record(convs: list[dict[str, Any]], context_dir: Path | None) -> Any:
        seen.append(context_dir)
        raise SystemExit(0)

    monkeypatch.setattr(analyze_context, "analyze_context_utilization", _record)

    with pytest.raises(SystemExit):
        analyze_context.main(["--context-dir", "ctx"])

    assert seen == [root / "ctx"]
