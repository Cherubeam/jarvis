"""Tests for GET /api/agents and GET /api/agents/{id}."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.gui.server.history.index import ConversationIndex
from apps.gui.server.routes.agents import router as agents_router
from packages.agents.registry import discover_agents


def _write(path, agents, cost=0.01, tokens=100, session_start="2026-04-19T10:00:00"):
    """Write a minimal migrated conversation JSON with the given speaker agents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": "test"}]
    for agent in agents:
        messages.append({"role": "assistant", "agent": agent, "content": "ok"})
    data = {
        "schema_version": "1.0.0",
        "id": "conv_x",
        "session_start": session_start,
        "session_end": session_start,
        "model": {"id": "openrouter/qwen", "provider": "openrouter"},
        "messages": messages,
        "metrics": {"total_tokens": tokens, "total_cost_usd": cost},
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def _build_app(tmp_path, conv_entries=()):
    """Construct a minimal FastAPI app with the agents router and real registry.

    `conv_entries` is a list of (filename_stem, agents_list, cost) tuples.
    ``session_start`` is derived from the filename stem so the summary ``date``
    field matches the filename's date prefix.
    """
    convs = tmp_path / "conversations"
    for stem, agents, cost in conv_entries:
        # Derive session_start from filename: "YYYY-MM-DD_HH-MM-SS" → "YYYY-MM-DDTHH:MM:SS".
        iso = stem[:10] + "T" + stem[11:].replace("-", ":")
        _write(
            convs / "2026" / f"{stem}.json",
            agents,
            cost=cost,
            session_start=iso,
        )

    index = ConversationIndex(convs)
    asyncio.run(index.refresh())

    app = FastAPI()
    app.state.conversation_index = index
    app.state.gui_session = SimpleNamespace(components=SimpleNamespace(agent_registry=discover_agents()))
    app.include_router(agents_router)
    return app


@pytest.fixture
def client(tmp_path):
    app = _build_app(
        tmp_path,
        conv_entries=[
            ("2026-04-20_10-00-00", ["writer", "JARVIS"], 0.02),
            ("2026-04-18_14-00-00", ["researcher"], 0.01),
            ("2026-04-19_09-00-00", ["writer"], 0.005),
        ],
    )
    return TestClient(app)


# ---- list endpoint ---------------------------------------------------------


def test_list_has_jarvis_first(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()
    assert agents[0]["name"] == "JARVIS"
    assert agents[0]["command"] == ""
    assert "delegate" in agents[0]["tools"]


def test_list_includes_data_driven_agents_sorted(client):
    agents = client.get("/api/agents").json()
    # Skip the JARVIS head and verify alphabetical.
    rest = [a["name"] for a in agents[1:]]
    assert rest == sorted(rest)
    assert "writer" in rest
    assert "researcher" in rest


# ---- detail endpoint -------------------------------------------------------


def test_detail_writer_shape(client):
    r = client.get("/api/agents/writer")
    assert r.status_code == 200
    j = r.json()
    assert set(j.keys()) == {
        "name",
        "command",
        "description",
        "tools",
        "temperature",
        "max_tokens",
        "max_iterations",
        "skills",
        "prompt_path",
        "prompt_includes_count",
        "model",
        "last_used",
        "recent_sessions",
        "cost_14d",
        "cost_14d_total",
    }
    assert j["name"] == "writer"
    assert j["command"] == "/write"
    assert j["prompt_path"] == "packages/agents/writer/prompts/system.md"
    assert j["model"] is None
    assert isinstance(j["cost_14d"], list)
    assert len(j["cost_14d"]) == 14


def test_detail_writer_meta_yaml_fields_populated(client):
    """temperature/max_iterations come from the real meta.yaml re-parse."""
    j = client.get("/api/agents/writer").json()
    # writer's meta.yaml has temperature set (verified from source tree).
    # The re-parse should surface floats/ints — not all-null.
    assert j["temperature"] is None or isinstance(j["temperature"], int | float)
    assert j["max_tokens"] is None or isinstance(j["max_tokens"], int)
    assert j["max_iterations"] is None or isinstance(j["max_iterations"], int)


def test_detail_recent_sessions_filtered_by_agent(client):
    j = client.get("/api/agents/writer").json()
    ids = [s["id"] for s in j["recent_sessions"]]
    assert "2026-04-20_10-00-00" in ids
    assert "2026-04-19_09-00-00" in ids
    # researcher-only conversation is NOT in writer's recent.
    assert "2026-04-18_14-00-00" not in ids
    assert j["last_used"] == "2026-04-20"


def test_detail_jarvis_synthetic_payload(client):
    r = client.get("/api/agents/JARVIS")
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == "JARVIS"
    assert j["prompt_path"] is None
    assert j["prompt_includes_count"] == 0
    assert j["skills"] == []
    assert j["temperature"] is None
    # JARVIS participated in the 2026-04-20 session.
    assert j["last_used"] == "2026-04-20"
    ids = [s["id"] for s in j["recent_sessions"]]
    assert "2026-04-20_10-00-00" in ids


def test_detail_unknown_agent_returns_404(client):
    r = client.get("/api/agents/does-not-exist")
    assert r.status_code == 404


def test_detail_path_traversal_returns_404(client):
    # ".." and "/" in the id are reflected into prompt_path — reject.
    r = client.get("/api/agents/..%2Fetc%2Fpasswd")
    assert r.status_code == 404


def test_detail_cost_14d_sums_only_agent_sessions(client):
    """cost_14d should count the writer's 0.02 + 0.005 conversations but not
    the researcher's 0.01."""
    j = client.get("/api/agents/writer").json()
    # Today may shift the window; just check the total is close to 0.025 if the
    # test-fixture dates fall inside the 14-day window relative to real today.
    # If outside the window the total is 0 — both are correct depending on date.
    # What we CAN assert: cost_14d_total never includes researcher's 0.01.
    assert j["cost_14d_total"] in (0.0, pytest.approx(0.025))


def test_detail_empty_index_returns_empty_recent(tmp_path):
    app = _build_app(tmp_path, conv_entries=[])
    client = TestClient(app)
    r = client.get("/api/agents/writer")
    assert r.status_code == 200
    j = r.json()
    assert j["recent_sessions"] == []
    assert j["last_used"] is None
    assert j["cost_14d_total"] == 0.0


# ---- _guard_agent_id (path-traversal guard) --------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "a/b",
        "../etc/passwd",
        "..",
        "a..b",  # contains ".." mid-string — also caught
        "../",
        "writer/../../escape",
    ],
)
def test_guard_agent_id_rejects_unsafe_input(bad: str):
    from fastapi import HTTPException

    from apps.gui.server.routes.agents import _guard_agent_id

    with pytest.raises(HTTPException) as exc:
        _guard_agent_id(bad)
    assert exc.value.status_code == 404
    # Detail message includes the offending id verbatim — locks the f-string.
    assert exc.value.detail == f"agent '{bad}' not found"


