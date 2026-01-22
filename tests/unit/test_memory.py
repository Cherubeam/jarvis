"""
Unit tests for memory module.

Tests SessionMetrics and ConversationLogger functionality.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from freezegun import freeze_time

# Try new import path first, fall back to old for backward compatibility
try:
    from packages.core.memory import SessionMetrics, ConversationLogger
except ImportError:
    from memory import SessionMetrics, ConversationLogger


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
        """Test that to_dict serializes correctly."""
        metrics = SessionMetrics()
        metrics.add_usage(100, 50, 150, 0.0045, ttft_ms=250.0, total_latency_ms=1500.0)

        result = metrics.to_dict()

        assert result == {
            "total_prompt_tokens": 100,
            "total_completion_tokens": 50,
            "total_tokens": 150,
            "total_cost_usd": 0.0045,
            "request_count": 1,
            "average_ttft_ms": 250.0,
            "average_latency_ms": 1500.0,
        }

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

    def test_conversation_logger_creates_dir(self, tmp_path: Path):
        """Test that ConversationLogger creates directory if missing."""
        new_dir = tmp_path / "new_conversations"
        assert not new_dir.exists()

        logger = ConversationLogger(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_add_message_user(self, temp_conversations_dir: Path):
        """Test adding a user message."""
        logger = ConversationLogger(temp_conversations_dir)

        with freeze_time("2026-01-15 14:30:00"):
            logger.add_message("user", "Hello!")

        assert len(logger.current_conversation) == 1
        message = logger.current_conversation[0]

        assert message["role"] == "user"
        assert message["content"] == "Hello!"
        assert message["timestamp"] == "2026-01-15T14:30:00"
        assert "usage" not in message

    def test_add_message_assistant_with_usage(self, temp_conversations_dir: Path):
        """Test adding an assistant message with usage data."""
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

        assert message["role"] == "assistant"
        assert message["content"] == "Hello, how can I help?"
        assert message["timestamp"] == "2026-01-15T14:30:00"
        assert message["usage"] == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.0045
        }

        # Check metrics were updated
        assert logger.metrics.total_tokens == 150
        assert logger.metrics.request_count == 1

    def test_add_message_assistant_without_usage(self, temp_conversations_dir: Path):
        """Test adding an assistant message without usage data."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("assistant", "Response")

        message = logger.current_conversation[0]
        assert "usage" not in message
        assert logger.metrics.request_count == 0

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
        """Test that get_messages_for_api returns messages without timestamps/usage."""
        logger = ConversationLogger(temp_conversations_dir)

        logger.add_message("user", "Hello")
        logger.add_message("assistant", "Hi there", prompt_tokens=10, completion_tokens=5, total_tokens=15)

        api_messages = logger.get_messages_for_api()

        assert len(api_messages) == 2
        assert api_messages[0] == {"role": "user", "content": "Hello"}
        assert api_messages[1] == {"role": "assistant", "content": "Hi there"}

        # Ensure no timestamp or usage in API format
        for msg in api_messages:
            assert "timestamp" not in msg
            assert "usage" not in msg

    @freeze_time("2026-01-15 14:30:00")
    def test_save_conversation_json_structure(self, temp_conversations_dir: Path):
        """Test that save creates correct JSON structure."""
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

        assert "session_start" in data
        assert "session_end" in data
        assert "metrics" in data
        assert "messages" in data

        assert data["session_start"] == "2026-01-15T14:30:00"
        assert data["session_end"] == "2026-01-15T14:31:00"
        assert data["metrics"]["total_tokens"] == 15
        assert len(data["messages"]) == 2

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
