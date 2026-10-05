"""Tests for the proposal-based Claude memory importer."""

import json
from pathlib import Path

import pytest

from packages.core.importers.claude_memory import (
    Fact,
    Proposal,
    apply_proposal,
    archive_export,
    build_prompt,
    draft_proposals,
    export_date,
    find_memory_file,
    find_project_notes,
    load_export_facts,
    load_project_names,
    log_decision,
    note_updated,
    parse_facts,
    parse_proposals,
    route,
)

NOTE = """---
created: 2026-04-09
updated: 2026-04-09
aliases:
tags:
  - type/jarvis-memory
type: jarvis-memory
memory-section: professional
summary: "Work"
source:
  - marco
---
# Professional Context

## Skills
- Python
- Agile coaching

## Trajectory
- Moving toward AI engineering
"""

FACTS = [
    Fact(id="f1", text="Knows Go", source_file="/profile.md", updated="2026-09-12"),
    Fact(id="f2", text="Old fact", source_file="/profile.md", updated="2026-03-01"),
]


def _proposal(**overrides) -> Proposal:
    base = {
        "section": "professional",
        "action": "add",
        "heading": "Skills",
        "new": "Go",
        "old": None,
        "fact_ids": ["f1"],
        "fact_date": "2026-09-12",
        "reason": "missing",
    }
    return Proposal(**{**base, **overrides})


# ==================== routing and parsing ====================


class TestRoute:
    @pytest.mark.parametrize(
        ("path", "section"),
        [
            ("/profile.md", "professional"),
            ("/people/fred.md", "professional"),
            ("/areas/brand.md", "professional"),
            ("/topics/communication.md", "preferences"),
            ("/topics/recent-work.md", "focus"),
            ("/topics/skills-and-learning.md", "professional"),
            ("/topics/gaming.md", "personal"),
            ("/projects/019a/overview.md", None),
            ("/unknown.md", None),
        ],
    )
    def test_routes(self, path, section):
        assert route(path) == section


class TestParseFacts:
    def test_strips_marker_and_frontmatter(self):
        content = "---\nname: x\nsources: [backfill]\n---\n- [stated] Lives in Berlin\n-   Plain fact  \ntext\n"
        assert parse_facts(content) == ["Lives in Berlin", "Plain fact"]

    def test_empty(self):
        assert parse_facts("") == []


def _write_export(tmp_path: Path) -> Path:
    export = tmp_path / "export"
    (export / "memories").mkdir(parents=True)
    (export / "light_metadata-000").mkdir()
    (export / "light_metadata-000" / "login_history.json").write_text("[]")
    (export / ".DS_Store").write_text("x")
    (export / "conversations.json").write_text("[]")
    (export / "manifest-1.json").write_text(json.dumps({"created_at": "2026-09-30T15:45:57+00:00"}))
    memory = {
        "memory_files": [
            {"path": "/profile.md", "content": "- [stated] A\n- [stated] B", "updated_at": "2026-09-12T10:00:00Z"},
            {"path": "/topics/gaming.md", "content": "- [stated] C", "updated_at": "2026-09-13T10:00:00Z"},
            {"path": "/projects/p1/overview.md", "content": "- [stated] P", "updated_at": "2026-09-13T10:00:00Z"},
            {"path": "/odd.md", "content": "- [stated] D", "updated_at": "2026-09-13T10:00:00Z"},
        ]
    }
    (export / "memories" / "acct.json").write_text(json.dumps(memory))
    return export


class TestLoadExport:
    def test_routes_facts_and_counts_skips(self, tmp_path):
        export = _write_export(tmp_path)
        facts = load_export_facts(find_memory_file(export))
        assert [(f.id, f.text, f.updated) for f in facts.by_section["professional"]] == [
            ("f1", "A", "2026-09-12"),
            ("f2", "B", "2026-09-12"),
        ]
        assert [f.text for f in facts.by_section["personal"]] == ["C"]
        assert {k: [f.text for f in v] for k, v in facts.by_project.items()} == {"p1": ["P"]}
        assert facts.unrouted == ["/odd.md"]

    def test_find_memory_file_requires_exactly_one(self, tmp_path):
        (tmp_path / "memories").mkdir()
        with pytest.raises(ValueError, match="Expected one file"):
            find_memory_file(tmp_path)

    def test_find_memory_file_missing_folder(self, tmp_path):
        with pytest.raises(ValueError, match="No memories folder"):
            find_memory_file(tmp_path)

    def test_find_memory_file_permission_error_is_explained(self, tmp_path, monkeypatch):
        (tmp_path / "memories").mkdir()

        def deny(self):
            raise PermissionError("Operation not permitted")

        monkeypatch.setattr(Path, "iterdir", deny)
        with pytest.raises(ValueError, match=r"No permission to read .*Privacy & Security"):
            find_memory_file(tmp_path)

    def test_export_date_from_manifest_or_today(self, tmp_path):
        assert export_date(_write_export(tmp_path)) == "2026-09-30"
        empty = tmp_path / "empty"
        empty.mkdir()
        assert len(export_date(empty)) == 10

    def test_archive_skips_account_data_and_runs_once(self, tmp_path):
        export = _write_export(tmp_path)
        target = tmp_path / "archive"
        assert archive_export(export, target) is True
        assert sorted(p.name for p in target.iterdir()) == ["conversations.json", "manifest-1.json", "memories"]
        assert archive_export(export, target) is False


