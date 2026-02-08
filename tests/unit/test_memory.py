"""
Unit tests for memory module.

Tests SessionMetrics, ConversationLogger, and schema v1.0.0 functionality.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from freezegun import freeze_time

# Try new import path first, fall back to old for backward compatibility
try:
    from packages.core.memory import (
        SessionMetrics, ConversationLogger, SCHEMA_VERSION,
        generate_conversation_id, hash_content,
        _normalize_content, _extract_text_from_content,
        migrate_conversation,
    )
except ImportError:
    from memory import SessionMetrics, ConversationLogger


@pytest.mark.unit
class TestGenerateConversationId:
    """Tests for generate_conversation_id()."""

    def test_format_pattern(self):
        """Test that ID matches conv_{YYYYMMDD}_{HHMMSS}_{6hex} pattern."""
        import re
        conv_id = generate_conversation_id()
        assert re.match(r"^conv_\d{8}_\d{6}_[0-9a-f]{6}$", conv_id)

    def test_starts_with_conv_prefix(self):
        """Test that ID starts with conv_ prefix."""
        conv_id = generate_conversation_id()
        assert conv_id.startswith("conv_")

    @freeze_time("2026-02-06 14:30:22")
    def test_contains_date_and_time(self):
        """Test that ID contains correct date and time components."""
        conv_id = generate_conversation_id()
        assert conv_id.startswith("conv_20260206_143022_")

    def test_uniqueness(self):
        """Test that consecutive IDs are unique (hex suffix differs)."""
        ids = {generate_conversation_id() for _ in range(100)}
        assert len(ids) == 100


@pytest.mark.unit
class TestHashContent:
    """Tests for hash_content()."""

    def test_returns_16_hex_chars(self):
        """Test that hash is 16 hex characters."""
        import re
        result = hash_content("test")
        assert re.match(r"^[0-9a-f]{16}$", result)

    def test_deterministic(self):
        """Test that same input produces same hash."""
        assert hash_content("hello") == hash_content("hello")

    def test_different_inputs_different_hashes(self):
        """Test that different inputs produce different hashes."""
        assert hash_content("hello") != hash_content("world")


@pytest.mark.unit
class TestNormalizeContent:
    """Tests for _normalize_content()."""

    def test_string_wrapped_in_text_block(self):
        """Test that a string is wrapped in a text content block."""
        result = _normalize_content("Hello!")
        assert result == [{"type": "text", "text": "Hello!"}]

    def test_list_passed_through(self):
        """Test that a list of content blocks is passed through."""
        blocks = [{"type": "text", "text": "Hello!"}, {"type": "code", "language": "python", "text": "x=1"}]
        result = _normalize_content(blocks)
        assert result is blocks

    def test_non_string_non_list_converted(self):
        """Test that non-string, non-list content is converted to string."""
        result = _normalize_content(42)
        assert result == [{"type": "text", "text": "42"}]


@pytest.mark.unit
class TestExtractTextFromContent:
    """Tests for _extract_text_from_content()."""

    def test_extracts_text_blocks(self):
        """Test that text is extracted from text blocks."""
        content = [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world!"}]
        assert _extract_text_from_content(content) == "Hello world!"

    def test_ignores_non_text_blocks(self):
        """Test that non-text blocks are ignored."""
        content = [
            {"type": "text", "text": "Hello!"},
            {"type": "tool_use", "id": "call_1", "tool_name": "search", "input": {}},
        ]
        assert _extract_text_from_content(content) == "Hello!"

    def test_empty_content(self):
        """Test extraction from empty content list."""
        assert _extract_text_from_content([]) == ""


@pytest.mark.unit
class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_session_metrics_init(self):
        """Test that SessionMetrics initializes with default values."""
        metrics = SessionMetrics()

        assert metrics.total_prompt_tokens == 0
        assert metrics.total_completion_tokens == 0
        assert metrics.total_tokens == 0
        assert metrics.total_cost_usd == 0.0
        assert metrics.total_cache_read_tokens == 0
        assert metrics.total_cache_write_tokens == 0
        assert metrics.total_thinking_tokens == 0
        assert metrics.request_count == 0
        assert metrics.total_ttft_ms == 0.0
        assert metrics.total_latency_ms == 0.0

    def test_session_metrics_add_usage(self):
        """Test that add_usage accumulates tokens and cost correctly."""
        metrics = SessionMetrics()

        metrics.add_usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.0045
        )

        assert metrics.total_prompt_tokens == 100
        assert metrics.total_completion_tokens == 50
        assert metrics.total_tokens == 150
        assert metrics.total_cost_usd == 0.0045
        assert metrics.request_count == 1

    def test_session_metrics_add_usage_multiple(self):
        """Test that multiple add_usage calls accumulate properly."""
        metrics = SessionMetrics()

        # First request
        metrics.add_usage(100, 50, 150, 0.0045)
        # Second request
        metrics.add_usage(200, 75, 275, 0.0082)

        assert metrics.total_prompt_tokens == 300
        assert metrics.total_completion_tokens == 125
        assert metrics.total_tokens == 425
        assert metrics.total_cost_usd == pytest.approx(0.0127)
        assert metrics.request_count == 2

    def test_session_metrics_to_dict(self):
        """Test that to_dict serializes correctly with new fields."""
        metrics = SessionMetrics()
        metrics.add_usage(100, 50, 150, 0.0045, ttft_ms=250.0, total_latency_ms=1500.0)

        result = metrics.to_dict()

        assert result == {
            "total_prompt_tokens": 100,
            "total_completion_tokens": 50,
            "total_tokens": 150,
            "total_cost_usd": 0.0045,
            "total_cache_read_tokens": 0,
            "total_cache_write_tokens": 0,
            "total_thinking_tokens": 0,
            "request_count": 1,
            "average_ttft_ms": 250.0,
            "average_latency_ms": 1500.0,
            "metadata": {},
        }

    def test_session_metrics_to_dict_includes_metadata(self):
        """Test that to_dict always includes metadata escape hatch."""
        metrics = SessionMetrics()
        result = metrics.to_dict()
        assert "metadata" in result
        assert result["metadata"] == {}

    def test_session_metrics_zero_cost(self):
        """Test that zero cost is handled correctly."""
        metrics = SessionMetrics()
        metrics.add_usage(100, 50, 150, 0.0)

        assert metrics.total_cost_usd == 0.0
        assert metrics.request_count == 1

    def test_session_metrics_latency_tracking(self):
        """Test that latency metrics are tracked and averaged correctly."""
        metrics = SessionMetrics()

        # First request: fast TTFT
        metrics.add_usage(100, 50, 150, 0.001, ttft_ms=200.0, total_latency_ms=1000.0)
        # Second request: slower TTFT
        metrics.add_usage(100, 50, 150, 0.001, ttft_ms=400.0, total_latency_ms=2000.0)

        assert metrics.total_ttft_ms == 600.0
        assert metrics.total_latency_ms == 3000.0
        assert metrics.average_ttft_ms == 300.0
        assert metrics.average_latency_ms == 1500.0

    def test_session_metrics_cache_tokens(self):
        """Test that cache token fields accumulate correctly."""
        metrics = SessionMetrics()
        metrics.add_usage(100, 50, 150, 0.001, cache_read_tokens=500, cache_write_tokens=200)
        metrics.add_usage(100, 50, 150, 0.001, cache_read_tokens=300, cache_write_tokens=0)

        assert metrics.total_cache_read_tokens == 800
        assert metrics.total_cache_write_tokens == 200

    def test_session_metrics_thinking_tokens(self):
        """Test that thinking tokens accumulate correctly."""
        metrics = SessionMetrics()
        metrics.add_usage(100, 50, 150, 0.001, thinking_tokens=1000)
        metrics.add_usage(100, 50, 150, 0.001, thinking_tokens=500)

        assert metrics.total_thinking_tokens == 1500


@pytest.mark.unit
class TestConversationLogger:
    """Tests for ConversationLogger class."""

    def test_conversation_logger_init(self, temp_conversations_dir: Path):
        """Test that ConversationLogger initializes with correct defaults."""
        logger = ConversationLogger(temp_conversations_dir)

        assert logger.conversations_dir == temp_conversations_dir
        assert logger.current_conversation == []
        assert isinstance(logger.session_start, datetime)
        assert isinstance(logger.metrics, SessionMetrics)
        assert logger.conversation_id.startswith("conv_")
        assert logger.title is None
        assert logger.topic is None
        assert logger.tags == []
        assert logger.feedback is None
        assert logger.metadata == {}

    def test_conversation_logger_init_with_configs(
        self, temp_conversations_dir: Path,
        sample_model_config, sample_agent_config,
        sample_context_snapshot, sample_environment,
    ):
        """Test that ConversationLogger accepts optional config dicts."""
        logger = ConversationLogger(
            temp_conversations_dir,
            model_config=sample_model_config,
            agent_config=sample_agent_config,
            context_snapshot=sample_context_snapshot,
            environment=sample_environment,
        )

        assert logger.model_config == sample_model_config
        assert logger.agent_config == sample_agent_config
        assert logger.context_snapshot == sample_context_snapshot
        assert logger.environment == sample_environment

    def test_conversation_logger_creates_dir(self, tmp_path: Path):
        """Test that ConversationLogger creates directory if missing."""
        new_dir = tmp_path / "new_conversations"
        assert not new_dir.exists()

        logger = ConversationLogger(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_add_message_user(self, temp_conversations_dir: Path):
        """Test adding a user message with new schema fields."""
        logger = ConversationLogger(temp_conversations_dir)

        with freeze_time("2026-01-15 14:30:00"):
            logger.add_message("user", "Hello!")

        assert len(logger.current_conversation) == 1
        message = logger.current_conversation[0]

        assert message["id"] == "msg_001"
        assert message["parent_id"] is None
        assert message["role"] == "user"
        assert message["content"] == [{"type": "text", "text": "Hello!"}]
        assert message["timestamp"] == "2026-01-15T14:30:00"
        assert message["usage"] is None
        assert message["latency"] is None
        assert message["stop_reason"] is None
        assert message["status"] == "completed"
        assert message["error"] is None
        assert message["metadata"] == {}

    def test_add_message_assistant_with_usage(self, temp_conversations_dir: Path):
        """Test adding an assistant message with usage data in new format."""
        logger = ConversationLogger(temp_conversations_dir)

        with freeze_time("2026-01-15 14:30:00"):
            logger.add_message(
                "assistant",
                "Hello, how can I help?",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.0045
            )

        assert len(logger.current_conversation) == 1
        message = logger.current_conversation[0]

        assert message["id"] == "msg_001"
        assert message["role"] == "assistant"
        assert message["content"] == [{"type": "text", "text": "Hello, how can I help?"}]
        assert message["usage"] == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "thinking_tokens": 0,
            "cost_usd": 0.0045,
            "metadata": {},
        }

        # Check metrics were updated
        assert logger.metrics.total_tokens == 150
        assert logger.metrics.request_count == 1

    def test_add_message_assistant_without_usage(self, temp_conversations_dir: Path):
        """Test adding an assistant message without usage data."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("assistant", "Response")

        message = logger.current_conversation[0]
        assert message["usage"] is None
        assert logger.metrics.request_count == 0

    def test_add_message_sequential_ids(self, temp_conversations_dir: Path):
        """Test that message IDs are assigned sequentially."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("user", "First")
        logger.add_message("assistant", "Second", total_tokens=10, prompt_tokens=5, completion_tokens=5)
        logger.add_message("user", "Third")

        assert logger.current_conversation[0]["id"] == "msg_001"
        assert logger.current_conversation[1]["id"] == "msg_002"
        assert logger.current_conversation[2]["id"] == "msg_003"

    def test_add_message_content_block_passthrough(self, temp_conversations_dir: Path):
        """Test that content block lists are passed through without wrapping."""
        logger = ConversationLogger(temp_conversations_dir)
        blocks = [
            {"type": "text", "text": "Hello!"},
            {"type": "tool_use", "id": "call_1", "tool_name": "search", "input": {"q": "test"}},
        ]

        logger.add_message("assistant", blocks)

        assert logger.current_conversation[0]["content"] == blocks

    def test_add_message_with_status_and_error(self, temp_conversations_dir: Path):
        """Test adding a message with error status."""
        logger = ConversationLogger(temp_conversations_dir)
        error_info = {"code": "rate_limit", "message": "Too many requests", "retry_count": 2}

        logger.add_message("assistant", "Error occurred", status="error", error=error_info)

        message = logger.current_conversation[0]
        assert message["status"] == "error"
        assert message["error"] == error_info

    def test_add_message_with_stop_reason(self, temp_conversations_dir: Path):
        """Test adding a message with stop_reason."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message(
            "assistant", "Full response",
            prompt_tokens=10, completion_tokens=5, total_tokens=15,
            stop_reason="end_turn",
        )

        assert logger.current_conversation[0]["stop_reason"] == "end_turn"

    def test_add_message_with_metadata(self, temp_conversations_dir: Path):
        """Test adding a message with per-message metadata."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("user", "Hello", metadata={"source": "voice", "language": "en"})

        assert logger.current_conversation[0]["metadata"] == {"source": "voice", "language": "en"}

    def test_add_message_timestamp_format(self, temp_conversations_dir: Path):
        """Test that timestamp is in ISO format."""
        logger = ConversationLogger(temp_conversations_dir)

        with freeze_time("2026-01-15 14:30:45"):
            logger.add_message("user", "Test")

        timestamp = logger.current_conversation[0]["timestamp"]

        # Should be valid ISO format
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.year == 2026
        assert parsed.month == 1
        assert parsed.day == 15

    def test_get_messages_for_api(self, temp_conversations_dir: Path):
        """Test that get_messages_for_api extracts text from content blocks."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("user", "Hello")
        logger.add_message("assistant", "Hi there", prompt_tokens=10, completion_tokens=5, total_tokens=15)

        api_messages = logger.get_messages_for_api()

        assert len(api_messages) == 2
        assert api_messages[0] == {"role": "user", "content": "Hello"}
        assert api_messages[1] == {"role": "assistant", "content": "Hi there"}

        # Ensure no extra fields in API format
        for msg in api_messages:
            assert "timestamp" not in msg
            assert "usage" not in msg
            assert "id" not in msg

    def test_get_messages_for_api_with_tool_role(self, temp_conversations_dir: Path):
        """Test that tool role messages are included in API messages."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("user", "Search for weather")
        logger.add_message("tool", "Weather is 3°C in Berlin")

        api_messages = logger.get_messages_for_api()
        assert len(api_messages) == 2
        assert api_messages[1]["role"] == "tool"
        assert api_messages[1]["content"] == "Weather is 3°C in Berlin"

    @freeze_time("2026-01-15 14:30:00")
    def test_save_conversation_json_structure(self, temp_conversations_dir: Path):
        """Test that save creates correct JSON structure with all new top-level keys."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("user", "Hello")
        logger.add_message("assistant", "Hi!", prompt_tokens=10, completion_tokens=5, total_tokens=15, cost_usd=0.001)

        with freeze_time("2026-01-15 14:31:00"):
            logger.save()

        # Find the saved file
        files = list(temp_conversations_dir.glob("*.json"))
        assert len(files) == 1

        # Load and verify structure
        with open(files[0]) as f:
            data = json.load(f)

        # All top-level keys present
        assert data["schema_version"] == "1.0.0"
        assert data["id"].startswith("conv_")
        assert data["title"] is None
        assert data["topic"] is None
        assert data["tags"] == []
        assert data["session_start"] == "2026-01-15T14:30:00"
        assert data["session_end"] == "2026-01-15T14:31:00"
        assert data["model"] is None
        assert data["agent"] is None
        assert data["context"] is None
        assert data["environment"] is None
        assert data["feedback"] is None
        assert data["metadata"] == {}

        # Metrics
        assert data["metrics"]["total_tokens"] == 15
        assert data["metrics"]["total_cache_read_tokens"] == 0
        assert data["metrics"]["total_cache_write_tokens"] == 0
        assert data["metrics"]["total_thinking_tokens"] == 0
        assert "metadata" in data["metrics"]

        # Messages
        assert len(data["messages"]) == 2
        msg0 = data["messages"][0]
        assert msg0["id"] == "msg_001"
        assert msg0["content"] == [{"type": "text", "text": "Hello"}]
        assert msg0["status"] == "completed"

    @freeze_time("2026-01-15 14:30:00")
    def test_save_conversation_with_configs(
        self, temp_conversations_dir: Path,
        sample_model_config, sample_agent_config,
        sample_context_snapshot, sample_environment,
    ):
        """Test that save includes model, agent, context, and environment."""
        logger = ConversationLogger(
            temp_conversations_dir,
            model_config=sample_model_config,
            agent_config=sample_agent_config,
            context_snapshot=sample_context_snapshot,
            environment=sample_environment,
        )
        logger.add_message("user", "Hello")
        logger.save()

        files = list(temp_conversations_dir.glob("*.json"))
        with open(files[0]) as f:
            data = json.load(f)

        assert data["model"] == sample_model_config
        assert data["agent"] == sample_agent_config
        assert data["context"] == sample_context_snapshot
        assert data["environment"] == sample_environment

    @freeze_time("2026-01-15 14:30:45")
    def test_save_conversation_filename(self, temp_conversations_dir: Path):
        """Test that filename format is correct (YYYY-MM-DD_HH-MM-SS.json)."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.add_message("user", "Test")

        logger.save()

        files = list(temp_conversations_dir.glob("*.json"))
        assert len(files) == 1

        filename = files[0].name
        assert filename == "2026-01-15_14-30-45.json"

    def test_save_empty_conversation(self, temp_conversations_dir: Path):
        """Test that save doesn't create file for empty conversation."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.save()

        files = list(temp_conversations_dir.glob("*.json"))
        assert len(files) == 0


