"""Tests for the Claude conversation importer."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from packages.core.importers.claude import (
    _parse_iso,
    convert_content_blocks,
    convert_conversation,
    import_conversations,
    parse_title_prefixes,
    update_conversation,
)
from packages.core.importers.common import ImportSummary, make_conv_id, make_filename
from packages.core.memory import ConversationLogger


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ==================== convert_content_blocks ====================


class TestConvertContentBlocks:
    def test_text_simple(self):
        blocks = [{"type": "text", "text": "Hello world"}]
        result = convert_content_blocks(blocks)
        assert result == [{"type": "text", "text": "Hello world"}]

    def test_text_multiple_blocks(self):
        blocks = [
            {"type": "text", "text": "Part 1"},
            {"type": "text", "text": "Part 2"},
        ]
        result = convert_content_blocks(blocks)
        assert len(result) == 2
        assert result[0]["text"] == "Part 1"
        assert result[1]["text"] == "Part 2"

    def test_text_empty_whitespace_skipped(self):
        blocks = [{"type": "text", "text": "\n\n"}]
        result = convert_content_blocks(blocks)
        # Should produce empty fallback since all blocks were skipped
        assert result == [{"type": "text", "text": ""}]

    def test_text_with_whitespace_around_content(self):
        blocks = [{"type": "text", "text": "  Hello  "}]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == "  Hello  "

    def test_thinking_block(self):
        blocks = [{"type": "thinking", "thinking": "Let me analyze this carefully."}]
        result = convert_content_blocks(blocks)
        assert len(result) == 1
        assert result[0]["text"] == "Let me analyze this carefully."
        assert result[0]["metadata"]["thought"] is True

    def test_thinking_empty_skipped(self):
        blocks = [{"type": "thinking", "thinking": ""}]
        result = convert_content_blocks(blocks)
        assert result == [{"type": "text", "text": ""}]

    def test_tool_use_block(self):
        blocks = [
            {
                "type": "tool_use",
                "name": "web_search",
                "input": {"query": "test"},
            }
        ]
        result = convert_content_blocks(blocks)
        assert len(result) == 1
        assert result[0]["text"] == "[Tool: web_search]"
        assert result[0]["metadata"]["tool_use"] is True
        assert result[0]["metadata"]["tool_name"] == "web_search"
        assert result[0]["metadata"]["tool_input"] == {"query": "test"}

    def test_tool_use_missing_name(self):
        blocks = [{"type": "tool_use", "input": {}}]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == "[Tool: unknown_tool]"
        assert result[0]["metadata"]["tool_name"] == "unknown_tool"
        assert result[0]["metadata"]["tool_input"] == {}

    def test_tool_result_block(self):
        blocks = [
            {
                "type": "tool_result",
                "name": "web_search",
                "content": [{"type": "text", "text": "Search results here."}],
                "is_error": False,
            }
        ]
        result = convert_content_blocks(blocks)
        assert len(result) == 1
        assert result[0]["text"] == "Search results here."
        assert result[0]["metadata"]["tool_result"] is True
        assert result[0]["metadata"]["tool_name"] == "web_search"
        assert result[0]["metadata"]["is_error"] is False

    def test_tool_result_error(self):
        blocks = [
            {
                "type": "tool_result",
                "name": "code_exec",
                "content": [{"type": "text", "text": "Error: timeout"}],
                "is_error": True,
            }
        ]
        result = convert_content_blocks(blocks)
        assert result[0]["metadata"]["is_error"] is True

    def test_tool_result_empty_content(self):
        blocks = [
            {
                "type": "tool_result",
                "name": "tool",
                "content": [],
                "is_error": False,
            }
        ]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == ""
        assert result[0]["metadata"]["tool_result"] is True

    def test_token_budget_skipped(self):
        blocks = [{"type": "token_budget"}]
        result = convert_content_blocks(blocks)
        # token_budget is skipped, so we get the empty fallback
        assert result == [{"type": "text", "text": ""}]

    def test_token_budget_among_others(self):
        blocks = [
            {"type": "text", "text": "Before"},
            {"type": "token_budget"},
            {"type": "text", "text": "After"},
        ]
        result = convert_content_blocks(blocks)
        assert len(result) == 2
        assert result[0]["text"] == "Before"
        assert result[1]["text"] == "After"

    def test_unknown_block_type(self):
        blocks = [{"type": "future_type", "text": "Some content"}]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == "Some content"
        assert result[0]["metadata"]["original_content_type"] == "future_type"

    def test_attachments(self):
        blocks = [{"type": "text", "text": "Analyze this."}]
        attachments = [
            {
                "file_name": "doc.txt",
                "file_size": 500,
                "file_type": "txt",
                "extracted_content": "File content here.",
            }
        ]
        result = convert_content_blocks(blocks, attachments=attachments)
        assert len(result) == 2
        assert result[1]["text"] == "File content here."
        assert result[1]["metadata"]["attachment"] is True
        assert result[1]["metadata"]["file_name"] == "doc.txt"
        assert result[1]["metadata"]["file_size"] == 500

    def test_attachment_empty_content_skipped(self):
        blocks = [{"type": "text", "text": "Hi"}]
        attachments = [
            {
                "file_name": "",
                "file_size": 0,
                "file_type": "txt",
                "extracted_content": "",
            }
        ]
        result = convert_content_blocks(blocks, attachments=attachments)
        assert len(result) == 1  # Only the text block

    def test_files_generated(self):
        blocks = [{"type": "text", "text": "Here is the result."}]
        files = [{"file_name": "output.png"}]
        result = convert_content_blocks(blocks, files=files)
        assert len(result) == 2
        assert result[1]["text"] == "[Generated file: output.png]"
        assert result[1]["metadata"]["generated_file"] is True
        assert result[1]["metadata"]["file_name"] == "output.png"

    def test_files_empty_name_skipped(self):
        blocks = [{"type": "text", "text": "Hi"}]
        files = [{"file_name": ""}]
        result = convert_content_blocks(blocks, files=files)
        assert len(result) == 1

    def test_empty_blocks_returns_fallback(self):
        result = convert_content_blocks([])
        assert result == [{"type": "text", "text": ""}]

    def test_mixed_blocks(self):
        blocks = [
            {"type": "thinking", "thinking": "Let me think..."},
            {"type": "tool_use", "name": "search", "input": {"q": "test"}},
            {
                "type": "tool_result",
                "name": "search",
                "content": [{"type": "text", "text": "Results"}],
                "is_error": False,
            },
            {"type": "token_budget"},
            {"type": "text", "text": "Here's what I found."},
        ]
        result = convert_content_blocks(blocks)
        assert len(result) == 4  # thinking + tool_use + tool_result + text (token_budget skipped)
        assert result[0]["metadata"]["thought"] is True
        assert result[1]["metadata"]["tool_use"] is True
        assert result[2]["metadata"]["tool_result"] is True
        assert result[3]["text"] == "Here's what I found."

    # --- Mutation-targeted: metadata dict key assertions ---

    def test_tool_use_metadata_exact_keys(self):
        blocks = [{"type": "tool_use", "name": "search", "input": {"q": "test"}}]
        result = convert_content_blocks(blocks)
        assert set(result[0]["metadata"].keys()) == {"tool_use", "tool_name", "tool_input"}

    def test_tool_result_metadata_exact_keys(self):
        blocks = [{"type": "tool_result", "name": "search", "content": [], "is_error": False}]
        result = convert_content_blocks(blocks)
        assert set(result[0]["metadata"].keys()) == {"tool_result", "tool_name", "is_error"}

    def test_tool_result_missing_name_and_is_error(self):
        """Defaults: name='unknown_tool', is_error=False when fields missing."""
        blocks = [{"type": "tool_result", "content": []}]
        result = convert_content_blocks(blocks)
        assert result[0]["metadata"]["tool_name"] == "unknown_tool"
        assert result[0]["metadata"]["is_error"] is False

    def test_tool_result_string_nested_content(self):
        """Nested content can be plain strings (not just dicts)."""
        blocks = [
            {"type": "tool_result", "name": "t", "content": ["plain text"], "is_error": False}
        ]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == "plain text"

    def test_tool_result_multiple_nested_text_joined(self):
        blocks = [
            {
                "type": "tool_result",
                "name": "t",
                "is_error": False,
                "content": [
                    {"type": "text", "text": "line1"},
                    {"type": "text", "text": "line2"},
                ],
            }
        ]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == "line1\nline2"

    def test_attachment_metadata_exact_keys(self):
        blocks = []
        attachments = [
            {
                "file_name": "doc.txt",
                "file_size": 100,
                "file_type": "txt",
                "extracted_content": "text",
            }
        ]
        result = convert_content_blocks(blocks, attachments=attachments)
        assert set(result[0]["metadata"].keys()) == {
            "attachment",
            "file_name",
            "file_size",
            "file_type",
        }

    def test_generated_file_metadata_exact_keys(self):
        blocks = []
        files = [{"file_name": "out.png"}]
        result = convert_content_blocks(blocks, files=files)
        assert set(result[0]["metadata"].keys()) == {"generated_file", "file_name"}

    def test_thinking_metadata_exact_keys(self):
        blocks = [{"type": "thinking", "thinking": "hmm"}]
        result = convert_content_blocks(blocks)
        assert set(result[0]["metadata"].keys()) == {"thought"}

    def test_unknown_type_text_fallback_to_thinking(self):
        """Unknown block type falls back to 'thinking' field if 'text' is missing."""
        blocks = [{"type": "exotic", "thinking": "deep thought"}]
        result = convert_content_blocks(blocks)
        assert result[0]["text"] == "deep thought"

    def test_unknown_type_empty_text_skipped(self):
        """Unknown block type with only whitespace text is skipped."""
        blocks = [{"type": "exotic", "text": "  \n  "}]
        result = convert_content_blocks(blocks)
        assert result == [{"type": "text", "text": ""}]


# ==================== convert_conversation ====================


class TestConvertConversation:
    @pytest.fixture
    def sample_conv(self):
        with open(FIXTURES_DIR / "claude_sample.json") as f:
            return json.load(f)[0]

    def test_schema_version(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["schema_version"] == "1.0.0"

    def test_title_mapping(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["title"] == "Simple Text Chat"

    def test_tags(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["tags"] == ["imported", "claude"]

    def test_model_is_none(self, sample_conv):
        """Claude export doesn't include model info."""
        result = convert_conversation(sample_conv)
        assert result["model"] is None

    def test_session_timestamps(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["session_start"] == "2025-12-10T10:30:00.000000Z"
        assert result["session_end"] == "2025-12-10T10:35:00.000000Z"

    def test_messages_count(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert len(result["messages"]) == 2

    def test_message_roles_human_maps_to_user(self, sample_conv):
        """Verify human→user and assistant→assistant role mapping."""
        result = convert_conversation(sample_conv)
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["role"] == "assistant"

    def test_unknown_sender_maps_to_system(self):
        """Verify unknown sender role falls back to 'system'."""
        conv = {
            "uuid": "test-uuid-role",
            "name": "Role test",
            "created_at": "2025-12-10T10:30:00.000000Z",
            "updated_at": "2025-12-10T10:30:00.000000Z",
            "chat_messages": [
                {
                    "sender": "unknown_sender",
                    "content": [{"type": "text", "text": "hello"}],
                    "created_at": "2025-12-10T10:30:00.000000Z",
                    "updated_at": "2025-12-10T10:30:00.000000Z",
                },
            ],
        }
        result = convert_conversation(conv)
        assert result["messages"][0]["role"] == "system"

    def test_message_ids_sequential(self, sample_conv):
        result = convert_conversation(sample_conv)
        for i, msg in enumerate(result["messages"], start=1):
            assert msg["id"] == f"msg_{i:03d}"

    def test_message_content_blocks(self, sample_conv):
        result = convert_conversation(sample_conv)
        user_msg = result["messages"][0]
        assert user_msg["content"] == [{"type": "text", "text": "Hello, how are you?"}]

    def test_metadata_import_fields(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["metadata"]["import_source"] == "claude"
        assert result["metadata"]["claude_id"] == "aaaa1111-bbbb-cccc-dddd-eeeeeeee0001"
        assert result["metadata"]["claude_summary"] == "A simple text conversation."
        assert isinstance(result["metadata"]["import_timestamp"], str)
        assert "original_title" not in result["metadata"]  # No prefix, no original_title

    def test_conversation_top_level_keys(self, sample_conv):
        """Verify all required top-level keys are present."""
        result = convert_conversation(sample_conv)
        expected_keys = {
            "schema_version",
            "id",
            "title",
            "topic",
            "tags",
            "session_start",
            "session_end",
            "model",
            "agent",
            "context",
            "metrics",
            "environment",
            "messages",
            "feedback",
            "metadata",
        }
        assert set(result.keys()) == expected_keys
        assert result["topic"] is None
        assert result["model"] is None
        assert result["agent"] is None
        assert result["context"] is None
        assert result["environment"] is None
        assert result["feedback"] is None

    def test_deterministic_conv_id(self, sample_conv):
        """Same input should produce same conv_id."""
        result1 = convert_conversation(sample_conv)
        result2 = convert_conversation(sample_conv)
        assert result1["id"] == result2["id"]

    def test_conv_id_format(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["id"].startswith("conv_")
        parts = result["id"].split("_")
        assert len(parts) == 4
        assert len(parts[3]) == 4  # 4 hex chars

    def test_message_structure_complete(self, sample_conv):
        """Every message has all required keys with correct types."""
        result = convert_conversation(sample_conv)
        expected_keys = {
            "id",
            "parent_id",
            "role",
            "timestamp",
            "content",
            "usage",
            "latency",
            "stop_reason",
            "status",
            "error",
            "metadata",
        }
        for msg in result["messages"]:
            assert set(msg.keys()) == expected_keys
            assert msg["usage"] is None
            assert msg["latency"] is None
            assert msg["stop_reason"] is None
            assert msg["status"] == "completed"
            assert msg["error"] is None
            assert msg["metadata"] == {}
            assert msg["parent_id"] is None
            assert isinstance(msg["content"], list)

    def test_empty_metrics(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["metrics"] == {}

    def test_thinking_and_attachments_conversation(self):
        with open(FIXTURES_DIR / "claude_sample.json") as f:
            conv = json.load(f)[1]  # Thinking and Attachments conversation
        result = convert_conversation(conv)
        # 4 messages: human (with attachment) + assistant (thinking+text+file) + human + assistant (tool_use+tool_result+token_budget+text)
        assert len(result["messages"]) == 4
        # First human message should have attachment content
        human_msg = result["messages"][0]
        assert any("attachment" in (b.get("metadata") or {}) for b in human_msg["content"])
        # Second message (assistant) should have thinking block
        assistant_msg = result["messages"][1]
        assert any((b.get("metadata") or {}).get("thought") for b in assistant_msg["content"])
        # Should have generated file
        assert any(
            (b.get("metadata") or {}).get("generated_file") for b in assistant_msg["content"]
        )

    def test_missing_timestamps(self):
        conv = {
            "uuid": "test-uuid-no-ts",
            "name": "No timestamps",
            "created_at": None,
            "updated_at": None,
            "chat_messages": [],
        }
        result = convert_conversation(conv)
        assert result["id"].startswith("conv_")
        assert result["messages"] == []


# ==================== Helper functions ====================


class TestHelpers:
    def test_parse_iso_valid(self):
        dt = _parse_iso("2025-12-10T10:30:00.000000Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.tzinfo is not None

    def test_parse_iso_none(self):
        assert _parse_iso(None) is None

    def test_parse_iso_empty(self):
        assert _parse_iso("") is None

    def test_parse_iso_no_timezone(self):
        dt = _parse_iso("2025-12-10T10:30:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc


# ==================== Common utilities ====================


class TestCommonUtilities:
    def test_make_conv_id_deterministic(self):
        dt = datetime(2025, 12, 10, 10, 30, 0, tzinfo=timezone.utc)
        id1 = make_conv_id("test-uuid", dt)
        id2 = make_conv_id("test-uuid", dt)
        assert id1 == id2

    def test_make_conv_id_different_uuids(self):
        dt = datetime(2025, 12, 10, 10, 30, 0, tzinfo=timezone.utc)
        id1 = make_conv_id("uuid-1", dt)
        id2 = make_conv_id("uuid-2", dt)
        assert id1 != id2

    def test_make_conv_id_format(self):
        dt = datetime(2025, 12, 10, 10, 30, 0, tzinfo=timezone.utc)
        conv_id = make_conv_id("test-uuid", dt)
        assert conv_id.startswith("conv_20251210_103000_")
        parts = conv_id.split("_")
        assert len(parts) == 4
        assert len(parts[3]) == 4

    def test_make_filename(self):
        dt = datetime(2025, 12, 10, 10, 30, 0, tzinfo=timezone.utc)
        filename = make_filename(dt)
        assert filename == "2025-12-10_10-30-00.json"

    def test_make_filename_format(self):
        dt = datetime(2025, 1, 5, 8, 5, 3, tzinfo=timezone.utc)
        filename = make_filename(dt)
        assert filename.endswith(".json")
        assert filename.count("-") == 4

    def test_import_summary_defaults(self):
        s = ImportSummary()
        assert s.total == 0
        assert s.imported == 0
        assert s.skipped_existing == 0
        assert s.skipped_archived == 0
        assert s.skipped_filter == 0
        assert s.updated == 0
        assert s.errors == 0
        assert s.error_details == []


# ==================== import_conversations ====================


class TestImportConversations:
    @pytest.fixture
    def sample_source(self):
        return FIXTURES_DIR / "claude_sample.json"

    def test_dry_run_no_files_written(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, dry_run=True)
        assert summary.imported > 0
        assert list(tmp_path.rglob("*.json")) == []

    def test_dry_run_counts(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, dry_run=True)
        assert summary.total == 5
        assert summary.imported == 5

    def test_import_creates_files(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path)
        assert summary.imported == 5
        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 5

    def test_imported_files_valid_schema(self, sample_source, tmp_path):
        import_conversations(sample_source, tmp_path)
        for f in tmp_path.rglob("*.json"):
            data = json.loads(f.read_text())
            assert data["schema_version"] == "1.0.0"
            assert "id" in data
            assert "messages" in data

    def test_filter_by_date_from(self, sample_source, tmp_path):
        # Old conv is from 2024-06, others from 2025-12
        summary = import_conversations(sample_source, tmp_path, date_from="2025-01-01")
        assert summary.imported == 4
        assert summary.skipped_filter == 1

    def test_filter_by_date_to(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, date_to="2024-12-31")
        assert summary.imported == 1
        assert summary.skipped_filter == 4

    def test_filter_by_date_range(self, sample_source, tmp_path):
        summary = import_conversations(
            sample_source, tmp_path, date_from="2025-12-10", date_to="2025-12-10"
        )
        assert summary.imported == 1
        assert summary.skipped_filter == 4

    def test_idempotent_reimport(self, sample_source, tmp_path):
        summary1 = import_conversations(sample_source, tmp_path)
        summary2 = import_conversations(sample_source, tmp_path)
        assert summary2.skipped_existing == 5
        assert summary2.imported == 0

    def test_filename_collision_handling(self, tmp_path):
        """Two conversations with the same created_at should get different filenames."""
        source = tmp_path / "source.json"
        convs = [
            {
                "uuid": f"uuid-collision-{i}",
                "name": f"Conv {i}",
                "created_at": "2025-12-10T10:30:00.000000Z",
                "updated_at": "2025-12-10T10:35:00.000000Z",
                "chat_messages": [],
            }
            for i in range(3)
        ]
        source.write_text(json.dumps(convs))
        target = tmp_path / "out"
        summary = import_conversations(source, target)
        assert summary.imported == 3
        files = sorted(f.name for f in target.rglob("*.json"))
        assert len(files) == 3
        assert any("_2" in f for f in files)
        assert any("_3" in f for f in files)

    def test_error_handling_continues(self, tmp_path):
        """A bad conversation should not stop import of others."""
        source = tmp_path / "source.json"
        convs = [
            {
                "uuid": "good-uuid",
                "name": "Good",
                "created_at": "2025-12-10T10:30:00.000000Z",
                "updated_at": "2025-12-10T10:35:00.000000Z",
                "chat_messages": [],
            },
        ]
        source.write_text(json.dumps(convs))
        summary = import_conversations(source, tmp_path / "out")
        assert summary.errors == 0
        assert summary.imported == 1


# ==================== Integration: load round-trip ====================


class TestLoadRoundTrip:
    def test_imported_file_loadable(self, tmp_path):
        source = FIXTURES_DIR / "claude_sample.json"
        import_conversations(source, tmp_path)
        for f in tmp_path.rglob("*.json"):
            data = ConversationLogger.load(f)
            assert data["schema_version"] == "1.0.0"
            assert isinstance(data["messages"], list)
            for msg in data["messages"]:
                assert "id" in msg
                assert "role" in msg
                assert "content" in msg
                assert isinstance(msg["content"], list)

    def test_imported_metadata_preserved(self, tmp_path):
        source = FIXTURES_DIR / "claude_sample.json"
        import_conversations(source, tmp_path)
        found_claude = False
        for f in tmp_path.rglob("*.json"):
            data = ConversationLogger.load(f)
            if data["metadata"].get("import_source") == "claude":
                found_claude = True
                assert "claude_id" in data["metadata"]
                assert "import_timestamp" in data["metadata"]
                assert "imported" in data["tags"]
                assert "claude" in data["tags"]
        assert found_claude

    def test_imported_tags_correct(self, tmp_path):
        source = FIXTURES_DIR / "claude_sample.json"
        import_conversations(source, tmp_path)
        for f in tmp_path.rglob("*.json"):
            data = ConversationLogger.load(f)
            assert "imported" in data["tags"]
            assert "claude" in data["tags"]


# ==================== Incremental sync ====================


def _make_claude_conv(
    uuid: str = "test-uuid-001",
    name: str = "My Chat",
    created_at: str = "2025-12-10T10:30:00.000000Z",
    updated_at: str = "2025-12-10T10:35:00.000000Z",
    messages: list[dict] | None = None,
) -> dict:
    """Helper to build a minimal Claude conversation dict."""
    if messages is None:
        messages = [
            {
                "sender": "human",
                "content": [{"type": "text", "text": "Hello"}],
                "created_at": "2025-12-10T10:30:00.000000Z",
                "updated_at": "2025-12-10T10:30:00.000000Z",
            },
            {
                "sender": "assistant",
                "content": [{"type": "text", "text": "Hi there!"}],
                "created_at": "2025-12-10T10:31:00.000000Z",
                "updated_at": "2025-12-10T10:31:00.000000Z",
            },
        ]
    return {
        "uuid": uuid,
        "name": name,
        "created_at": created_at,
        "updated_at": updated_at,
        "chat_messages": messages,
    }


def _import_and_get_path(claude_conv: dict, tmp_path: Path) -> Path:
    """Import a single Claude conv and return the written file path."""
    source = tmp_path / "source.json"
    source.write_text(json.dumps([claude_conv]))
    target = tmp_path / "out"
    import_conversations(source, target)
    files = list(target.rglob("*.json"))
    assert len(files) == 1
    return files[0]


class TestIncrementalSync:
    def test_update_appends_new_messages(self, tmp_path):
        """2 msgs → 4 msgs, verify all 4 present."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)

        # Add 2 more messages to the Claude conv
        conv["chat_messages"].extend(
            [
                {
                    "sender": "human",
                    "content": [{"type": "text", "text": "Follow-up question"}],
                    "created_at": "2025-12-10T10:32:00.000000Z",
                    "updated_at": "2025-12-10T10:32:00.000000Z",
                },
                {
                    "sender": "assistant",
                    "content": [{"type": "text", "text": "Here's the answer"}],
                    "created_at": "2025-12-10T10:33:00.000000Z",
                    "updated_at": "2025-12-10T10:33:00.000000Z",
                },
            ]
        )
        conv["updated_at"] = "2025-12-10T10:33:00.000000Z"

        changed = update_conversation(path, conv)
        assert changed is True

        data = json.loads(path.read_text())
        assert len(data["messages"]) == 4
        assert data["messages"][2]["content"][0]["text"] == "Follow-up question"
        assert data["messages"][3]["content"][0]["text"] == "Here's the answer"

    def test_update_title_sync(self, tmp_path):
        """Title change is synced; prefix is stripped, tag is added."""
        conv = _make_claude_conv(name="My Chat")
        path = _import_and_get_path(conv, tmp_path)

        conv["name"] = "[X] My Chat"
        changed = update_conversation(path, conv)
        assert changed is True

        data = json.loads(path.read_text())
        assert data["title"] == "My Chat"  # Prefix stripped
        assert "status:done" in data["tags"]
        assert data["metadata"]["original_title"] == "[X] My Chat"

    def test_update_no_change_skips(self, tmp_path):
        """Identical re-import returns False (no changes)."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)

        changed = update_conversation(path, conv)
        assert changed is False

    def test_update_session_end(self, tmp_path):
        """Newer updated_at replaces older session_end."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)

        conv["updated_at"] = "2025-12-10T12:00:00.000000Z"
        changed = update_conversation(path, conv)
        assert changed is True

        data = json.loads(path.read_text())
        assert data["session_end"] == "2025-12-10T12:00:00.000000Z"

    def test_update_no_message_removal(self, tmp_path):
        """If Claude has fewer messages, JARVIS keeps all its messages."""
        conv = _make_claude_conv()
        conv["chat_messages"].extend(
            [
                {
                    "sender": "human",
                    "content": [{"type": "text", "text": "Extra msg 1"}],
                    "created_at": "2025-12-10T10:32:00.000000Z",
                    "updated_at": "2025-12-10T10:32:00.000000Z",
                },
                {
                    "sender": "assistant",
                    "content": [{"type": "text", "text": "Extra msg 2"}],
                    "created_at": "2025-12-10T10:33:00.000000Z",
                    "updated_at": "2025-12-10T10:33:00.000000Z",
                },
            ]
        )
        path = _import_and_get_path(conv, tmp_path)
        data_before = json.loads(path.read_text())
        assert len(data_before["messages"]) == 4

        # Now "sync" with only 2 messages in Claude (simulating deletion)
        conv_fewer = _make_claude_conv()  # only 2 messages
        changed = update_conversation(path, conv_fewer)
        assert changed is False

        data_after = json.loads(path.read_text())
        assert len(data_after["messages"]) == 4  # All preserved

    def test_update_message_ids_continue_sequence(self, tmp_path):
        """New messages get sequential IDs continuing from existing."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)

        conv["chat_messages"].append(
            {
                "sender": "human",
                "content": [{"type": "text", "text": "Another question"}],
                "created_at": "2025-12-10T10:32:00.000000Z",
                "updated_at": "2025-12-10T10:32:00.000000Z",
            }
        )
        conv["updated_at"] = "2025-12-10T10:32:00.000000Z"

        update_conversation(path, conv)
        data = json.loads(path.read_text())
        assert data["messages"][0]["id"] == "msg_001"
        assert data["messages"][1]["id"] == "msg_002"
        assert data["messages"][2]["id"] == "msg_003"

    def test_update_dry_run(self, tmp_path):
        """Dry run detects changes but writes nothing."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)
        original_content = path.read_text()

        conv["name"] = "[X] My Chat"
        conv["chat_messages"].append(
            {
                "sender": "human",
                "content": [{"type": "text", "text": "New msg"}],
                "created_at": "2025-12-10T10:32:00.000000Z",
                "updated_at": "2025-12-10T10:32:00.000000Z",
            }
        )

        changed = update_conversation(path, conv, dry_run=True)
        assert changed is True
        assert path.read_text() == original_content  # File unchanged

    def test_update_sync_metadata(self, tmp_path):
        """last_sync_timestamp is set after update."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)

        conv["name"] = "Updated Title"
        update_conversation(path, conv)

        data = json.loads(path.read_text())
        assert "last_sync_timestamp" in data["metadata"]

    def test_incremental_sync_via_import(self, tmp_path):
        """Full round-trip: import, then re-import with new messages uses update path."""
        conv = _make_claude_conv()
        source = tmp_path / "source.json"
        source.write_text(json.dumps([conv]))
        target = tmp_path / "out"

        summary1 = import_conversations(source, target)
        assert summary1.imported == 1

        # Add messages and re-import
        conv["chat_messages"].append(
            {
                "sender": "human",
                "content": [{"type": "text", "text": "New question"}],
                "created_at": "2025-12-10T10:32:00.000000Z",
                "updated_at": "2025-12-10T10:32:00.000000Z",
            }
        )
        conv["updated_at"] = "2025-12-10T10:32:00.000000Z"
        source.write_text(json.dumps([conv]))

        summary2 = import_conversations(source, target)
        assert summary2.updated == 1
        assert summary2.skipped_existing == 0
        assert summary2.imported == 0

    def test_new_messages_have_complete_fields(self, tmp_path):
        """Appended messages have all required Jarvis fields."""
        conv = _make_claude_conv()
        path = _import_and_get_path(conv, tmp_path)

        conv["chat_messages"].append(
            {
                "sender": "human",
                "content": [{"type": "text", "text": "New"}],
                "created_at": "2025-12-10T10:32:00.000000Z",
                "updated_at": "2025-12-10T10:32:00.000000Z",
            }
        )
        conv["updated_at"] = "2025-12-10T10:32:00.000000Z"
        update_conversation(path, conv)

        data = json.loads(path.read_text())
        new_msg = data["messages"][2]
        assert new_msg["parent_id"] is None
        assert new_msg["usage"] is None
        assert new_msg["latency"] is None
        assert new_msg["stop_reason"] is None
        assert new_msg["status"] == "completed"
        assert new_msg["error"] is None
        assert new_msg["metadata"] == {}
        assert new_msg["role"] == "user"

    def test_update_replaces_status_tags(self, tmp_path):
        """Status tags are replaced, not accumulated."""
        conv = _make_claude_conv(name="[!] Important task")
        path = _import_and_get_path(conv, tmp_path)

        data1 = json.loads(path.read_text())
        assert "status:important" in data1["tags"]

        # Change status from [!] to [X]
        conv["name"] = "[X] Important task"
        update_conversation(path, conv)

        data2 = json.loads(path.read_text())
        assert "status:done" in data2["tags"]
        assert "status:important" not in data2["tags"]

    def test_update_summary_sync(self, tmp_path):
        """Claude summary changes are synced to metadata."""
        conv = _make_claude_conv()
        conv["summary"] = "Initial summary"
        path = _import_and_get_path(conv, tmp_path)

        conv["summary"] = "Updated summary"
        changed = update_conversation(path, conv)
        assert changed is True

        data = json.loads(path.read_text())
        assert data["metadata"]["claude_summary"] == "Updated summary"

    def test_update_removes_original_title_when_no_prefix(self, tmp_path):
        """When title no longer has prefix, original_title is removed."""
        conv = _make_claude_conv(name="[X] Task Done")
        path = _import_and_get_path(conv, tmp_path)

        data1 = json.loads(path.read_text())
        assert data1["metadata"]["original_title"] == "[X] Task Done"

        # Remove prefix
        conv["name"] = "Task Done"
        update_conversation(path, conv)

        data2 = json.loads(path.read_text())
        assert "original_title" not in data2["metadata"]


# ==================== parse_title_prefixes ====================


class TestParseTitlePrefixes:
    def test_no_prefix(self):
        title, tags = parse_title_prefixes("My Chat")
        assert title == "My Chat"
        assert tags == []

    def test_none_input(self):
        title, tags = parse_title_prefixes(None)
        assert title == ""
        assert tags == []

    def test_empty_string(self):
        title, tags = parse_title_prefixes("")
        assert title == ""
        assert tags == []

    def test_done_prefix(self):
        title, tags = parse_title_prefixes("[X] Completed Task")
        assert title == "Completed Task"
        assert tags == ["status:done"]

    def test_open_prefix(self):
        title, tags = parse_title_prefixes("[ ] Open Task")
        assert title == "Open Task"
        assert tags == ["status:open"]

    def test_important_prefix(self):
        title, tags = parse_title_prefixes("[!] Urgent Item")
        assert title == "Urgent Item"
        assert tags == ["status:important"]

    def test_in_progress_prefix(self):
        title, tags = parse_title_prefixes("[~] Working On It")
        assert title == "Working On It"
        assert tags == ["status:in-progress"]

    def test_topic_prefix(self):
        title, tags = parse_title_prefixes("[Teaser Note] My Post")
        assert title == "My Post"
        assert tags == ["topic:teaser note"]

    def test_multiple_prefixes_status_and_topic(self):
        title, tags = parse_title_prefixes("[X][Teaser Note] Technical literacy")
        assert title == "Technical literacy"
        assert tags == ["status:done", "topic:teaser note"]

    def test_multiple_status_prefixes(self):
        """Edge case: multiple status brackets. Both are added."""
        title, tags = parse_title_prefixes("[X][!] Something")
        assert title == "Something"
        assert "status:done" in tags
        assert "status:important" in tags

    def test_no_trailing_space_after_bracket(self):
        title, tags = parse_title_prefixes("[X]NoSpace")
        assert title == "NoSpace"
        assert tags == ["status:done"]

    def test_empty_brackets(self):
        """Empty brackets [] have no content match in status map, become topic:."""
        title, tags = parse_title_prefixes("[] Title")
        assert title == "Title"
        assert tags == ["topic:"]

    def test_bracket_in_middle_not_parsed(self):
        """Only leading brackets are parsed."""
        title, tags = parse_title_prefixes("Title [X] suffix")
        assert title == "Title [X] suffix"
        assert tags == []


# ==================== Prefix integration in convert/update ====================


class TestPrefixIntegration:
    def test_convert_strips_prefix_from_title(self):
        conv = _make_claude_conv(name="[X] Done Chat")
        result = convert_conversation(conv)
        assert result["title"] == "Done Chat"
        assert "status:done" in result["tags"]
        assert "imported" in result["tags"]
        assert "claude" in result["tags"]

    def test_convert_stores_original_title(self):
        conv = _make_claude_conv(name="[X] Done Chat")
        result = convert_conversation(conv)
        assert result["metadata"]["original_title"] == "[X] Done Chat"

    def test_convert_no_original_title_when_no_prefix(self):
        conv = _make_claude_conv(name="Plain Chat")
        result = convert_conversation(conv)
        assert "original_title" not in result["metadata"]

    def test_convert_stores_summary(self):
        with open(FIXTURES_DIR / "claude_sample.json") as f:
            conv = json.load(f)[0]
        result = convert_conversation(conv)
        assert result["metadata"]["claude_summary"] == "A simple text conversation."

    def test_convert_prefixed_fixture(self):
        with open(FIXTURES_DIR / "claude_sample.json") as f:
            conv = json.load(f)[3]  # [X] Completed Task Chat
        result = convert_conversation(conv)
        assert result["title"] == "Completed Task Chat"
        assert "status:done" in result["tags"]
        assert result["metadata"]["original_title"] == "[X] Completed Task Chat"
        assert result["metadata"]["claude_summary"] == "A completed task with a prefix."

    def test_convert_multi_prefix_fixture(self):
        with open(FIXTURES_DIR / "claude_sample.json") as f:
            conv = json.load(f)[4]  # [~][Teaser Note] Draft Post
        result = convert_conversation(conv)
        assert result["title"] == "Draft Post"
        assert "status:in-progress" in result["tags"]
        assert "topic:teaser note" in result["tags"]

    def test_update_syncs_prefix_tags(self, tmp_path):
        """Status tag changes from [~] to [X] on re-import."""
        conv = _make_claude_conv(name="[~] Working")
        path = _import_and_get_path(conv, tmp_path)

        data = json.loads(path.read_text())
        assert "status:in-progress" in data["tags"]

        conv["name"] = "[X] Working"
        changed = update_conversation(path, conv)
        assert changed is True

        data = json.loads(path.read_text())
        assert "status:done" in data["tags"]
        assert "status:in-progress" not in data["tags"]

    def test_update_clears_original_title_when_prefix_removed(self, tmp_path):
        conv = _make_claude_conv(name="[X] My Chat")
        path = _import_and_get_path(conv, tmp_path)

        data = json.loads(path.read_text())
        assert data["metadata"]["original_title"] == "[X] My Chat"

        conv["name"] = "My Chat"
        update_conversation(path, conv)

        data = json.loads(path.read_text())
        assert "original_title" not in data["metadata"]

    def test_update_syncs_summary(self, tmp_path):
        conv = _make_claude_conv()
        conv["summary"] = "Old summary"
        path = _import_and_get_path(conv, tmp_path)

        conv["summary"] = "Updated summary"
        changed = update_conversation(path, conv)
        assert changed is True

        data = json.loads(path.read_text())
        assert data["metadata"]["claude_summary"] == "Updated summary"

    def test_update_adds_topic_tags_additively(self, tmp_path):
        conv = _make_claude_conv(name="[X][Blog] My Post")
        path = _import_and_get_path(conv, tmp_path)

        data = json.loads(path.read_text())
        assert "topic:blog" in data["tags"]

        conv["name"] = "[X][Blog][Series] My Post"
        update_conversation(path, conv)

        data = json.loads(path.read_text())
        assert "topic:blog" in data["tags"]
        assert "topic:series" in data["tags"]

    def test_update_no_change_when_same_prefix(self, tmp_path):
        conv = _make_claude_conv(name="[X] My Chat")
        path = _import_and_get_path(conv, tmp_path)

        changed = update_conversation(path, conv)
        assert changed is False
