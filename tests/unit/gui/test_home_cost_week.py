"""Tests for apps.gui.server.home.cost_week."""

from datetime import date
from types import SimpleNamespace

from apps.gui.server.home.cost_week import cost_week_rollup


def _fake_index(entries: list[dict]):
    """Build a stand-in for ConversationIndex with just a _cache attribute.

    Each entry becomes `_cache["path-N"] = (mtime_ns, summary_dict)` — the
    same shape ConversationIndex.facets() walks.
    """
    cache = {f"path-{i}": (0, e) for i, e in enumerate(entries)}
    return SimpleNamespace(_cache=cache)


def test_empty_cache_returns_seven_zero_days():
    idx = _fake_index([])
    out = cost_week_rollup(idx, today=date(2026, 4, 20))
    assert len(out["days"]) == 7
    assert all(d["cost"] == 0.0 for d in out["days"])
    assert all(d["conversations"] == 0 for d in out["days"])
    assert out["total"] == 0.0
    assert out["conversation_count"] == 0


def test_window_ends_today_and_starts_six_days_earlier():
    today = date(2026, 4, 20)
    out = cost_week_rollup(_fake_index([]), today=today)
    assert out["days"][0]["date"] == "2026-04-14"
    assert out["days"][-1]["date"] == "2026-04-20"


def test_sums_costs_by_date_and_counts_conversations():
    entries = [
        {"date": "2026-04-20", "cost": 0.0100},
        {"date": "2026-04-20", "cost": 0.0050},
        {"date": "2026-04-18", "cost": 0.0042},
        {"date": "2026-04-14", "cost": 0.0001},
    ]
    out = cost_week_rollup(_fake_index(entries), today=date(2026, 4, 20))
    # Indices: 0=14, 1=15, 2=16, 3=17, 4=18, 5=19, 6=20.
    assert out["days"][0]["cost"] == 0.0001
    assert out["days"][0]["conversations"] == 1
    assert out["days"][4]["cost"] == 0.0042
    assert out["days"][4]["conversations"] == 1
    assert abs(out["days"][6]["cost"] - 0.015) < 1e-9
    assert out["days"][6]["conversations"] == 2
    # Days 1, 2, 3, 5 are zero.
    for i in (1, 2, 3, 5):
        assert out["days"][i]["cost"] == 0.0
        assert out["days"][i]["conversations"] == 0
    assert abs(out["total"] - 0.0193) < 1e-9
    assert out["conversation_count"] == 4


def test_entries_outside_window_are_ignored():
    entries = [
        {"date": "2026-04-13", "cost": 100.0},  # one day before window
        {"date": "2026-04-21", "cost": 200.0},  # future, not in 7-day window
        {"date": "2026-04-14", "cost": 0.01},
    ]
    out = cost_week_rollup(_fake_index(entries), today=date(2026, 4, 20))
    assert out["total"] == 0.01
    assert out["conversation_count"] == 1


def test_missing_cost_or_none_tolerated():
    entries = [
        {"date": "2026-04-20"},                     # no cost key
        {"date": "2026-04-20", "cost": None},       # None cost
        {"date": "2026-04-20", "cost": 0.005},
    ]
    out = cost_week_rollup(_fake_index(entries), today=date(2026, 4, 20))
    assert out["days"][-1]["cost"] == 0.005
    assert out["days"][-1]["conversations"] == 3


def test_defaults_to_today_when_not_passed():
    # Just verify it runs without error; actual window depends on today.
    out = cost_week_rollup(_fake_index([]))
    assert len(out["days"]) == 7