@pytest.mark.unit
class TestConversationLoggerMethods:
    """Tests for set_topic, add_tag, set_title, set_feedback methods."""

    def test_set_title(self, temp_conversations_dir: Path):
        """Test setting conversation title."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.set_title("Debugging Python issue")
        assert logger.title == "Debugging Python issue"

    def test_set_topic(self, temp_conversations_dir: Path):
        """Test setting conversation topic."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.set_topic("coding")
        assert logger.topic == "coding"

    def test_add_tag(self, temp_conversations_dir: Path):
        """Test adding tags."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.add_tag("python")
        logger.add_tag("debugging")
        assert logger.tags == ["python", "debugging"]

    def test_add_tag_no_duplicates(self, temp_conversations_dir: Path):
        """Test that duplicate tags are not added."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.add_tag("python")
        logger.add_tag("python")
        assert logger.tags == ["python"]

    def test_set_feedback(self, temp_conversations_dir: Path):
        """Test setting session feedback."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.set_feedback(overall_rating=4, helpful=True, notes="Great session")

        assert logger.feedback == {
            "overall_rating": 4,
            "helpful": True,
            "notes": "Great session",
            "metadata": {},
        }

    def test_set_feedback_with_extra_kwargs(self, temp_conversations_dir: Path):
        """Test that extra kwargs go into feedback metadata."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.set_feedback(overall_rating=5, source="auto")

        assert logger.feedback["metadata"] == {"source": "auto"}

    @freeze_time("2026-01-15 14:30:00")
    def test_metadata_saved_to_json(self, temp_conversations_dir: Path):
        """Test that title, topic, tags, feedback are saved to JSON."""
        logger = ConversationLogger(temp_conversations_dir)
        logger.set_title("Test session")
        logger.set_topic("testing")
        logger.add_tag("unit-test")
        logger.set_feedback(overall_rating=5)

        logger.add_message("user", "Hello")
        logger.save()

        files = list(temp_conversations_dir.glob("*.json"))
        with open(files[0]) as f:
            data = json.load(f)

        assert data["title"] == "Test session"
        assert data["topic"] == "testing"
        assert data["tags"] == ["unit-test"]
        assert data["feedback"]["overall_rating"] == 5