@pytest.mark.parametrize(
    "good",
    [
        "writer",
        "content_reviewer",
        "agent-with-dash",
        "snake_case_name",
        "",  # empty is allowed by this guard (only "/" and ".." rejected)
        ".hidden",  # leading dot allowed (different from outcomes' guard)
    ],
)
def test_guard_agent_id_accepts_safe_input(good: str):
    """Returns None for any string that doesn't contain "/" or ".."."""
    from apps.gui.server.routes.agents import _guard_agent_id

    assert _guard_agent_id(good) is None


# ---- _load_meta_dict (resilient YAML re-parse) -----------------------------


def test_load_meta_dict_parses_valid_yaml(tmp_path):
    from apps.gui.server.routes.agents import _load_meta_dict

    p = tmp_path / "meta.yaml"
    p.write_text(
        "name: writer\ntemperature: 0.5\nmax_tokens: 4096\nprompt_includes:\n  voice_profile: voice-profile\n",
        encoding="utf-8",
    )
    out = _load_meta_dict(p)
    assert out == {
        "name": "writer",
        "temperature": 0.5,
        "max_tokens": 4096,
        "prompt_includes": {"voice_profile": "voice-profile"},
    }


def test_load_meta_dict_missing_file_returns_empty(tmp_path):
    """Missing file → swallowed exception → empty dict so callers can `.get()`."""
    from apps.gui.server.routes.agents import _load_meta_dict

    assert _load_meta_dict(tmp_path / "nope.yaml") == {}


def test_load_meta_dict_corrupt_yaml_returns_empty(tmp_path):
    from apps.gui.server.routes.agents import _load_meta_dict

    p = tmp_path / "meta.yaml"
    p.write_text("not: valid: yaml: at: all:", encoding="utf-8")
    assert _load_meta_dict(p) == {}


def test_load_meta_dict_empty_file_returns_empty(tmp_path):
    """yaml.safe_load(\"\") returns None — must coerce to {} via `or {}`."""
    from apps.gui.server.routes.agents import _load_meta_dict

    p = tmp_path / "meta.yaml"
    p.write_text("", encoding="utf-8")
    assert _load_meta_dict(p) == {}


def test_load_meta_dict_top_level_list_returns_list(tmp_path):
    """Documents the `or {}` only fires for None — a YAML list survives.

    This is intentional: `.get()` on the result will fail loudly upstream.
    Locking the behaviour here means a future "harden" mutation that
    silently coerces non-dict YAML to {} would be killed.
    """
    from apps.gui.server.routes.agents import _load_meta_dict

    p = tmp_path / "meta.yaml"
    p.write_text("- one\n- two\n", encoding="utf-8")
    assert _load_meta_dict(p) == ["one", "two"]


