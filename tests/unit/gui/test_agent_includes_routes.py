"""Tests for /api/agents/{id}/includes* — Phase 6 follow-up."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.history.index import ConversationIndex
from apps.gui.server.routes.agent_includes import router as includes_router
from apps.gui.server.routes.agents import router as agents_router
from packages.agents.registry import AgentMeta


def _make_meta(
    tmp_path: Path,
    agent_id: str,
    *,
    prompt_includes: dict[str, str] | None = None,
    local_includes: dict[str, str] | None = None,
    local_examples: dict[str, str] | None = None,
) -> AgentMeta:
    """Materialise an agent dir with optional local include files / examples."""
    agent_dir = tmp_path / "packages" / "agents" / agent_id
    prompts_dir = agent_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "system.md").write_text("system body", encoding="utf-8")

    for name, content in (local_includes or {}).items():
        (prompts_dir / f"{name}.md").write_text(content, encoding="utf-8")
    for name, content in (local_examples or {}).items():
        (prompts_dir / f"{name}.md.example").write_text(content, encoding="utf-8")

    meta_dict: dict = {"name": agent_id, "description": agent_id, "command": f"/{agent_id}"}
    if prompt_includes:
        meta_dict["prompt_includes"] = prompt_includes
    meta_path = agent_dir / "meta.yaml"
    meta_path.write_text(yaml.safe_dump(meta_dict), encoding="utf-8")

    return AgentMeta(
        name=agent_id,
        description=agent_id,
        command=f"/{agent_id}",
        meta_path=meta_path,
        tool_groups=(),
        skills=(),
        vault_writing=None,
    )


def _make_shared(tmp_path: Path, **files: str) -> None:
    shared = tmp_path / "packages" / "agents" / "_shared" / "prompts"
    shared.mkdir(parents=True)
    for name, content in files.items():
        # Allow ".example" suffix via "voice_profile_example": pass with explicit ext.
        suffix = ".md" if not name.endswith("__example") else ".md.example"
        base = name.replace("__example", "")
        (shared / f"{base}{suffix}").write_text(content, encoding="utf-8")


def _build_app(tmp_path: Path, agents: dict[str, AgentMeta]) -> FastAPI:
    convs = tmp_path / "conversations"
    convs.mkdir(parents=True)
    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    settings = SimpleNamespace(paths=SimpleNamespace(prompt_history_dir="data/prompt-history"))
    components = SimpleNamespace(
        agent_registry=agents,
        config={},
        settings=settings,
        jarvis_dir=tmp_path,
        active_agent=None,
    )
    app = FastAPI()
    app.state.conversation_index = index
    app.state.gui_session = SimpleNamespace(components=components)
    app.include_router(agents_router)
    app.include_router(includes_router)
    return app


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture
def writer_local(tmp_path: Path) -> TestClient:
    """Writer with one local include (voice_profile → voice-profile.md present)."""
    meta = _make_meta(
        tmp_path,
        "writer",
        prompt_includes={"voice_profile": "voice-profile"},
        local_includes={"voice-profile": "terse and precise"},
    )
    return TestClient(_build_app(tmp_path, {"writer": meta}))


@pytest.fixture
def writer_shared(tmp_path: Path) -> TestClient:
    """Writer + content_reviewer both use a shared voice-profile.md."""
    _make_shared(tmp_path, voice_profile="shared voice text")
    writer = _make_meta(tmp_path, "writer", prompt_includes={"voice_profile": "voice_profile"})
    reviewer = _make_meta(tmp_path, "content_reviewer", prompt_includes={"voice_profile": "voice_profile"})
    return TestClient(_build_app(tmp_path, {"writer": writer, "content_reviewer": reviewer}))


@pytest.fixture
def writer_local_example(tmp_path: Path) -> TestClient:
    """Writer with a `.md.example` and no canonical local file (and no shared)."""
    meta = _make_meta(
        tmp_path,
        "writer",
        prompt_includes={"voice_profile": "voice-profile"},
        local_examples={"voice-profile": "starter voice"},
    )
    return TestClient(_build_app(tmp_path, {"writer": meta}))


@pytest.fixture
def writer_missing(tmp_path: Path) -> TestClient:
    """Writer declares an include with no file anywhere."""
    meta = _make_meta(
        tmp_path,
        "writer",
        prompt_includes={"voice_profile": "voice-profile"},
    )
    return TestClient(_build_app(tmp_path, {"writer": meta}))


# ---------------------------------------------------------------------------
# GET /includes (list)


def test_list_includes_returns_one_row_per_declared(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/writer/includes")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["placeholder"] == "voice_profile"
    assert row["filename"] == "voice-profile"
    assert row["status"] == "found_local"
    assert row["editable"] is True
    assert row["bytes"] == len("terse and precise")
    assert row["affects_agents"] == []


def test_list_includes_jarvis_returns_empty(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/JARVIS/includes")
    assert r.status_code == 200
    assert r.json() == []


def test_list_includes_no_includes_returns_empty(tmp_path: Path) -> None:
    meta = _make_meta(tmp_path, "simplifier")  # no prompt_includes
    client = TestClient(_build_app(tmp_path, {"simplifier": meta}))
    r = client.get("/api/agents/simplifier/includes")
    assert r.status_code == 200
    assert r.json() == []


def test_list_includes_unknown_agent_404(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/nope/includes")
    assert r.status_code == 404


def test_list_includes_shared_lists_other_affected_agents(writer_shared: TestClient) -> None:
    rows = writer_shared.get("/api/agents/writer/includes").json()
    assert rows[0]["status"] == "found_shared"
    assert rows[0]["affects_agents"] == ["content_reviewer"]


def test_list_includes_shared_excludes_agent_with_local_override(tmp_path: Path) -> None:
    """An agent with its OWN voice_profile.md must not be listed as affected."""
    _make_shared(tmp_path, voice_profile="shared")
    writer = _make_meta(tmp_path, "writer", prompt_includes={"vp": "voice_profile"})
    # content_reviewer has its own local override → resolves found_local → not affected.
    reviewer = _make_meta(
        tmp_path,
        "content_reviewer",
        prompt_includes={"vp": "voice_profile"},
        local_includes={"voice_profile": "local override"},
    )
    client = TestClient(_build_app(tmp_path, {"writer": writer, "content_reviewer": reviewer}))
    rows = client.get("/api/agents/writer/includes").json()
    assert rows[0]["affects_agents"] == []


# ---------------------------------------------------------------------------
# GET /includes/{placeholder}


def test_get_include_returns_content(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/writer/includes/voice_profile")
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "terse and precise"
    assert body["status"] == "found_local"
    assert body["editable"] is True


def test_get_include_unknown_placeholder_404(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/writer/includes/not_a_real_placeholder")
    assert r.status_code == 404


def test_get_include_invalid_placeholder_404(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/writer/includes/has-a-dash")
    assert r.status_code == 404


def test_get_include_jarvis_404(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/JARVIS/includes/voice_profile")
    assert r.status_code == 404


def test_get_include_missing_returns_empty_content(writer_missing: TestClient) -> None:
    body = writer_missing.get("/api/agents/writer/includes/voice_profile").json()
    assert body["status"] == "missing"
    assert body["content"] == ""
    assert body["editable"] is False


# ---------------------------------------------------------------------------
# PUT /includes/{placeholder}


def test_put_include_local_writes_and_snapshots(writer_local: TestClient, tmp_path: Path) -> None:
    r = writer_local.put(
        "/api/agents/writer/includes/voice_profile",
        json={"content": "new voice", "note": "edit"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["snapshot_id"]
    assert body["bytes"] == len("new voice")

    on_disk = (tmp_path / "packages/agents/writer/prompts/voice-profile.md").read_text(encoding="utf-8")
    assert on_disk == "new voice"

    snaps = writer_local.get("/api/agents/writer/includes/voice_profile/snapshots").json()
    kinds = [s["kind"] for s in snaps]
    assert kinds.count("pre_first_save") == 1
    assert kinds.count("save") == 1


def test_put_include_shared_writes_to_shared_file(writer_shared: TestClient, tmp_path: Path) -> None:
    r = writer_shared.put(
        "/api/agents/writer/includes/voice_profile",
        json={"content": "edited via writer"},
    )
    assert r.status_code == 200
    on_disk = (tmp_path / "packages/agents/_shared/prompts/voice_profile.md").read_text(encoding="utf-8")
    assert on_disk == "edited via writer"


def test_put_include_example_status_returns_409(writer_local_example: TestClient) -> None:
    r = writer_local_example.put(
        "/api/agents/writer/includes/voice_profile",
        json={"content": "x"},
    )
    assert r.status_code == 409


def test_put_include_missing_returns_409(writer_missing: TestClient) -> None:
    r = writer_missing.put(
        "/api/agents/writer/includes/voice_profile",
        json={"content": "x"},
    )
    assert r.status_code == 409


def test_put_include_over_size_limit_returns_413(writer_local: TestClient) -> None:
    big = "x" * (1_000_000 + 1)
    r = writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": big})
    assert r.status_code == 413


def test_put_include_jarvis_returns_404(writer_local: TestClient) -> None:
    # JARVIS has no prompt_includes — _lookup short-circuits with 404.
    r = writer_local.put("/api/agents/JARVIS/includes/voice_profile", json={"content": "x"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /includes/{placeholder}/promote


def test_promote_from_local_example_creates_local_file(writer_local_example: TestClient, tmp_path: Path) -> None:
    r = writer_local_example.post("/api/agents/writer/includes/voice_profile/promote")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "found_local"
    assert body["editable"] is True
    assert body["content"] == "starter voice"

    on_disk = (tmp_path / "packages/agents/writer/prompts/voice-profile.md").read_text(encoding="utf-8")
    assert on_disk == "starter voice"


def test_promote_from_shared_example_creates_local_override(tmp_path: Path) -> None:
    _make_shared(tmp_path, voice_profile__example="shared starter")
    meta = _make_meta(
        tmp_path,
        "writer",
        prompt_includes={"voice_profile": "voice_profile"},
    )
    client = TestClient(_build_app(tmp_path, {"writer": meta}))
    r = client.post("/api/agents/writer/includes/voice_profile/promote")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "found_local"
    assert body["content"] == "shared starter"

    # Shared file untouched.
    shared = (tmp_path / "packages/agents/_shared/prompts/voice_profile.md.example").read_text(encoding="utf-8")
    assert shared == "shared starter"


def test_promote_from_missing_creates_empty_local(writer_missing: TestClient, tmp_path: Path) -> None:
    r = writer_missing.post("/api/agents/writer/includes/voice_profile/promote")
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == ""
    on_disk = (tmp_path / "packages/agents/writer/prompts/voice-profile.md").read_text(encoding="utf-8")
    assert on_disk == ""


def test_promote_when_local_already_exists_returns_409(writer_local: TestClient) -> None:
    r = writer_local.post("/api/agents/writer/includes/voice_profile/promote")
    assert r.status_code == 409


def test_promote_when_shared_already_resolves_returns_409(writer_shared: TestClient) -> None:
    """Shared (no local) is editable in place — promote is a no-op error."""
    r = writer_shared.post("/api/agents/writer/includes/voice_profile/promote")
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# GET /includes/{placeholder}/snapshots


def test_list_include_snapshots_empty_initially(writer_local: TestClient) -> None:
    r = writer_local.get("/api/agents/writer/includes/voice_profile/snapshots")
    assert r.status_code == 200
    assert r.json() == []


def test_list_include_snapshots_grows_after_save(writer_local: TestClient) -> None:
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "v1"})
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "v2"})
    rows = writer_local.get("/api/agents/writer/includes/voice_profile/snapshots").json()
    kinds = [r["kind"] for r in rows]
    assert kinds.count("pre_first_save") == 1
    assert kinds.count("save") == 2


def test_list_include_snapshots_isolated_from_system_md_history(writer_local: TestClient) -> None:
    """Saving an include must not pollute system.md's snapshot list."""
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "x"})
    sys_snaps = writer_local.get("/api/agents/writer/prompt/snapshots").json()
    assert sys_snaps == []


