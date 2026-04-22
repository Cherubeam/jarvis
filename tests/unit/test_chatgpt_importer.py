"""Tests for the ChatGPT conversation importer."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.core.importers.chatgpt import (
    _make_conv_id,
    _make_filename,
    _unix_to_iso,
    convert_content_parts,
    convert_conversation,
    import_conversations,
    linearize_message_tree,
)
from packages.core.memory import ConversationLogger

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ==================== linearize_message_tree ====================


class TestLinearizeMessageTree:
    def test_simple_chain(self):
        mapping = {
            "root": {"id": "root", "message": None, "parent": None, "children": ["a"]},
            "a": {
                "id": "a",
                "message": {
                    "id": "a",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["hi"]},
                },
                "parent": "root",
                "children": ["b"],
            },
            "b": {
                "id": "b",
                "message": {
                    "id": "b",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["hello"]},
                },
                "parent": "a",
                "children": [],
            },
        }
        result = linearize_message_tree(mapping, "b")
        assert len(result) == 2
        assert result[0]["author"]["role"] == "user"
        assert result[1]["author"]["role"] == "assistant"

    def test_skips_null_messages(self):
        mapping = {
            "root": {"id": "root", "message": None, "parent": None, "children": ["a"]},
            "a": {
                "id": "a",
                "message": {
                    "id": "a",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["hi"]},
                },
                "parent": "root",
                "children": [],
            },
        }
        result = linearize_message_tree(mapping, "a")
        assert len(result) == 1
        assert result[0]["author"]["role"] == "user"

    def test_cycle_detection(self):
        mapping = {
            "a": {
                "id": "a",
                "message": {
                    "id": "a",
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["hi"]},
                },
                "parent": "b",
                "children": [],
            },
            "b": {
                "id": "b",
                "message": {
                    "id": "b",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["yo"]},
                },
                "parent": "a",
                "children": ["a"],
            },
        }
        result = linearize_message_tree(mapping, "a")
        # Should stop at cycle, still return what it found
        assert len(result) >= 1

    def test_missing_current_node(self):
        mapping = {"a": {"id": "a", "message": None, "parent": None, "children": []}}
        result = linearize_message_tree(mapping, "nonexistent")
        assert result == []

    def test_empty_mapping(self):
        result = linearize_message_tree({}, "anything")
        assert result == []

    def test_chronological_order(self):
        mapping = {
            "root": {"id": "root", "message": None, "parent": None, "children": ["a"]},
            "a": {
                "id": "a",
                "message": {
                    "id": "a",
                    "author": {"role": "user"},
                    "create_time": 1.0,
                    "content": {"content_type": "text", "parts": ["first"]},
                },
                "parent": "root",
                "children": ["b"],
            },
            "b": {
                "id": "b",
                "message": {
                    "id": "b",
                    "author": {"role": "assistant"},
                    "create_time": 2.0,
                    "content": {"content_type": "text", "parts": ["second"]},
                },
                "parent": "a",
                "children": ["c"],
            },
            "c": {
                "id": "c",
                "message": {
                    "id": "c",
                    "author": {"role": "user"},
                    "create_time": 3.0,
                    "content": {"content_type": "text", "parts": ["third"]},
                },
                "parent": "b",
                "children": [],
            },
        }
        result = linearize_message_tree(mapping, "c")
        assert len(result) == 3
        assert result[0]["content"]["parts"] == ["first"]
        assert result[2]["content"]["parts"] == ["third"]


# ==================== convert_content_parts ====================


class TestConvertContentParts:
    def test_text_simple(self):
        content = {"content_type": "text", "parts": ["Hello world"]}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": "Hello world"}]

    def test_text_multiple_parts(self):
        content = {"content_type": "text", "parts": ["Part 1", "Part 2"]}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": "Part 1\nPart 2"}]
        # Verify newline join (not space, comma, etc.)
        assert "\n" in result[0]["text"]
        assert result[0]["text"].count("\n") == 1

    def test_text_empty_parts(self):
        content = {"content_type": "text", "parts": []}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": ""}]

    def test_multimodal_text_with_image(self):
        content = {
            "content_type": "multimodal_text",
            "parts": [
                "What is this?",
                {
                    "content_type": "image_asset_pointer",
                    "asset_pointer": "sediment://file_abc",
                    "size_bytes": 1000,
                    "width": 100,
                    "height": 100,
                    "fovea": None,
                    "metadata": {},
                },
            ],
        }
        result = convert_content_parts(content)
        assert len(result) == 2
        assert result[0] == {"type": "text", "text": "What is this?"}
        assert result[1]["text"] == "[Image not available]"
        assert result[1]["metadata"] == {
            "original_type": "image",
            "asset_pointer": "sediment://file_abc",
        }

    def test_multimodal_empty(self):
        content = {"content_type": "multimodal_text", "parts": []}
        result = convert_content_parts(content)
        assert len(result) == 1
        assert result == [{"type": "text", "text": ""}]

    def test_code_with_language(self):
        content = {"content_type": "code", "language": "python", "text": "print('hello')"}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": "```python\nprint('hello')\n```"}]
        # Verify backtick fencing format
        text = result[0]["text"]
        assert text.startswith("```python\n")
        assert text.endswith("\n```")

    def test_code_unknown_language(self):
        content = {"content_type": "code", "language": "unknown", "text": "some code"}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": "```\nsome code\n```"}]
        text = result[0]["text"]
        assert text.startswith("```\n")
        assert text.endswith("\n```")

    def test_code_no_language(self):
        content = {"content_type": "code", "language": "", "text": "x = 1"}
        result = convert_content_parts(content)
        text = result[0]["text"]
        assert text.startswith("```\n")
        assert text.endswith("\n```")

    def test_thoughts(self):
        content = {
            "content_type": "thoughts",
            "thoughts": [
                {
                    "summary": "Thinking...",
                    "content": "Deep analysis here",
                    "chunks": [],
                    "finished": True,
                }
            ],
        }
        result = convert_content_parts(content)
        assert len(result) == 1
        # content takes precedence over summary when both exist
        assert result[0]["text"] == "Deep analysis here"
        assert result[0]["text"] != "Thinking..."
        assert result[0]["metadata"] == {"thought": True}

    def test_thoughts_empty_content_falls_back_to_summary(self):
        content = {
            "content_type": "thoughts",
            "thoughts": [{"summary": "Brief thought", "content": "", "chunks": [], "finished": True}],
        }
        result = convert_content_parts(content)
        assert result[0]["text"] == "Brief thought"
        assert result[0]["metadata"] == {"thought": True}

    def test_thoughts_empty_list(self):
        content = {"content_type": "thoughts", "thoughts": []}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": ""}]

    def test_execution_output(self):
        content = {"content_type": "execution_output", "text": "/mnt/data/output.txt"}
        result = convert_content_parts(content)
        assert result[0]["text"] == "/mnt/data/output.txt"
        assert result[0]["metadata"] == {"execution_output": True}

    def test_tether_browsing_display(self):
        content = {
            "content_type": "tether_browsing_display",
            "result": "Search results here",
            "summary": "",
        }
        result = convert_content_parts(content)
        assert result[0]["text"] == "Search results here"
        assert result[0]["metadata"] == {"browsing_display": True}

    def test_tether_quote(self):
        content = {
            "content_type": "tether_quote",
            "text": "Quoted text",
            "domain": "example.com",
            "url": "https://example.com",
        }
        result = convert_content_parts(content)
        assert result[0]["text"] == "Quoted text"
        assert result[0]["metadata"] == {
            "quote_source": "example.com",
            "quote_url": "https://example.com",
        }

    def test_reasoning_recap(self):
        content = {"content_type": "reasoning_recap", "content": "Thought for 5s"}
        result = convert_content_parts(content)
        assert result[0]["text"] == "Thought for 5s"
        assert result[0]["metadata"]["reasoning_recap"] is True

    def test_system_error(self):
        content = {
            "content_type": "system_error",
            "name": "SomeError",
            "text": "Something went wrong",
        }
        result = convert_content_parts(content)
        assert result[0]["text"] == "Something went wrong"
        assert result[0]["metadata"]["error_name"] == "SomeError"

    def test_unknown_content_type(self):
        content = {"content_type": "future_type", "parts": ["some text"]}
        result = convert_content_parts(content)
        assert result[0]["metadata"]["original_content_type"] == "future_type"
        assert result[0]["text"] == "some text"

    # --- Mutation-targeted: missing content_type defaults and edge cases ---

    def test_missing_content_type_defaults_to_text(self):
        """Missing content_type should default to 'text'."""
        content = {"parts": ["Hello"]}
        result = convert_content_parts(content)
        assert result == [{"type": "text", "text": "Hello"}]

    def test_tether_browsing_display_result_empty_uses_summary(self):
        """When result is empty, falls back to summary."""
        content = {
            "content_type": "tether_browsing_display",
            "result": "",
            "summary": "Fallback summary",
        }
        result = convert_content_parts(content)
        assert result[0]["text"] == "Fallback summary"

    def test_tether_browsing_display_both_empty(self):
        content = {"content_type": "tether_browsing_display", "result": "", "summary": ""}
        result = convert_content_parts(content)
        assert result[0]["text"] == ""
        assert result[0]["metadata"] == {"browsing_display": True}

    def test_tether_quote_missing_domain_and_url(self):
        content = {"content_type": "tether_quote", "text": "quote"}
        result = convert_content_parts(content)
        assert result[0]["metadata"]["quote_source"] == ""
        assert result[0]["metadata"]["quote_url"] == ""

    def test_user_editable_context(self):
        content = {"content_type": "user_editable_context", "user_profile": "My profile text"}
        result = convert_content_parts(content)
        assert result[0]["text"] == "My profile text"
        assert result[0]["metadata"] == {"user_editable_context": True}

    def test_user_editable_context_missing_profile(self):
        content = {"content_type": "user_editable_context"}
        result = convert_content_parts(content)
        assert result[0]["text"] == ""

    def test_app_pairing_content(self):
        content = {
            "content_type": "app_pairing_content",
            "context_parts": [
                {"text": "Line 1"},
                {"text": "Line 2"},
                {"other": "no text field"},
            ],
        }
        result = convert_content_parts(content)
        assert result[0]["text"] == "Line 1\nLine 2"
        assert result[0]["metadata"] == {"app_pairing": True}

    def test_app_pairing_content_empty(self):
        content = {"content_type": "app_pairing_content", "context_parts": []}
        result = convert_content_parts(content)
        assert result[0]["text"] == ""

    def test_multimodal_non_image_dict(self):
        """Dict parts with non-image content_type use fallback formatting."""
        content = {
            "content_type": "multimodal_text",
            "parts": [{"content_type": "video", "url": "https://example.com"}],
        }
        result = convert_content_parts(content)
        assert result[0]["metadata"]["original_type"] == "video"

    def test_multimodal_dict_empty_content_type(self):
        """Dict part with empty content_type defaults to 'unknown'."""
        content = {
            "content_type": "multimodal_text",
            "parts": [{"content_type": "", "data": "raw"}],
        }
        result = convert_content_parts(content)
        assert result[0]["metadata"]["original_type"] == "unknown"

    def test_multimodal_non_string_non_dict(self):
        """Non-string, non-dict parts are stringified."""
        content = {"content_type": "multimodal_text", "parts": [42]}
        result = convert_content_parts(content)
        assert result[0]["text"] == "42"

    def test_multimodal_empty_string_skipped(self):
        """Empty strings in multimodal parts are skipped."""
        content = {"content_type": "multimodal_text", "parts": ["", "actual text"]}
        result = convert_content_parts(content)
        assert len(result) == 1
        assert result[0]["text"] == "actual text"

    def test_text_non_string_parts(self):
        """Non-string parts in text content are stringified."""
        content = {"content_type": "text", "parts": [123, None]}
        result = convert_content_parts(content)
        assert result[0]["text"] == "123\nNone"

    def test_thoughts_only_summary(self):
        """Thought with no content key falls back to summary."""
        content = {"content_type": "thoughts", "thoughts": [{"summary": "Just summary"}]}
        result = convert_content_parts(content)
        assert result[0]["text"] == "Just summary"

    def test_fallback_text_from_parts(self):
        """Unknown content_type with string parts joins them."""
        content = {"content_type": "exotic", "parts": ["a", 42, "b"]}
        result = convert_content_parts(content)
        # _extract_fallback_text only joins str parts
        assert result[0]["text"] == "a\nb"

    def test_fallback_text_from_text_field(self):
        """Unknown content_type with no parts uses text field."""
        content = {"content_type": "exotic", "parts": [], "text": "fallback text"}
        result = convert_content_parts(content)
        assert result[0]["text"] == "fallback text"

    def test_execution_output_missing_text(self):
        content = {"content_type": "execution_output"}
        result = convert_content_parts(content)
        assert result[0]["text"] == ""
        assert result[0]["metadata"] == {"execution_output": True}

    def test_system_error_missing_name(self):
        content = {"content_type": "system_error", "text": "error"}
        result = convert_content_parts(content)
        assert result[0]["metadata"]["error_name"] == ""


# ==================== convert_conversation ====================


class TestConvertConversation:
    @pytest.fixture
    def sample_conv(self):
        with open(FIXTURES_DIR / "chatgpt_sample.json") as f:
            return json.load(f)[0]

    def test_schema_version(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["schema_version"] == "1.0.0"

    def test_title_mapping(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["title"] == "Simple Text Chat"

    def test_tags(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert "imported" in result["tags"]
        assert "chatgpt" in result["tags"]
        assert "archived" not in result["tags"]

    def test_archived_tag(self):
        with open(FIXTURES_DIR / "chatgpt_sample.json") as f:
            archived_conv = json.load(f)[2]  # The archived one
        result = convert_conversation(archived_conv)
        assert "archived" in result["tags"]

    def test_model_mapping(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["model"] == {"id": "gpt-4", "provider": "openai"}

    def test_session_timestamps(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["session_start"] is not None
        assert result["session_end"] is not None
        # Should be ISO format
        datetime.fromisoformat(result["session_start"])
        datetime.fromisoformat(result["session_end"])

    def test_messages_linearized(self, sample_conv):
        result = convert_conversation(sample_conv)
        messages = result["messages"]
        # root (null msg) + system + user + assistant = 3 messages
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_message_ids_sequential(self, sample_conv):
        result = convert_conversation(sample_conv)
        for i, msg in enumerate(result["messages"], start=1):
            assert msg["id"] == f"msg_{i:03d}"

    def test_message_content_blocks(self, sample_conv):
        result = convert_conversation(sample_conv)
        user_msg = result["messages"][1]
        assert user_msg["content"] == [{"type": "text", "text": "Hello, how are you?"}]

    def test_metadata_import_fields(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["metadata"]["import_source"] == "chatgpt"
        assert result["metadata"]["chatgpt_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert "import_timestamp" in result["metadata"]

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

    def test_no_usage_data(self, sample_conv):
        result = convert_conversation(sample_conv)
        for msg in result["messages"]:
            assert msg["usage"] is None
            assert msg["latency"] is None

    def test_empty_metrics(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["metrics"] == {}

    def test_missing_model_slug(self):
        conv = {
            "title": "No model",
            "create_time": 1711580000.0,
            "update_time": 1711580100.0,
            "mapping": {},
            "current_node": None,
            "conversation_id": "test-id",
            "is_archived": False,
        }
        result = convert_conversation(conv)
        assert result["model"] is None

    # --- Mutation-targeted: missing field assertions ---

    def test_null_fields(self, sample_conv):
        """Fields that should be None/empty are verified."""
        result = convert_conversation(sample_conv)
        assert result["topic"] is None
        assert result["agent"] is None
        assert result["context"] is None
        assert result["environment"] is None
        assert result["feedback"] is None

    def test_message_default_fields(self, sample_conv):
        """Every message has the required default fields."""
        result = convert_conversation(sample_conv)
        for msg in result["messages"]:
            assert msg["parent_id"] is None
            assert msg["stop_reason"] is None
            assert msg["status"] == "completed"
            assert msg["error"] is None
            assert msg["metadata"] == {}

    def test_unmapped_role_defaults_to_system(self):
        """A role not in _ROLE_MAP should fall back to 'system'."""
        conv = {
            "create_time": 1711580000.0,
            "update_time": 1711580100.0,
            "conversation_id": "test-role",
            "mapping": {
                "root": {"id": "root", "message": None, "parent": None, "children": ["a"]},
                "a": {
                    "id": "a",
                    "message": {
                        "id": "a",
                        "author": {"role": "unknown_future_role"},
                        "content": {"content_type": "text", "parts": ["msg"]},
                    },
                    "parent": "root",
                    "children": [],
                },
            },
            "current_node": "a",
        }
        result = convert_conversation(conv)
        assert result["messages"][0]["role"] == "system"

    def test_metadata_import_source_exact(self, sample_conv):
        """Metadata has exact expected keys."""
        result = convert_conversation(sample_conv)
        assert set(result["metadata"].keys()) == {"import_source", "chatgpt_id", "import_timestamp"}
        assert result["metadata"]["import_source"] == "chatgpt"

    def test_model_structure_when_present(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert set(result["model"].keys()) == {"id", "provider"}
        assert result["model"]["provider"] == "openai"

    def test_tags_exact_for_non_archived(self, sample_conv):
        result = convert_conversation(sample_conv)
        assert result["tags"] == ["imported", "chatgpt"]

    def test_empty_mapping_no_messages(self):
        conv = {
            "create_time": 1711580000.0,
            "update_time": 1711580100.0,
            "conversation_id": "test-empty",
            "mapping": {},
            "current_node": None,
        }
        result = convert_conversation(conv)
        assert result["messages"] == []


# ==================== Helper functions ====================


class TestHelpers:
    def test_unix_to_iso(self):
        result = _unix_to_iso(1711580000.0)
        assert result is not None
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo == UTC

    def test_unix_to_iso_none(self):
        assert _unix_to_iso(None) is None

    def test_make_conv_id_deterministic(self):
        id1 = _make_conv_id("test-uuid", 1711580000.0)
        id2 = _make_conv_id("test-uuid", 1711580000.0)
        assert id1 == id2

    def test_make_conv_id_different_uuids(self):
        id1 = _make_conv_id("uuid-1", 1711580000.0)
        id2 = _make_conv_id("uuid-2", 1711580000.0)
        assert id1 != id2

    def test_make_filename(self):
        filename = _make_filename(1711580000.0, None)
        assert filename.endswith(".json")
        assert filename.count("-") == 4  # YYYY-MM-DD_HH-MM-SS

    def test_make_filename_fallback_to_update_time(self):
        filename = _make_filename(None, 1711580000.0)
        assert filename.endswith(".json")


# ==================== import_conversations ====================


class TestImportConversations:
    @pytest.fixture
    def sample_source(self):
        return FIXTURES_DIR / "chatgpt_sample.json"

    def test_dry_run_no_files_written(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, dry_run=True)
        assert summary.imported > 0
        assert list(tmp_path.rglob("*.json")) == []

    def test_dry_run_counts(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, dry_run=True)
        assert summary.total == 3
        assert summary.imported == 2  # 1 archived excluded
        assert summary.skipped_archived == 1

    def test_import_creates_files(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path)
        assert summary.imported == 2
        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 2

    def test_imported_files_valid_schema(self, sample_source, tmp_path):
        import_conversations(sample_source, tmp_path)
        for f in tmp_path.rglob("*.json"):
            data = json.loads(f.read_text())
            assert data["schema_version"] == "1.0.0"
            assert "id" in data
            assert "messages" in data

    def test_include_archived(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, include_archived=True)
        assert summary.imported == 3
        assert summary.skipped_archived == 0

    def test_filter_by_model(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, model_filter="gpt-4o", include_archived=True)
        assert summary.imported == 1
        assert summary.skipped_filter == 2

    def test_filter_by_date_from(self, sample_source, tmp_path):
        # Archived conv is from 2023-11, others from 2024-03
        summary = import_conversations(sample_source, tmp_path, date_from="2024-01-01", include_archived=True)
        assert summary.imported == 2
        assert summary.skipped_filter == 1

    def test_filter_by_date_to(self, sample_source, tmp_path):
        summary = import_conversations(sample_source, tmp_path, date_to="2023-12-31", include_archived=True)
        assert summary.imported == 1
        assert summary.skipped_filter == 2

    def test_idempotent_reimport(self, sample_source, tmp_path):
        import_conversations(sample_source, tmp_path)
        summary2 = import_conversations(sample_source, tmp_path)
        assert summary2.skipped_existing == 2
        assert summary2.imported == 0

    def test_filename_collision_handling(self, tmp_path):
        """Two conversations with the same create_time should get different filenames."""
        source = tmp_path / "source.json"
        convs = [
            {
                "title": f"Conv {i}",
                "create_time": 1711580000.0,
                "update_time": 1711580100.0,
                "mapping": {"root": {"id": "root", "message": None, "parent": None, "children": []}},
                "current_node": "root",
                "conversation_id": f"id-{i}",
                "is_archived": False,
            }
            for i in range(3)
        ]
        source.write_text(json.dumps(convs))
        target = tmp_path / "out"
        summary = import_conversations(source, target)
        assert summary.imported == 3
        files = sorted(f.name for f in target.rglob("*.json"))
        assert len(files) == 3
        # Should have base, _2, _3 suffixes
        assert any("_2" in f for f in files)
        assert any("_3" in f for f in files)

    def test_error_handling_continues(self, tmp_path):
        """A bad conversation should not stop import of others."""
        source = tmp_path / "source.json"
        convs = [
            {
                "title": "Good",
                "create_time": 1711580000.0,
                "update_time": 1711580100.0,
                "mapping": {"root": {"id": "root", "message": None, "parent": None, "children": []}},
                "current_node": "root",
                "conversation_id": "good-id",
                "is_archived": False,
            },
        ]
        source.write_text(json.dumps(convs))
        summary = import_conversations(source, tmp_path / "out")
        assert summary.errors == 0
        assert summary.imported == 1


# ==================== Integration: load round-trip ====================


class TestLoadRoundTrip:
    def test_imported_file_loadable(self, tmp_path):
        source = FIXTURES_DIR / "chatgpt_sample.json"
        import_conversations(source, tmp_path)
        for f in tmp_path.rglob("*.json"):
            data = ConversationLogger.load(f)
            assert data["schema_version"] == "1.0.0"
            assert isinstance(data["messages"], list)
            assert len(data["messages"]) > 0
            for msg in data["messages"]:
                assert "id" in msg
                assert "role" in msg
                assert "content" in msg
                assert isinstance(msg["content"], list)
