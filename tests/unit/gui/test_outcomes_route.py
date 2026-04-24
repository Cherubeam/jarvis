"""Tests for /api/outcomes/pending and /api/outcomes/{file_id}/review."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.routes.outcomes import router as outcomes_router
from packages.core import frontmatter
from packages.core.settings import OutcomesSettings


def _write_outcome(
    outcomes_dir: Path,
    name: str,
    *,
    status: str = "pending",
    revisit_at: str = "2026-04-10",
    what: str = "Do the thing",
    why: str = "Because reasons",
    success_looks_like: str = "",
) -> Path:
    outcomes_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "created_at": "2026-04-01T14:32:00",
        "revisit_at": revisit_at,
        "status": status,
        "what": what,
        "why": why,
        "success_looks_like": success_looks_like,
        "conversation_id": "c1",
    }
    path = outcomes_dir / name
    path.write_text(frontmatter.dump(meta, ""), encoding="utf-8")
    return path


def _build_app(jarvis_dir: Path, outcomes_enabled: bool = True) -> FastAPI:
    settings = SimpleNamespace(outcomes=OutcomesSettings(enabled=outcomes_enabled, dir="data/outcomes"))
    components = SimpleNamespace(
        config={"_paths": {"jarvis_dir": jarvis_dir}},
        settings=settings,
        jarvis_dir=jarvis_dir,
    )
    app = FastAPI()
    app.state.gui_session = SimpleNamespace(components=components)
    app.include_router(outcomes_router)
    return app


@pytest.fixture
def outcomes_dir(tmp_path: Path) -> Path:
    return tmp_path / "data" / "outcomes"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(_build_app(tmp_path))


# ---- GET /api/outcomes/pending ---------------------------------------------


def test_pending_empty_when_no_dir(tmp_path: Path):
    c = TestClient(_build_app(tmp_path))
    r = c.get("/api/outcomes/pending?today=2026-05-01")
    assert r.status_code == 200
    assert r.json() == []


def test_pending_returns_due_items(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "a.md", revisit_at="2026-04-10", what="Do A")
    _write_outcome(outcomes_dir, "b.md", revisit_at="2026-04-15", what="Do B")
    c = TestClient(_build_app(tmp_path))
    r = c.get("/api/outcomes/pending?today=2026-05-01")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    # sorted by revisit_at ascending
    assert items[0]["file_id"] == "a"
    assert items[0]["what"] == "Do A"
    assert items[1]["file_id"] == "b"


def test_pending_excludes_future_and_reviewed(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "due.md", revisit_at="2026-04-10")
    _write_outcome(outcomes_dir, "future.md", revisit_at="2026-06-01")
    _write_outcome(outcomes_dir, "done.md", status="reviewed", revisit_at="2026-04-10")
    c = TestClient(_build_app(tmp_path))
    r = c.get("/api/outcomes/pending?today=2026-05-01")
    assert r.status_code == 200
    ids = [i["file_id"] for i in r.json()]
    assert ids == ["due"]


def test_pending_invalid_today_returns_400(client: TestClient):
    r = client.get("/api/outcomes/pending?today=garbage")
    assert r.status_code == 400
    assert "garbage" in r.json()["detail"]


def test_pending_returns_empty_when_disabled(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "a.md")  # would otherwise be returned
    c = TestClient(_build_app(tmp_path, outcomes_enabled=False))
    r = c.get("/api/outcomes/pending")
    assert r.status_code == 200
    assert r.json() == []


def test_pending_wire_shape(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(
        outcomes_dir,
        "x.md",
        revisit_at="2026-04-10",
        what="W",
        why="Y",
        success_looks_like="S",
    )
    c = TestClient(_build_app(tmp_path))
    r = c.get("/api/outcomes/pending?today=2026-05-01")
    assert r.status_code == 200
    item = r.json()[0]
    assert set(item) == {"file_id", "what", "why", "created_at", "revisit_at", "success_looks_like"}
    assert item["success_looks_like"] == "S"


# ---- POST /api/outcomes/{file_id}/review -----------------------------------


def test_review_happy_path_updates_file(tmp_path: Path, outcomes_dir: Path):
    path = _write_outcome(outcomes_dir, "a.md")
    c = TestClient(_build_app(tmp_path))

    r = c.post(
        "/api/outcomes/a/review",
        json={"outcome": "happened", "quality": 4, "note": "went well"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["file_id"] == "a"
    assert body["outcome"] == "happened"
    assert body["quality"] == 4
    assert "reviewed_at" in body

    updated_meta, updated_body = frontmatter.parse(path.read_text())
    assert updated_meta["status"] == "reviewed"
    assert updated_meta["outcome"] == "happened"
    assert updated_meta["quality"] == 4
    assert updated_body == "went well"


def test_review_missing_file_returns_404(client: TestClient):
    r = client.post(
        "/api/outcomes/nope/review",
        json={"outcome": "happened", "quality": 3, "note": ""},
    )
    assert r.status_code == 404


def test_review_path_traversal_blocked(client: TestClient):
    r = client.post(
        "/api/outcomes/..%2Fetc%2Fpasswd/review",
        json={"outcome": "happened", "quality": 3, "note": ""},
    )
    assert r.status_code == 404


def test_review_invalid_outcome_400(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "a.md")
    c = TestClient(_build_app(tmp_path))
    r = c.post(
        "/api/outcomes/a/review",
        json={"outcome": "maybe", "quality": 3, "note": ""},
    )
    assert r.status_code == 400
    assert "maybe" in r.json()["detail"]


def test_review_invalid_quality_422(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "a.md")
    c = TestClient(_build_app(tmp_path))
    r = c.post(
        "/api/outcomes/a/review",
        json={"outcome": "happened", "quality": 7, "note": ""},
    )
    # FastAPI/pydantic validator rejects out-of-range int with 422
    assert r.status_code == 422


def test_review_already_reviewed_returns_409(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "a.md", status="reviewed")
    c = TestClient(_build_app(tmp_path))
    r = c.post(
        "/api/outcomes/a/review",
        json={"outcome": "happened", "quality": 3, "note": ""},
    )
    assert r.status_code == 409


def test_review_rejected_when_disabled(tmp_path: Path, outcomes_dir: Path):
    _write_outcome(outcomes_dir, "a.md")
    c = TestClient(_build_app(tmp_path, outcomes_enabled=False))
    r = c.post(
        "/api/outcomes/a/review",
        json={"outcome": "happened", "quality": 3, "note": ""},
    )
    assert r.status_code == 403
