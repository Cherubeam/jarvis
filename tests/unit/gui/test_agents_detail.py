"""Tests for apps.gui.server.agents.detail."""

from datetime import date
from types import SimpleNamespace

from apps.gui.server.agents.detail import cost_14d_rollup, recent_sessions_for_agent


def _fake_index(entries: list[dict]):
    """Build a stand-in for ConversationIndex with a _cache attribute.

    Each entry becomes `_cache["path-N"] = (mtime_ns, summary_dict)` — same
    shape ConversationIndex.facets() walks.
    """
    cache = {f"path-{i}": (0, e) for i, e in enumerate(entries)}
    return SimpleNamespace(_cache=cache)


# ---- cost_14d_rollup ------------------------------------------------------


def test_empty_cache_returns_fourteen_zero_days():
    idx = _fake_index([])
    out = cost_14d_rollup(idx, "writer", today=date(2026, 4, 22))
    assert len(out["days"]) == 14
    assert all(d["cost"] == 0.0 for d in out["days"])
    assert out["total"] == 0.0


def test_window_ends_today_and_starts_thirteen_days_earlier():
    out = cost_14d_rollup(_fake_index([]), "writer", today=date(2026, 4, 22))
    assert out["days"][0]["date"] == "2026-04-09"
    assert out["days"][-1]["date"] == "2026-04-22"


def test_only_sums_costs_where_agent_is_in_summary_agents():
    entries = [
        {"date": "2026-04-22", "cost": 0.01, "agents": ["writer", "JARVIS"]},
        {"date": "2026-04-22", "cost": 0.02, "agents": ["researcher"]},  # excluded
        {"date": "2026-04-20", "cost": 0.03, "agents": ["JARVIS", "writer"]},
    ]
    out = cost_14d_rollup(_fake_index(entries), "writer", today=date(2026, 4, 22))
    # Index -1 is today (2026-04-22).
    assert abs(out["days"][-1]["cost"] - 0.01) < 1e-9
    # 2026-04-20 is two days back → index 11.
    assert abs(out["days"][11]["cost"] - 0.03) < 1e-9
    assert abs(out["total"] - 0.04) < 1e-9


def test_missing_cost_or_none_tolerated():
    entries = [
        {"date": "2026-04-22", "agents": ["writer"]},  # no cost key
        {"date": "2026-04-22", "cost": None, "agents": ["writer"]},
        {"date": "2026-04-22", "cost": 0.005, "agents": ["writer"]},
    ]
    out = cost_14d_rollup(_fake_index(entries), "writer", today=date(2026, 4, 22))
    assert out["days"][-1]["cost"] == 0.005
    assert out["total"] == 0.005


def test_entries_outside_window_are_ignored():
    entries = [
        {"date": "2026-04-08", "cost": 100.0, "agents": ["writer"]},  # one day before window
        {"date": "2026-04-23", "cost": 200.0, "agents": ["writer"]},  # future
        {"date": "2026-04-09", "cost": 0.01, "agents": ["writer"]},
    ]
    out = cost_14d_rollup(_fake_index(entries), "writer", today=date(2026, 4, 22))
    assert out["total"] == 0.01


def test_missing_agents_key_treated_as_empty():
    entries = [
        {"date": "2026-04-22", "cost": 0.01},  # no agents key
        {"date": "2026-04-22", "cost": 0.02, "agents": None},
    ]
    out = cost_14d_rollup(_fake_index(entries), "writer", today=date(2026, 4, 22))
    assert out["total"] == 0.0


def test_defaults_to_today_when_not_passed():
    out = cost_14d_rollup(_fake_index([]), "writer")
    assert len(out["days"]) == 14


def test_custom_days_parameter():
    out = cost_14d_rollup(_fake_index([]), "writer", today=date(2026, 4, 22), days=7)
    assert len(out["days"]) == 7
    assert out["days"][0]["date"] == "2026-04-16"
    assert out["days"][-1]["date"] == "2026-04-22"


# ---- recent_sessions_for_agent -------------------------------------------


def test_filters_by_agent_and_sorts_recent_first():
    entries = [
        {"id": "2026-04-20_10-00-00", "agents": ["writer"], "date": "2026-04-20"},
        {"id": "2026-04-22_14-00-00", "agents": ["writer", "JARVIS"], "date": "2026-04-22"},
        {"id": "2026-04-21_09-00-00", "agents": ["researcher"], "date": "2026-04-21"},  # excluded
        {"id": "2026-04-19_12-00-00", "agents": ["writer"], "date": "2026-04-19"},
    ]
    out = recent_sessions_for_agent(_fake_index(entries), "writer")
    assert [s["id"] for s in out] == [
        "2026-04-22_14-00-00",
        "2026-04-20_10-00-00",
        "2026-04-19_12-00-00",
    ]


def test_respects_limit():
    entries = [
        {"id": f"2026-04-{d:02d}_10-00-00", "agents": ["writer"], "date": f"2026-04-{d:02d}"} for d in range(10, 20)
    ]
    out = recent_sessions_for_agent(_fake_index(entries), "writer", limit=3)
    assert len(out) == 3
    assert out[0]["id"] == "2026-04-19_10-00-00"


def test_returns_empty_when_no_match():
    entries = [
        {"id": "2026-04-22_10-00-00", "agents": ["researcher"], "date": "2026-04-22"},
    ]
    out = recent_sessions_for_agent(_fake_index(entries), "writer")
    assert out == []


def test_tolerates_missing_agents_key():
    entries = [
        {"id": "2026-04-22_10-00-00", "date": "2026-04-22"},
        {"id": "2026-04-21_10-00-00", "agents": None, "date": "2026-04-21"},
        {"id": "2026-04-20_10-00-00", "agents": ["writer"], "date": "2026-04-20"},
    ]
    out = recent_sessions_for_agent(_fake_index(entries), "writer")
    assert [s["id"] for s in out] == ["2026-04-20_10-00-00"]


def test_default_limit_is_six():
    entries = [
        {"id": f"2026-04-{d:02d}_10-00-00", "agents": ["writer"], "date": f"2026-04-{d:02d}"} for d in range(1, 15)
    ]
    out = recent_sessions_for_agent(_fake_index(entries), "writer")
    assert len(out) == 6
