"""Tests for the Claude Code session importer."""

import json
from pathlib import Path
from typing import Any

from packages.core.importers.claude_code import (
    build_messages,
    convert_session,
    import_sessions,
    match_desktop_entry,
    project_name,
    read_transcript,
    session_title,
    summarize_tool_input,
    user_prompt_text,
)

SESSION_ID = "11111111-2222-3333-4444-555555555555"
CWD = "/Users/me/Workspace/github.com/me/jarvis"


def _user(text: Any, ts: str = "2026-10-05T08:00:00.000Z", **extra: Any) -> dict[str, Any]:
    return {
        "type": "user",
        "timestamp": ts,
        "cwd": CWD,
        "gitBranch": "main",
        "entrypoint": "claude-desktop",
        "version": "2.5.0",
        "sessionId": SESSION_ID,
        "message": {"role": "user", "content": text},
        **extra,
    }


def _assistant(
    blocks: list[dict[str, Any]], msg_id: str = "msg_a", ts: str = "2026-10-05T08:00:05.000Z", **usage: int
) -> dict[str, Any]:
    return {
        "type": "assistant",
        "timestamp": ts,
        "cwd": CWD,
        "gitBranch": "feat/x",
        "message": {
            "id": msg_id,
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": blocks,
            "stop_reason": "end_turn",
            "usage": usage or {"input_tokens": 10, "output_tokens": 20},
        },
    }


def _tool_result(content: Any, is_error: bool = False) -> dict[str, Any]:
    return _user(
        [{"type": "tool_result", "tool_use_id": "t1", "content": content, "is_error": is_error}],
        ts="2026-10-05T08:00:06.000Z",
    )


def _session() -> list[dict[str, Any]]:
    return [
        {"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-10-05T07:59:59.000Z"},
        _user("Fix the bug"),
        _assistant([{"type": "thinking", "thinking": "Look at the log."}], msg_id="m1"),
        _assistant([{"type": "tool_use", "name": "Bash", "input": {"command": "git status"}}], msg_id="m1"),
        _tool_result("On branch main\n"),
        _assistant([{"type": "text", "text": "Fixed."}], msg_id="m2", ts="2026-10-05T08:00:09.000Z"),
        {"type": "ai-title", "aiTitle": "Bug fix", "sessionId": SESSION_ID},
        _user("Thanks", ts="2026-10-05T08:01:00.000Z"),
    ]


# ==================== user_prompt_text ====================


class TestUserPromptText:
    def test_plain_string(self):
        assert user_prompt_text(_user("Hello")) == "Hello"

    def test_text_blocks_and_image(self):
        record = _user([{"type": "text", "text": "Look"}, {"type": "image", "source": {}}])
        assert user_prompt_text(record) == "Look\n[Image]"

    def test_tool_result_is_not_a_prompt(self):
        assert user_prompt_text(_tool_result("x")) is None

    def test_meta_and_compact_summary_skipped(self):
        assert user_prompt_text(_user("expanded skill", isMeta=True)) is None
        assert user_prompt_text(_user("summary", isCompactSummary=True)) is None
        assert user_prompt_text(_user("summary", isVisibleInTranscriptOnly=True)) is None

    def test_non_human_origin_skipped(self):
        assert user_prompt_text(_user("peer says hi", origin={"kind": "peer"})) is None
        assert user_prompt_text(_user("typed", origin={"kind": "human"})) == "typed"

    def test_injected_prefixes_skipped(self):
        for text in (
            "<local-command-caveat>Caveat</local-command-caveat>",
            "<local-command-stdout>ok</local-command-stdout>",
            "<task-notification><task-id>1</task-id></task-notification>",
            "<system-reminder>x</system-reminder>",
            "<bash-input>ls</bash-input>",
        ):
            assert user_prompt_text(_user(text)) is None, text
        assert user_prompt_text(_user([{"type": "text", "text": "[Request interrupted by user]"}])) is None

    def test_slash_command_with_args(self):
        text = (
            "<command-message>review</command-message>\n<command-name>/review</command-name>\n"
            "<command-args>PR 5</command-args>"
        )
        assert user_prompt_text(_user(text)) == "/review PR 5"

    def test_slash_command_without_args(self):
        text = (
            "<command-name>/clear</command-name>\n<command-message>clear</command-message>\n"
            "<command-args></command-args>"
        )
        assert user_prompt_text(_user(text)) == "/clear"

    def test_assistant_and_sidechain_are_not_prompts(self):
        assert user_prompt_text(_assistant([{"type": "text", "text": "hi"}])) is None
        assert user_prompt_text(_user("sub", isSidechain=True)) is None

    def test_empty_text_skipped(self):
        assert user_prompt_text(_user("   ")) is None