class TestProjects:
    def test_load_project_names(self, tmp_path):
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "a.json").write_text(json.dumps({"uuid": "p1", "name": "JARVIS"}))
        (tmp_path / "projects" / "b.json").write_text(json.dumps({"uuid": "p2"}))
        (tmp_path / "projects" / "c.json").write_text("{broken")
        assert load_project_names(tmp_path) == {"p1": "JARVIS", "p2": "p2"}

    def test_find_project_notes_by_frontmatter_id(self, tmp_path):
        vault = tmp_path / "vault"
        (vault / "Projects" / "J").mkdir(parents=True)
        (vault / ".trash").mkdir()
        (vault / "Projects" / "J" / "_Project Memory.md").write_text(
            "---\ncreated: 2026-03-26\nclaude-project: 019ac6f0-be8c\n---\n# JARVIS\n"
        )
        (vault / "Projects" / "quoted.md").write_text('---\nclaude-project: "019d-aa"\n---\nbody\n')
        (vault / "body-only.md").write_text("no frontmatter\nclaude-project: 019x-body\n")
        (vault / "in-body.md").write_text("---\ntitle: x\n---\nclaude-project: 019y-body\n")
        (vault / ".trash" / "old.md").write_text("---\nclaude-project: 019z-trash\n---\n")
        notes = find_project_notes(vault)
        assert notes == {
            "019ac6f0-be8c": vault / "Projects" / "J" / "_Project Memory.md",
            "019d-aa": vault / "Projects" / "quoted.md",
        }

    def test_prompt_asks_to_follow_note_rules(self):
        prompt = build_prompt("project:JARVIS", NOTE, FACTS)
        assert "follow them, and propose nothing for sections the rules reserve for the owner" in prompt
        assert 'Note "project:JARVIS"' in prompt


# ==================== prompt and proposals ====================


class TestPrompt:
    def test_contains_note_body_date_and_facts(self):
        prompt = build_prompt("professional", NOTE, FACTS)
        assert 'Note "professional" (last updated 2026-04-09)' in prompt
        assert "## Skills\n- Python" in prompt
        assert "created: 2026-04-09" not in prompt
        assert "f1 (2026-09-12, /profile.md): Knows Go" in prompt

    def test_note_updated(self):
        assert note_updated(NOTE) == "2026-04-09"
        assert note_updated("no frontmatter") == ""


class TestParseProposals:
    def test_valid_add_and_update(self):
        raw = """Here you go:
```json
[{"action": "add", "heading": "## Skills", "new": "Go", "fact_ids": ["f1"], "reason": "missing"},
 {"action": "update", "heading": "Skills", "old": "Python", "new": "Python, Go", "fact_ids": ["f1", "zz"]}]
```"""
        proposals = parse_proposals(raw, "professional", FACTS, NOTE)
        assert proposals[0] == _proposal()
        assert proposals[0].position == "bottom"
        assert proposals[1].action == "update"
        assert proposals[1].old == "Python"
        assert proposals[1].fact_ids == ["f1"]
        assert proposals[1].reason == ""

    def test_invalid_entries_dropped(self):
        raw = json.dumps(
            [
                {"action": "delete", "new": "x", "fact_ids": ["f1"]},
                {"action": "add", "new": "", "fact_ids": ["f1"]},
                {"action": "add", "new": "x", "fact_ids": ["nope"]},
                {"action": "update", "old": "Not in note", "new": "x", "fact_ids": ["f1"]},
                {"action": "update", "old": None, "new": "x", "fact_ids": ["f1"]},
                "junk",
            ]
        )
        assert parse_proposals(raw, "professional", FACTS, NOTE) == []

    def test_unparseable(self):
        assert parse_proposals("no json here", "professional", FACTS, NOTE) == []
        assert parse_proposals("[not json]", "professional", FACTS, NOTE) == []

    def test_older_fact_is_conflict(self):
        raw = json.dumps([{"action": "add", "heading": "Skills", "new": "Old", "fact_ids": ["f2"]}])
        proposal = parse_proposals(raw, "professional", FACTS, NOTE)[0]
        assert proposal.conflict is True
        assert proposal.appliable is False
        assert proposal.fact_date == "2026-03-01"

    def test_newest_fact_decides_date(self):
        raw = json.dumps([{"action": "add", "heading": "Skills", "new": "Both", "fact_ids": ["f2", "f1"]}])
        assert parse_proposals(raw, "professional", FACTS, NOTE)[0].conflict is False

    def test_position_top(self):
        raw = json.dumps([{"action": "add", "heading": "Skills", "new": "Go", "fact_ids": ["f1"], "position": "top"}])
        assert parse_proposals(raw, "professional", FACTS, NOTE)[0].position == "top"

    def test_missing_heading_gets_default(self):
        raw = json.dumps([{"action": "add", "new": "Go", "fact_ids": ["f1"]}])
        assert parse_proposals(raw, "professional", FACTS, NOTE)[0].heading == "From Claude export"

    def test_draft_proposals_calls_model_once(self):
        prompts: list[str] = []

        def complete(prompt: str) -> str:
            prompts.append(prompt)
            return json.dumps([{"action": "add", "heading": "Skills", "new": "Go", "fact_ids": ["f1"]}])

        assert len(draft_proposals("professional", NOTE, FACTS, complete)) == 1
        assert len(prompts) == 1
        assert draft_proposals("professional", NOTE, [], complete) == []
        assert len(prompts) == 1


