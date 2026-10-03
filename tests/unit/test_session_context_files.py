"""HUB-03: build_session reads context files and tasks from settings, and snapshots them."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from apps.cli import session_factory
from apps.cli.session_factory import _snapshot_context_files, _snapshot_path, build_session
from packages.core.context_builder import build_system_prompt_with_metadata
from packages.core.memory import hash_content
from packages.core.settings import ContextFilesSettings, PathsSettings, Settings
from packages.integrations.things3.task_sync import Task

VAULT_FILES = ContextFilesSettings(
    soul="JARVIS Soul.md",
    personal="Memory/Personal Context.md",
    professional="Memory/Professional Context.md",
    preferences="Memory/Preferences.md",
    focus="Memory/Current Focus.md",
    reading="Memory/Reading Profile.md",
)


class _StopBuildError(Exception):
    """Raised by the patched LLMClient so build_session stops right after the prompt is built."""


@pytest.mark.unit
class TestBuildSessionContextPaths:
    def _build(self, settings: Settings) -> list[str]:
        """Run build_session up to the LLM client; return the system prompts it built."""
        prompts: list[str] = []

        def record(*args: Any) -> Any:
            result = build_system_prompt_with_metadata(*args)
            prompts.append(result[0])
            return result

        with (
            patch.object(session_factory, "collect_api_keys", return_value={"openrouter": "test-key"}),
            patch.object(session_factory, "get_api_key", return_value="test-key"),
            patch.object(session_factory, "build_system_prompt_with_metadata", side_effect=record),
            patch.object(session_factory, "LLMClient", side_effect=_StopBuildError),
            patch(
                "packages.integrations.things3.task_sync.fetch_tasks",
                return_value={"inbox": [], "today": [Task(title="Fresh task")], "upcoming": []},
            ),
            pytest.raises(_StopBuildError),
        ):
            build_session(SimpleNamespace(model=None, agent=None), settings, confirmation_handler=None)  # type: ignore[arg-type]
        return prompts

    def test_tasks_synced_to_and_read_from_tasks_file(self, tmp_path: Path) -> None:
        context_dir = tmp_path / "vault" / "07 – Personal System" / "JARVIS"
        (context_dir / "Memory").mkdir(parents=True)
        (context_dir / "JARVIS Soul.md").write_text("---\nupdated: 2026-10-03\n---\nSOUL\n")
        (context_dir / "Memory" / "Current Focus.md").write_text("FOCUS\n")
        (context_dir / "tasks.md").write_text("STALE TASKS\n")
        tasks_file = tmp_path / "Library" / "Caches" / "JARVIS" / "tasks.md"
        settings = Settings(
            paths=PathsSettings(context_dir=str(context_dir), context_files=VAULT_FILES, tasks_file=str(tasks_file))
        )
        settings.jarvis_dir = tmp_path / "repo"

        prompts = self._build(settings)

        assert "Fresh task" in tasks_file.read_text()
        assert (context_dir / "tasks.md").read_text() == "STALE TASKS\n"
        assert len(prompts) == 1
        assert prompts[0].startswith("SOUL\n\n## Current focus\n\nFOCUS\n\n\n---\n\n## Their tasks\n\n")
        assert "Fresh task" in prompts[0]
        assert "STALE" not in prompts[0]
        assert "updated:" not in prompts[0]

    def test_default_tasks_file_is_joined_onto_the_repo_root(self, tmp_path: Path) -> None:
        settings = Settings()
        settings.jarvis_dir = tmp_path
        (tmp_path / "data" / "context").mkdir(parents=True)
        (tmp_path / "data" / "context" / "soul.md").write_text("SOUL\n")

        prompts = self._build(settings)

        assert "Fresh task" in (tmp_path / "data" / "context" / "tasks.md").read_text()
        assert prompts[0].startswith("SOUL\n\n## Their tasks\n\n# Tasks from Things 3")


@pytest.mark.unit
class TestSnapshotContextFiles:
    def test_snapshot_path_relative_inside_repo_absolute_outside(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        assert _snapshot_path(repo / "data" / "context" / "soul.md", repo) == "data/context/soul.md"
        outside = tmp_path / "vault" / "JARVIS Soul.md"
        assert _snapshot_path(outside, repo) == str(outside)

    def test_records_configured_files_in_prompt_order_only(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        context_dir = tmp_path / "vault" / "JARVIS"
        (context_dir / "Memory").mkdir(parents=True)
        (context_dir / "Memory" / "Reading Profile.md").write_text("READING\n")
        (context_dir / "JARVIS Soul.md").write_text("SOUL\n")
        (context_dir / "Unrelated Note.md").write_text("not loaded\n")
        (context_dir / "Archive").mkdir()
        tasks_file = tmp_path / "cache" / "tasks.md"
        tasks_file.parent.mkdir()
        tasks_file.write_text("TASKS\n")

        entries = _snapshot_context_files(repo, context_dir, VAULT_FILES, tasks_file)

        assert entries == [
            {
                "path": str(context_dir / "JARVIS Soul.md"),
                "hash": f"sha256:{hash_content('SOUL\n')}",
                "size_bytes": 5,
                "approx_tokens": 1,
            },
            {
                "path": str(tasks_file),
                "hash": f"sha256:{hash_content('TASKS\n')}",
                "size_bytes": 6,
                "approx_tokens": 1,
            },
            {
                "path": str(context_dir / "Memory" / "Reading Profile.md"),
                "hash": f"sha256:{hash_content('READING\n')}",
                "size_bytes": 8,
                "approx_tokens": 2,
            },
        ]

    def test_default_layout_keeps_project_relative_paths(self, tmp_path: Path) -> None:
        context_dir = tmp_path / "data" / "context"
        context_dir.mkdir(parents=True)
        (context_dir / "soul.md").write_text("SOUL\n")
        (context_dir / "tasks.md").write_text("TASKS\n")

        entries = _snapshot_context_files(tmp_path, context_dir, ContextFilesSettings(), context_dir / "tasks.md")

        assert [e["path"] for e in entries] == ["data/context/soul.md", "data/context/tasks.md"]

    def test_projects_dir_recorded_with_active_flag(self, tmp_path: Path) -> None:
        context_dir = tmp_path / "data" / "context"
        (context_dir / "projects").mkdir(parents=True)
        content = "---\nactive: false\nsummary: x\n---\nBody\n"
        (context_dir / "projects" / "alpha.md").write_text(content)
        (context_dir / "projects" / "beta.md").write_text("No frontmatter\n")

        entries = _snapshot_context_files(tmp_path, context_dir, ContextFilesSettings(), tmp_path / "tasks.md")

        assert entries == [
            {
                "path": "data/context/projects/alpha.md",
                "hash": f"sha256:{hash_content(content)}",
                "size_bytes": len(content),
                "approx_tokens": len(content) // 4,
                "active": False,
                "frontmatter": {"active": False, "summary": "x"},
            },
            {
                "path": "data/context/projects/beta.md",
                "hash": f"sha256:{hash_content('No frontmatter\n')}",
                "size_bytes": 15,
                "approx_tokens": 3,
                "active": True,
            },
        ]

    def test_missing_context_dir_and_projects_dir_give_empty_snapshot(self, tmp_path: Path) -> None:
        entries = _snapshot_context_files(tmp_path, tmp_path / "nope", ContextFilesSettings(), tmp_path / "t.md")

        assert entries == []