# ==================== summarize_tool_input ====================


class TestSummarizeToolInput:
    def test_preferred_key(self):
        assert summarize_tool_input({"description": "List", "command": "ls -la"}) == "ls -la"

    def test_file_path(self):
        assert summarize_tool_input({"file_path": "/a/b.py", "old_string": "x"}) == "/a/b.py"

    def test_first_string_fallback(self):
        assert summarize_tool_input({"count": 3, "foo": "bar"}) == "bar"

    def test_json_fallback(self):
        assert summarize_tool_input({"count": 3}) == '{"count": 3}'

    def test_empty_and_non_dict(self):
        assert summarize_tool_input({}) == ""
        assert summarize_tool_input(None) == ""

    def test_collapses_whitespace_and_truncates(self):
        result = summarize_tool_input({"command": "a\n  b " + "x" * 300})
        assert result.startswith("a b x")
        assert len(result) == 200
        assert result.endswith("…")


# ==================== project_name ====================


class TestProjectName:
    def test_repo(self):
        assert project_name(CWD) == "jarvis"

    def test_worktree_maps_to_repo(self):
        assert project_name("/Users/me/repo/jarvis/.claude/worktrees/gallant-x") == "jarvis"

    def test_none(self):
        assert project_name(None) is None


# ==================== build_messages ====================