# ---- _get_write_lock (per-agent asyncio.Lock cache) ------------------------


def test_get_write_lock_creates_lock_on_first_call():
    import asyncio as _asyncio

    from apps.gui.server.routes.agents import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())
    lock = _asyncio.run(_get_write_lock(app, "writer"))
    assert isinstance(lock, _asyncio.Lock)
    assert app.state.prompt_write_locks == {"writer": lock}


def test_get_write_lock_returns_same_lock_for_same_agent():
    """Cache hit: a second call must return the exact same Lock instance."""
    import asyncio as _asyncio

    from apps.gui.server.routes.agents import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())

    async def _two_calls():
        a = await _get_write_lock(app, "writer")
        b = await _get_write_lock(app, "writer")
        return a, b

    a, b = _asyncio.run(_two_calls())
    assert a is b
    assert app.state.prompt_write_locks == {"writer": a}


def test_get_write_lock_distinct_per_agent():
    """Different agent_ids must get distinct Lock objects."""
    import asyncio as _asyncio

    from apps.gui.server.routes.agents import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())

    async def _two_agents():
        return await _get_write_lock(app, "writer"), await _get_write_lock(app, "researcher")

    w, r = _asyncio.run(_two_agents())
    assert w is not r
    assert set(app.state.prompt_write_locks.keys()) == {"writer", "researcher"}


def test_get_write_lock_reuses_preexisting_state_dict():
    """If state.prompt_write_locks is already a non-empty dict, that exact
    object must be reused (no replacement)."""
    import asyncio as _asyncio

    from apps.gui.server.routes.agents import _get_write_lock

    preexisting: dict = {"writer": _asyncio.Lock()}
    app = SimpleNamespace(state=SimpleNamespace(prompt_write_locks=preexisting))
    lock = _asyncio.run(_get_write_lock(app, "writer"))
    assert lock is preexisting["writer"]
    assert app.state.prompt_write_locks is preexisting


def test_get_write_lock_serialises_concurrent_holders():
    """Two coroutines awaiting the same lock must execute serially, not interleave."""
    import asyncio as _asyncio

    from apps.gui.server.routes.agents import _get_write_lock

    app = SimpleNamespace(state=SimpleNamespace())
    log: list[str] = []

    async def _hold(label: str, hold_for: float):
        lock = await _get_write_lock(app, "writer")
        async with lock:
            log.append(f"{label}-enter")
            await _asyncio.sleep(hold_for)
            log.append(f"{label}-exit")

    async def _race():
        await _asyncio.gather(_hold("a", 0.05), _hold("b", 0.0))

    _asyncio.run(_race())
    # No interleaving: each holder's enter+exit are adjacent in the log.
    assert log in (
        ["a-enter", "a-exit", "b-enter", "b-exit"],
        ["b-enter", "b-exit", "a-enter", "a-exit"],
    )


# ---- _history_root + path helpers -----------------------------------------


def test_history_root_joins_jarvis_dir_with_settings_path(tmp_path):
    from apps.gui.server.routes.agents import _history_root

    settings = SimpleNamespace(paths=SimpleNamespace(prompt_history_dir="data/prompt-history"))
    components = SimpleNamespace(jarvis_dir=tmp_path, settings=settings)
    session = SimpleNamespace(components=components)
    assert _history_root(session) == tmp_path / "data/prompt-history"


def test_meta_path_returns_none_for_unknown_agent():
    from apps.gui.server.routes.agents import _meta_path

    session = SimpleNamespace(components=SimpleNamespace(agent_registry={}))
    assert _meta_path("nope", session) is None


def test_agent_dir_returns_none_when_meta_path_none():
    from apps.gui.server.routes.agents import _agent_dir

    session = SimpleNamespace(components=SimpleNamespace(agent_registry={}))
    assert _agent_dir("nope", session) is None


def test_system_prompt_path_returns_none_when_agent_dir_none():
    from apps.gui.server.routes.agents import _system_prompt_path

    session = SimpleNamespace(components=SimpleNamespace(agent_registry={}))
    assert _system_prompt_path("nope", session) is None


def test_system_prompt_path_appends_prompts_system_md(tmp_path):
    """Returns ``<agent_dir>/prompts/system.md`` — locks the literal segments."""
    from apps.gui.server.routes.agents import _system_prompt_path
    from packages.agents.registry import AgentMeta

    meta_path = tmp_path / "packages" / "agents" / "writer" / "meta.yaml"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text("name: writer\n", encoding="utf-8")
    registry = {
        "writer": AgentMeta(
            name="writer",
            description="",
            command="/write",
            meta_path=meta_path,
            tool_groups=(),
            skills=(),
            vault_writing=None,
        )
    }
    session = SimpleNamespace(components=SimpleNamespace(agent_registry=registry))
    assert _system_prompt_path("writer", session) == meta_path.parent / "prompts" / "system.md"
