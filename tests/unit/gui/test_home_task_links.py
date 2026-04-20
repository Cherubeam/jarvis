"""Tests for apps.gui.server.home.task_links."""

from apps.gui.server.home.task_links import link_tasks_to_conversations


def _s(id_: str, title: str) -> dict:
    return {"id": id_, "title": title}


def test_empty_inputs():
    assert link_tasks_to_conversations([], []) == []
    out = link_tasks_to_conversations(
        [{"title": "Week-12 Substack draft"}],
        [],
    )
    assert out == [{"title": "Week-12 Substack draft", "linked_conversation_ids": []}]


def test_longest_word_matches_first():
    tasks = [{"title": "Week-12 Substack draft"}]
    # "substack" is longer than "week", "draft". It should match first.
    summaries = [
        _s("2026-04-18_09-00-00", "week-12 substack · draft opening"),
        _s("2026-04-15_11-00-00", "substack pricing strategy"),
    ]
    out = link_tasks_to_conversations(tasks, summaries)
    ids = out[0]["linked_conversation_ids"]
    # Both match "substack"; order follows summary order. Capped at 2.
    assert ids == ["2026-04-18_09-00-00", "2026-04-15_11-00-00"]


def test_skips_short_words():
    tasks = [{"title": "TL;DR of q1"}]  # only "of" + "q1" both < 4 chars
    summaries = [_s("c1", "quarterly review of q1 and q2")]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["linked_conversation_ids"] == []


def test_dedupes_across_words_and_caps_at_two():
    tasks = [{"title": "Ship JARVIS GUI prototype v1"}]
    # Every summary contains either "jarvis" or "prototype" or both; order
    # matters because we walk summaries in order per word.
    summaries = [
        _s("c1", "jarvis gui prototype phase 1"),
        _s("c2", "prototype iteration notes"),
        _s("c3", "jarvis config refactor"),
        _s("c4", "ship review"),
    ]
    ids = link_tasks_to_conversations(tasks, summaries)[0]["linked_conversation_ids"]
    # Only 2 ids returned; no duplicates.
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_case_insensitive_match():
    tasks = [{"title": "Weekly Substack Review"}]
    summaries = [_s("c1", "SUBSTACK planning notes")]
    assert link_tasks_to_conversations(tasks, summaries)[0]["linked_conversation_ids"] == ["c1"]


def test_preserves_task_fields():
    tasks = [{"title": "Research pricing", "project": "Blog", "priority": "high"}]
    summaries = [_s("c1", "pricing landscape for substack")]
    out = link_tasks_to_conversations(tasks, summaries)
    assert out[0]["project"] == "Blog"
    assert out[0]["priority"] == "high"
    # "pricing" (7 chars) matches as a substring.
    assert out[0]["linked_conversation_ids"] == ["c1"]