# ---------------------------------------------------------------------------
# POST /includes/{placeholder}/restore


def test_restore_include_writes_pre_restore_snapshot(writer_local: TestClient, tmp_path: Path) -> None:
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "v1"})
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "v2"})

    rows = writer_local.get("/api/agents/writer/includes/voice_profile/snapshots").json()
    pre_first = next(r for r in rows if r["kind"] == "pre_first_save")

    r = writer_local.post(
        "/api/agents/writer/includes/voice_profile/restore",
        json={"snapshot_id": pre_first["id"]},
    )
    assert r.status_code == 200
    on_disk = (tmp_path / "packages/agents/writer/prompts/voice-profile.md").read_text(encoding="utf-8")
    assert on_disk == "terse and precise"

    rows_after = writer_local.get("/api/agents/writer/includes/voice_profile/snapshots").json()
    assert any(r["kind"] == "pre_restore" for r in rows_after)


def test_restore_include_unknown_snapshot_404(writer_local: TestClient) -> None:
    # Force the include to be editable (resolve is local) so we hit the snapshot lookup.
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "v1"})
    r = writer_local.post(
        "/api/agents/writer/includes/voice_profile/restore",
        json={"snapshot_id": "20990101T000000_000000Z"},
    )
    assert r.status_code == 404