class TestBuildMessages:
    def test_groups_turns(self):
        messages = build_messages(_session())
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert [m["id"] for m in messages] == ["msg_001", "msg_002", "msg_003"]

        turn = messages[1]
        assert turn["timestamp"] == "2026-10-05T08:00:05.000Z"
        assert turn["usage"] is None
        assert turn["stop_reason"] == "end_turn"
        assert [b["text"] for b in turn["content"]] == [
            "Look at the log.",
            "[Tool: Bash] git status",
            "[Tool result: 15 chars]",
            "Fixed.",
        ]
        assert turn["content"][0]["metadata"] == {"thought": True}
        assert turn["content"][1]["metadata"] == {
            "tool_use": True,
            "tool_name": "Bash",
            "tool_input_summary": "git status",
        }
        assert turn["content"][2]["metadata"] == {"tool_result": True, "is_error": False, "result_chars": 15}

    def test_usage_counted_once_per_message_id(self):
        turn = build_messages(_session())[1]
        assert turn["metadata"]["model"] == "claude-opus-5-5"
        assert turn["metadata"]["claude_code_usage"] == {"input_tokens": 20, "output_tokens": 40}

    def test_tool_error_with_block_content(self):
        records = [
            _user("Go"),
            _assistant([{"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}}]),
            _tool_result([{"type": "text", "text": "missing"}], is_error=True),
        ]
        stub = build_messages(records)[1]["content"][1]
        assert stub["text"] == "[Tool error: 7 chars]"
        assert stub["metadata"]["is_error"] is True

    def test_records_before_first_prompt_dropped(self):
        records = [_assistant([{"type": "text", "text": "orphan"}]), _user("Hi")]
        messages = build_messages(records)
        assert len(messages) == 1
        assert messages[0]["content"] == [{"type": "text", "text": "Hi"}]

    def test_empty_assistant_turn_gets_placeholder(self):
        records = [_user("Hi"), _assistant([{"type": "thinking", "thinking": "  "}])]
        assert build_messages(records)[1]["content"] == [{"type": "text", "text": ""}]

    def test_synthetic_model_ignored(self):
        record = _assistant([{"type": "text", "text": "x"}])
        record["message"]["model"] = "<synthetic>"
        assert "model" not in build_messages([_user("Hi"), record])[1]["metadata"]


# ==================== session_title ====================


class TestSessionTitle:
    def test_desktop_title_wins(self):
        records = [{"type": "custom-title", "customTitle": "Custom"}]
        assert session_title(records, {"title": "Desktop"}) == "Desktop"

    def test_custom_before_ai_title(self):
        records = [
            {"type": "ai-title", "aiTitle": "AI"},
            {"type": "custom-title", "customTitle": "Old"},
            {"type": "custom-title", "customTitle": "New"},
        ]
        assert session_title(records, None) == "New"

    def test_ai_title(self):
        assert session_title([{"type": "ai-title", "aiTitle": "AI"}], {}) == "AI"

    def test_none(self):
        assert session_title([], None) is None


# ==================== convert_session ====================


class TestConvertSession:
    def test_fields(self):
        desktop = {"sessionId": "local_1", "title": "Desk", "isArchived": True}
        conv = convert_session(SESSION_ID, _session(), desktop=desktop, subagent_count=2)
        assert conv is not None
        assert conv["schema_version"] == "1.0.0"
        assert conv["id"].startswith("conv_20261005_075959_")
        assert conv["title"] == "Desk"
        assert conv["tags"] == ["imported", "claude-code", "project:jarvis"]
        assert conv["session_start"] == "2026-10-05T07:59:59.000Z"
        assert conv["session_end"] == "2026-10-05T08:01:00.000Z"
        assert conv["model"] == "claude-opus-5-5"
        meta = conv["metadata"]
        assert meta["import_source"] == "claude_code"
        assert meta["claude_code_session_id"] == SESSION_ID
        assert meta["cwd"] == CWD
        assert meta["project"] == "jarvis"
        assert meta["git_branches"] == ["feat/x", "main"]
        assert meta["entrypoint"] == "claude-desktop"
        assert meta["claude_code_version"] == "2.5.0"
        assert meta["subagent_transcripts"] == 2
        assert meta["desktop_session_id"] == "local_1"
        assert meta["archived"] is True

    def test_title_falls_back_to_first_prompt(self):
        records = [_user("  Please   fix " + "x" * 100)]
        conv = convert_session(SESSION_ID, records)
        assert conv is not None
        assert conv["title"] == ("Please fix " + "x" * 100)[:80]
        assert "desktop_session_id" not in conv["metadata"]

    def test_no_prompt_returns_none(self):
        assert convert_session(SESSION_ID, [_user("x", isMeta=True)]) is None


# ==================== match_desktop_entry ====================


class TestMatchDesktopEntry:
    START = "2026-10-05T08:00:00.000Z"
    START_MS = 1_791_187_200_000  # 2026-10-05T08:00:00Z

    def test_by_cli_id(self):
        entry = {"cliSessionId": SESSION_ID}
        assert match_desktop_entry(SESSION_ID, self.START, CWD, {SESSION_ID: entry}, []) is entry

    def test_by_start_time_and_cwd_closest_wins(self):
        far = {"createdAt": self.START_MS - 1900, "cwd": CWD}
        near = {"createdAt": self.START_MS - 900, "cwd": CWD}
        other_cwd = {"createdAt": self.START_MS, "cwd": "/elsewhere"}
        assert match_desktop_entry(SESSION_ID, self.START, CWD, {}, [far, near, other_cwd]) is near

    def test_outside_tolerance(self):
        entry = {"createdAt": self.START_MS - 2100, "cwd": CWD}
        assert match_desktop_entry(SESSION_ID, self.START, CWD, {}, [entry]) is None

    def test_no_start(self):
        assert match_desktop_entry(SESSION_ID, None, CWD, {}, [{"createdAt": 0, "cwd": CWD}]) is None


# ==================== read_transcript / import_sessions ====================


def _write_transcript(projects: Path, records: list[dict[str, Any]], session_id: str = SESSION_ID) -> Path:
    folder = projects / "-Users-me-jarvis"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{session_id}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


class TestReadTranscript:
    def test_skips_invalid_and_blank_lines(self, tmp_path):
        path = tmp_path / "t.jsonl"
        path.write_text('{"type": "user"}\n\nnot json\n[1, 2]\n{"type": "assistant"}\n')
        assert read_transcript(path) == [{"type": "user"}, {"type": "assistant"}]


class TestImportSessions:
    def test_import_then_unchanged_then_update(self, tmp_path):
        projects = tmp_path / "projects"
        target = tmp_path / "out"
        records = _session()
        transcript = _write_transcript(projects, records)
        (transcript.parent / SESSION_ID / "subagents").mkdir(parents=True)
        (transcript.parent / SESSION_ID / "subagents" / "agent-a.jsonl").write_text("{}\n")

        first = import_sessions(projects, target)
        assert (first.total, first.imported, first.updated, first.skipped_existing) == (1, 1, 0, 0)
        path = target / "2026" / "2026-10-05_07-59-59.json"
        conv = json.loads(path.read_text())
        assert conv["metadata"]["subagent_transcripts"] == 1
        first_import = conv["metadata"]["import_timestamp"]

        second = import_sessions(projects, target)
        assert (second.imported, second.updated, second.skipped_existing) == (0, 0, 1)

        records.append(_assistant([{"type": "text", "text": "You're welcome."}], msg_id="m3"))
        _write_transcript(projects, records)
        third = import_sessions(projects, target)
        assert (third.imported, third.updated) == (0, 1)
        updated = json.loads(path.read_text())
        assert updated["id"] == conv["id"]
        assert len(updated["messages"]) == 4
        assert updated["metadata"]["import_timestamp"] == first_import
        assert "last_sync_timestamp" in updated["metadata"]
        assert list(target.rglob("*.json")) == [path]

    def test_shorter_transcript_left_alone(self, tmp_path):
        projects = tmp_path / "projects"
        target = tmp_path / "out"
        _write_transcript(projects, _session())
        import_sessions(projects, target)
        _write_transcript(projects, _session()[:3])
        summary = import_sessions(projects, target)
        assert (summary.updated, summary.skipped_existing) == (0, 1)
        path = next(target.rglob("*.json"))
        assert len(json.loads(path.read_text())["messages"]) == 3

    def test_dry_run_writes_nothing(self, tmp_path):
        projects = tmp_path / "projects"
        _write_transcript(projects, _session())
        summary = import_sessions(projects, tmp_path / "out", dry_run=True)
        assert summary.imported == 1
        assert not (tmp_path / "out").exists()

    def test_empty_session_skipped(self, tmp_path):
        projects = tmp_path / "projects"
        _write_transcript(projects, [_user("x", isMeta=True)], session_id="empty")
        _write_transcript(projects, _session())
        summary = import_sessions(projects, tmp_path / "out")
        assert (summary.total, summary.skipped_empty, summary.imported) == (2, 1, 1)

    def test_date_filter(self, tmp_path):
        projects = tmp_path / "projects"
        _write_transcript(projects, _session())
        assert import_sessions(projects, tmp_path / "out", date_from="2026-10-06").skipped_filter == 1
        assert import_sessions(projects, tmp_path / "out", date_to="2026-10-04").skipped_filter == 1
        assert import_sessions(projects, tmp_path / "out", date_from="2026-10-05", date_to="2026-10-05").imported == 1

    def test_filename_collision_gets_suffix(self, tmp_path):
        projects = tmp_path / "projects"
        target = tmp_path / "out"
        _write_transcript(projects, _session(), session_id="a")
        _write_transcript(projects, _session(), session_id="b")
        import_sessions(projects, target)
        names = sorted(p.name for p in target.rglob("*.json"))
        assert names == ["2026-10-05_07-59-59.json", "2026-10-05_07-59-59_2.json"]

    def test_desktop_title_used(self, tmp_path):
        projects = tmp_path / "projects"
        desktop_dir = tmp_path / "desktop" / "org" / "acct"
        desktop_dir.mkdir(parents=True)
        (desktop_dir / "local_1.json").write_text(
            json.dumps({"sessionId": "local_1", "cliSessionId": SESSION_ID, "title": "From desktop"})
        )
        (desktop_dir / "broken.json").write_text("{")
        _write_transcript(projects, _session())
        import_sessions(projects, tmp_path / "out", desktop_sessions_dir=tmp_path / "desktop")
        conv = json.loads(next((tmp_path / "out").rglob("*.json")).read_text())
        assert conv["title"] == "From desktop"
        assert conv["metadata"]["desktop_session_id"] == "local_1"

    def test_error_is_reported(self, tmp_path):
        projects = tmp_path / "projects"
        path = _write_transcript(projects, _session())
        path.write_bytes(b"\xff\xfe")
        summary = import_sessions(projects, tmp_path / "out")
        assert summary.errors == 1
        assert summary.error_details[0].startswith("Error converting")
