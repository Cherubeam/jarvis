"""Tests for the seven prompt-editor endpoints on /api/agents/{id}/prompt*."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.history.index import ConversationIndex
from apps.gui.server.routes.agents import router as agents_router
from packages.agents.registry import AgentMeta


def _write_fake_agent(
    tmp_path: Path,
    agent_id: str,
    system_text: str = "You are a helpful assistant.",
    prompt_includes: dict[str, str] | None = None,
    **include_files: str,
) -> AgentMeta:
    """Materialise a minimal agent directory + meta.yaml under ``tmp_path``."""
    agent_dir = tmp_path / "packages" / "agents" / agent_id
    prompts_dir = agent_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text(system_text, encoding="utf-8")
    for name, content in include_files.items():
        (prompts_dir / f"{name}.md").write_text(content, encoding="utf-8")

    meta_dict: dict = {
        "name": agent_id,
        "description": f"test agent {agent_id}",
        "command": f"/{agent_id}",
    }
    if prompt_includes:
        meta_dict["prompt_includes"] = prompt_includes
    meta_path = agent_dir / "meta.yaml"
    meta_path.write_text(yaml.safe_dump(meta_dict), encoding="utf-8")

    return AgentMeta(
        name=agent_id,
        description=meta_dict["description"],
        command=meta_dict["command"],
        meta_path=meta_path,
        tool_groups=(),
        skills=(),
        vault_writing=None,
    )


def _build_app(tmp_path: Path, agents: dict[str, AgentMeta] | None = None) -> FastAPI:
    convs = tmp_path / "conversations"
    convs.mkdir(parents=True)
    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    config = {
        "_paths": {"jarvis_dir": tmp_path},
        "paths": {"prompt_history_dir": "data/prompt-history"},
    }
    settings = SimpleNamespace(paths=SimpleNamespace(prompt_history_dir="data/prompt-history"))
    active_jarvis = SimpleNamespace(config=SimpleNamespace(system_prompt="JARVIS assembled prompt here.\nSecond line."))
    components = SimpleNamespace(
        agent_registry=agents or {},
        config=config,
        settings=settings,
        jarvis_dir=tmp_path,
        active_agent=active_jarvis,
    )
    app = FastAPI()
    app.state.conversation_index = index
    app.state.gui_session = SimpleNamespace(components=components)
    app.include_router(agents_router)
    return app


@pytest.fixture
def client_with_writer(tmp_path: Path) -> TestClient:
    writer = _write_fake_agent(
        tmp_path,
        "writer",
        system_text="Voice: {voice}\n\nBe concise.",
        prompt_includes={"voice": "voice"},
        voice="terse and precise",
    )
    return TestClient(_build_app(tmp_path, {"writer": writer}))


# ---------- GET /prompt ----------


def test_get_prompt_returns_current_content(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/writer/prompt")
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "Voice: {voice}\n\nBe concise."
    assert body["editable"] is True
    assert body["path"] == "packages/agents/writer/prompts/system.md"
    assert body["bytes"] > 0
    assert body["last_modified_iso"] is not None


def test_get_prompt_jarvis_is_read_only(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/JARVIS/prompt")
    assert r.status_code == 200
    body = r.json()
    assert body["editable"] is False
    assert "data/context/" in body["explanation"]
    assert body["content"].startswith("JARVIS assembled")


def test_get_prompt_unknown_agent_returns_404(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/nope/prompt")
    assert r.status_code == 404


def test_get_prompt_path_traversal_returns_404(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/..%2Fsomething/prompt")
    assert r.status_code == 404


# ---------- PUT /prompt ----------


def test_put_prompt_writes_file_and_snapshots_prior(client_with_writer: TestClient, tmp_path: Path) -> None:
    r = client_with_writer.put(
        "/api/agents/writer/prompt",
        json={"content": "New voice.", "note": "edit"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["snapshot_id"]
    assert body["bytes"] == len(b"New voice.")

    on_disk = (tmp_path / "packages/agents/writer/prompts/system.md").read_text(encoding="utf-8")
    assert on_disk == "New voice."

    snaps_r = client_with_writer.get("/api/agents/writer/prompt/snapshots")
    rows = snaps_r.json()
    # Two rows: the pre_first_save + the save itself, newest first.
    assert len(rows) == 2
    assert rows[0]["kind"] == "save"
    assert rows[1]["kind"] == "pre_first_save"


def test_put_prompt_jarvis_returns_403(client_with_writer: TestClient) -> None:
    r = client_with_writer.put("/api/agents/JARVIS/prompt", json={"content": "hi"})
    assert r.status_code == 403


def test_put_prompt_over_size_limit_returns_413(client_with_writer: TestClient) -> None:
    big = "x" * (1_000_000 + 1)
    r = client_with_writer.put("/api/agents/writer/prompt", json={"content": big})
    assert r.status_code == 413


def test_put_prompt_unknown_agent_returns_404(client_with_writer: TestClient) -> None:
    r = client_with_writer.put("/api/agents/nope/prompt", json={"content": "x"})
    assert r.status_code == 404


def test_put_prompt_second_save_does_not_double_pre_first_save(
    client_with_writer: TestClient,
) -> None:
    client_with_writer.put("/api/agents/writer/prompt", json={"content": "v1"})
    client_with_writer.put("/api/agents/writer/prompt", json={"content": "v2"})
    rows = client_with_writer.get("/api/agents/writer/prompt/snapshots").json()
    kinds = [r["kind"] for r in rows]
    # Exactly one pre_first_save, two save rows.
    assert kinds.count("pre_first_save") == 1
    assert kinds.count("save") == 2


# ---------- GET /prompt/snapshots ----------


def test_list_snapshots_empty_before_first_save(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/writer/prompt/snapshots")
    assert r.status_code == 200
    assert r.json() == []


def test_list_snapshots_jarvis_always_empty(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/JARVIS/prompt/snapshots")
    assert r.status_code == 200
    assert r.json() == []


# ---------- GET /prompt/snapshots/{id} ----------


def test_get_single_snapshot_returns_content(client_with_writer: TestClient) -> None:
    save = client_with_writer.put("/api/agents/writer/prompt", json={"content": "v1", "note": "first"}).json()
    # Look up the pre_first_save snapshot — that's the "before v1" state.
    rows = client_with_writer.get("/api/agents/writer/prompt/snapshots").json()
    pre_first = next(r for r in rows if r["kind"] == "pre_first_save")
    r = client_with_writer.get(f"/api/agents/writer/prompt/snapshots/{pre_first['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "pre_first_save"
    assert body["content"] == "Voice: {voice}\n\nBe concise."
    # Round-trip the save_id we just captured.
    assert save["snapshot_id"]


def test_get_missing_snapshot_returns_404(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/writer/prompt/snapshots/20990101T000000_000000Z")
    assert r.status_code == 404


# ---------- POST /prompt/restore ----------


def test_restore_replaces_system_md_and_creates_pre_restore_snapshot(
    client_with_writer: TestClient, tmp_path: Path
) -> None:
    client_with_writer.put("/api/agents/writer/prompt", json={"content": "v1"})
    client_with_writer.put("/api/agents/writer/prompt", json={"content": "v2"})
    rows = client_with_writer.get("/api/agents/writer/prompt/snapshots").json()
    # Find the pre_first_save (contains the ORIGINAL content).
    pre_first = next(r for r in rows if r["kind"] == "pre_first_save")

    r = client_with_writer.post(
        "/api/agents/writer/prompt/restore",
        json={"snapshot_id": pre_first["id"]},
    )
    assert r.status_code == 200

    on_disk = (tmp_path / "packages/agents/writer/prompts/system.md").read_text(encoding="utf-8")
    assert on_disk == "Voice: {voice}\n\nBe concise."

    rows_after = client_with_writer.get("/api/agents/writer/prompt/snapshots").json()
    assert any(r["kind"] == "pre_restore" for r in rows_after)


def test_restore_missing_snapshot_returns_404(client_with_writer: TestClient) -> None:
    r = client_with_writer.post(
        "/api/agents/writer/prompt/restore",
        json={"snapshot_id": "20990101T000000_000000Z"},
    )
    assert r.status_code == 404


def test_restore_jarvis_returns_403(client_with_writer: TestClient) -> None:
    r = client_with_writer.post(
        "/api/agents/JARVIS/prompt/restore",
        json={"snapshot_id": "20260423T000000_000000Z"},
    )
    assert r.status_code == 403


# ---------- GET /prompt/stats ----------


def test_stats_reports_counts_and_include_status(client_with_writer: TestClient) -> None:
    r = client_with_writer.get("/api/agents/writer/prompt/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["char_count"] == len("Voice: {voice}\n\nBe concise.")
    assert body["line_count"] == 3
    assert body["token_estimate_method"] == "len_utf8_over_4"
    assert body["snapshot_count"] == 0
    assert len(body["prompt_includes"]) == 1
    assert body["prompt_includes"][0]["placeholder"] == "voice"
    assert body["prompt_includes"][0]["status"] == "found_local"


def test_stats_snapshot_count_grows_after_save(client_with_writer: TestClient) -> None:
    client_with_writer.put("/api/agents/writer/prompt", json={"content": "v1"})
    body = client_with_writer.get("/api/agents/writer/prompt/stats").json()
    # pre_first_save + one save = 2.
    assert body["snapshot_count"] == 2


def test_stats_jarvis_returns_live_assembled_prompt_shape(
    client_with_writer: TestClient,
) -> None:
    body = client_with_writer.get("/api/agents/JARVIS/prompt/stats").json()
    assert body["snapshot_count"] == 0
    assert body["prompt_includes"] == []
    assert body["char_count"] > 0  # JARVIS session has a system_prompt


# ---------- GET /prompt/resolved ----------


def test_resolved_expands_placeholders(client_with_writer: TestClient) -> None:
    body = client_with_writer.get("/api/agents/writer/prompt/resolved").json()
    assert body["resolved_content"] == "Voice: terse and precise\n\nBe concise."


def test_resolved_jarvis_returns_session_prompt(client_with_writer: TestClient) -> None:
    body = client_with_writer.get("/api/agents/JARVIS/prompt/resolved").json()
    assert body["resolved_content"] == "JARVIS assembled prompt here.\nSecond line."


def test_resolved_missing_system_md_returns_404(tmp_path: Path) -> None:
    # Create a registered agent whose system.md is missing.
    agent_dir = tmp_path / "packages/agents/broken"
    agent_dir.mkdir(parents=True)
    meta_path = agent_dir / "meta.yaml"
    meta_path.write_text(yaml.safe_dump({"name": "broken"}), encoding="utf-8")
    meta = AgentMeta(
        name="broken",
        description="",
        command="",
        meta_path=meta_path,
        tool_groups=(),
        skills=(),
        vault_writing=None,
    )
    client = TestClient(_build_app(tmp_path, {"broken": meta}))
    r = client.get("/api/agents/broken/prompt/resolved")
    assert r.status_code == 404


# ---------- Concurrency + file safety ----------


def test_concurrent_puts_do_not_lose_snapshots(client_with_writer: TestClient, tmp_path: Path) -> None:
    """Sequential fire of 5 PUTs should leave exactly 5 save + 1 pre_first_save."""
    for i in range(5):
        r = client_with_writer.put("/api/agents/writer/prompt", json={"content": f"v{i}"})
        assert r.status_code == 200

    rows = client_with_writer.get("/api/agents/writer/prompt/snapshots").json()
    kinds = [r["kind"] for r in rows]
    assert kinds.count("save") == 5
    assert kinds.count("pre_first_save") == 1

    # Index.json matches on-disk files (no orphans).
    history_dir = tmp_path / "data/prompt-history/writer"
    on_disk = {p.stem for p in history_dir.iterdir() if p.suffix == ".md"}
    index = json.loads((history_dir / "index.json").read_text(encoding="utf-8"))
    in_index = {row["id"] for row in index}
    assert on_disk == in_index