@pytest.mark.unit
class TestMigrateConversation:
    """Tests for read-time migration of old conversation formats."""

    def test_already_migrated_passes_through(self):
        """Test that data with schema_version is returned as-is."""
        data = {"schema_version": "1.0.0", "id": "conv_123", "messages": []}
        result = migrate_conversation(data)
        assert result is data

    def test_migrate_v0_no_metrics(self):
        """Test migration of oldest format (no metrics)."""
        old_data = {
            "session_start": "2025-11-28T14:23:43.228507",
            "session_end": "2025-11-28T14:24:18.407526",
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": "2025-11-28T14:23:56"},
                {"role": "assistant", "content": "Hi!", "timestamp": "2025-11-28T14:23:59"},
            ]
        }

        result = migrate_conversation(old_data)

        assert result["schema_version"] == "1.0.0"
        assert result["id"] is None
        assert result["title"] is None
        assert result["topic"] is None
        assert result["tags"] == []
        assert result["metrics"] == {}
        assert result["feedback"] is None
        assert result["metadata"] == {}

        # Messages migrated
        assert len(result["messages"]) == 2
        msg0 = result["messages"][0]
        assert msg0["id"] == "msg_001"
        assert msg0["role"] == "user"
        assert msg0["content"] == [{"type": "text", "text": "Hello"}]
        assert msg0["status"] == "completed"
        assert msg0["usage"] is None

    def test_migrate_v2_with_latency(self):
        """Test migration of latest old format (metrics with latency)."""
        old_data = {
            "session_start": "2026-01-22T20:31:08.613204",
            "session_end": "2026-01-22T20:31:18.904728",
            "metrics": {
                "total_prompt_tokens": 1783,
                "total_completion_tokens": 13,
                "total_tokens": 1796,
                "total_cost_usd": 0.005544,
                "request_count": 1,
                "average_ttft_ms": 1154.24,
                "average_latency_ms": 1480.24,
            },
            "messages": [
                {"role": "user", "content": "Hi", "timestamp": "2026-01-22T20:31:14"},
                {
                    "role": "assistant",
                    "content": "Hey!",
                    "timestamp": "2026-01-22T20:31:15",
                    "usage": {
                        "prompt_tokens": 1783,
                        "completion_tokens": 13,
                        "total_tokens": 1796,
                        "cost_usd": 0.005544,
                    },
                    "latency": {"ttft_ms": 1154.24, "total_ms": 1480.24},
                },
            ]
        }

        result = migrate_conversation(old_data)

        # Metrics migrated with new fields
        assert result["metrics"]["total_cache_read_tokens"] == 0
        assert result["metrics"]["total_cache_write_tokens"] == 0
        assert result["metrics"]["total_thinking_tokens"] == 0
        assert result["metrics"]["total_prompt_tokens"] == 1783
        assert "metadata" in result["metrics"]

        # Message usage migrated with new fields
        msg1 = result["messages"][1]
        assert msg1["usage"]["cache_read_tokens"] == 0
        assert msg1["usage"]["thinking_tokens"] == 0
        assert msg1["usage"]["prompt_tokens"] == 1783
        assert "metadata" in msg1["usage"]

        # Latency preserved
        assert msg1["latency"]["ttft_ms"] == 1154.24

    def test_load_static_method(self, tmp_path: Path):
        """Test ConversationLogger.load() with an old format file."""
        old_data = {
            "session_start": "2025-11-28T14:23:43",
            "session_end": "2025-11-28T14:24:18",
            "messages": [
                {"role": "user", "content": "Test", "timestamp": "2025-11-28T14:23:56"},
            ]
        }
        filepath = tmp_path / "old_conversation.json"
        filepath.write_text(json.dumps(old_data))

        result = ConversationLogger.load(filepath)

        assert result["schema_version"] == "1.0.0"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == [{"type": "text", "text": "Test"}]

    def test_load_already_v1(self, tmp_path: Path):
        """Test that loading a v1.0.0 file returns it unchanged."""
        v1_data = {
            "schema_version": "1.0.0",
            "id": "conv_20260206_143022_abcd",
            "title": None,
            "messages": [],
        }
        filepath = tmp_path / "v1_conversation.json"
        filepath.write_text(json.dumps(v1_data))

        result = ConversationLogger.load(filepath)

        assert result["schema_version"] == "1.0.0"
        assert result["id"] == "conv_20260206_143022_abcd"