# ==================== applying ====================


class TestApplyProposal:
    def test_add_under_existing_heading(self):
        result = apply_proposal(NOTE, _proposal(), today="2026-10-05")
        assert result is not None
        assert "## Skills\n- Python\n- Agile coaching\n- Go\n\n## Trajectory" in result

    def test_add_at_top_of_section(self):
        note = NOTE.replace("## Trajectory\n", "## Log (newest first)\n\n- **2026-03** — old\n\n## Trajectory\n")
        result = apply_proposal(
            note, _proposal(heading="Log (newest first)", new="**2026-09** — new", position="top"), today="2026-10-05"
        )
        assert result is not None
        assert "## Log (newest first)\n\n- **2026-09** — new\n- **2026-03** — old\n\n## Trajectory" in result

    def test_add_at_top_of_empty_section(self):
        note = NOTE.replace("## Trajectory\n", "## Log\n\n## Trajectory\n")
        result = apply_proposal(note, _proposal(heading="Log", new="first", position="top"), today="2026-10-05")
        assert result is not None
        assert "## Log\n- first\n\n## Trajectory" in result

    def test_add_to_last_section(self):
        result = apply_proposal(NOTE, _proposal(heading="Trajectory", new="Writing a book"), today="2026-10-05")
        assert result is not None
        assert result.endswith("- Moving toward AI engineering\n- Writing a book\n")

    def test_add_creates_missing_heading(self):
        result = apply_proposal(NOTE, _proposal(heading="Languages", new="German"), today="2026-10-05")
        assert result is not None
        assert result.endswith("- Moving toward AI engineering\n\n## Languages\n- German\n")

    def test_update_replaces_only_that_line(self):
        proposal = _proposal(action="update", old="Python", new="Python, Go")
        result = apply_proposal(NOTE, proposal, today="2026-10-05")
        assert result is not None
        assert "- Python, Go\n- Agile coaching" in result
        assert "- Python\n" not in result

    def test_update_of_vanished_line_returns_none(self):
        proposal = _proposal(action="update", old="Rust", new="Rust, Go")
        assert apply_proposal(NOTE, proposal, today="2026-10-05") is None

    def test_conflict_never_applied(self):
        assert apply_proposal(NOTE, _proposal(conflict=True), today="2026-10-05") is None

    def test_frontmatter_updated_source_and_assist(self):
        result = apply_proposal(NOTE, _proposal(), today="2026-10-05")
        assert result is not None
        head = result.split("\n---\n", 1)[0]
        assert "updated: 2026-10-05" in head
        assert "created: 2026-04-09" in head
        assert "source:\n  - marco\n  - claude-export" in head
        assert head.endswith("assist:\n  - prose")
        assert "aliases:\ntags:" in head  # untouched fields keep their formatting

    def test_repeated_apply_adds_no_duplicates(self):
        once = apply_proposal(NOTE, _proposal(), today="2026-10-05")
        assert once is not None
        twice = apply_proposal(once, _proposal(new="Rust"), today="2026-10-06")
        assert twice is not None
        assert twice.count("claude-export") == 1
        assert twice.count("  - prose") == 1
        assert "updated: 2026-10-06" in twice

    def test_inline_list_converted(self):
        note = "---\nupdated: 2026-01-01\nsource: [marco, readwise]\nassist: prose\n---\n## Skills\n- Python\n"
        result = apply_proposal(note, _proposal(), today="2026-10-05")
        assert result is not None
        assert "source:\n  - marco\n  - readwise\n  - claude-export\n" in result
        assert "assist:\n  - prose\n---" in result

    def test_note_without_frontmatter(self):
        result = apply_proposal("## Skills\n- Python\n", _proposal(), today="2026-10-05")
        assert result == "## Skills\n- Python\n- Go\n"


class TestLogDecision:
    def test_appends_jsonl(self, tmp_path):
        log = tmp_path / "logs" / "decisions.jsonl"
        log_decision(log, _proposal(), "applied", model="m", applied_text="Go")
        log_decision(log, _proposal(), "edited", model="m", applied_text="Go, Rust")
        first, second = (json.loads(line) for line in log.read_text().splitlines())
        assert first["decision"] == "applied"
        assert first["model"] == "m"
        assert first["new"] == "Go"
        assert "applied_text" not in first
        assert second["applied_text"] == "Go, Rust"