def test_restore_after_promote_writes_to_local_path(writer_local_example: TestClient, tmp_path: Path) -> None:
    """Restore must target the currently-resolved file, not the path at snapshot time."""
    # Promote (creates local file from .md.example) → save (creates first snapshots).
    writer_local_example.post("/api/agents/writer/includes/voice_profile/promote")
    writer_local_example.put("/api/agents/writer/includes/voice_profile", json={"content": "edited"})

    rows = writer_local_example.get("/api/agents/writer/includes/voice_profile/snapshots").json()
    pre_first = next(r for r in rows if r["kind"] == "pre_first_save")

    r = writer_local_example.post(
        "/api/agents/writer/includes/voice_profile/restore",
        json={"snapshot_id": pre_first["id"]},
    )
    assert r.status_code == 200

    # Restored content lands in the local file, not the example.
    local = (tmp_path / "packages/agents/writer/prompts/voice-profile.md").read_text(encoding="utf-8")
    assert local == "starter voice"
    example = (tmp_path / "packages/agents/writer/prompts/voice-profile.md.example").read_text(encoding="utf-8")
    assert example == "starter voice"  # untouched


# ---------------------------------------------------------------------------
# Lock identity (PUT and POST share the same lock per (agent, placeholder))


def test_put_and_promote_share_write_lock(writer_local: TestClient) -> None:
    """Both endpoints must call _get_write_lock with the same key shape."""
    from apps.gui.server.routes.agent_includes import _history_key

    key = _history_key("writer", "voice_profile")
    # First call creates the lock; we don't care about its identity here, only
    # that the routes both successfully serialize through it. The smoke test
    # is that PUT + promote both 200 / 409 (deterministic) without deadlock.
    writer_local.put("/api/agents/writer/includes/voice_profile", json={"content": "v1"})
    r = writer_local.post("/api/agents/writer/includes/voice_profile/promote")
    assert r.status_code == 409  # local already exists
    # Sanity: the helper produces the documented shape so the lock dict key is stable.
    assert key == "writer/_includes/voice_profile"
