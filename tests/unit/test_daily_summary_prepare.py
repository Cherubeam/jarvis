"""Tests for packages.core.daily_summary — pure helpers shared by CLI and GUI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from packages.core.daily_summary import (
    DailySummaryError,
    DailySummaryFailure,
    DailySummaryRequest,
    build_daily_summary_request,
    parse_daily_summary_command,
)
from packages.integrations.obsidian.callout import CalloutBlock, CalloutNotFound

# --- parse_daily_summary_command -----------------------------------------


@pytest.mark.unit
class TestParseCommand:
    def test_no_payload_returns_none_none(self):
        target, failure = parse_daily_summary_command("/daily-summary")
        assert target is None
        assert failure is None

    def test_whitespace_payload_returns_none_none(self):
        target, failure = parse_daily_summary_command("/daily-summary   ")
        assert target is None
        assert failure is None

    def test_valid_iso_date_returns_date_none(self):
        target, failure = parse_daily_summary_command("/daily-summary 2026-04-18")
        assert target == "2026-04-18"
        assert failure is None

    def test_invalid_date_returns_failure(self):
        target, failure = parse_daily_summary_command("/daily-summary not-a-date")
        assert target is None
        assert failure is not None
        assert failure.error == DailySummaryError.INVALID_DATE
        assert "not-a-date" in failure.message


# --- build_daily_summary_request -----------------------------------------


def _vault_mock():
    return Mock(name="VaultConfig")


@pytest.mark.unit
class TestBuildRequest:
    def test_vault_none_returns_vault_not_configured(self):
        result = build_daily_summary_request(
            vault_config=None,
            system_prompt="SYS",
            history=[],
            daily_prompt="DAILY",
        )
        assert isinstance(result, DailySummaryFailure)
        assert result.error == DailySummaryError.VAULT_NOT_CONFIGURED
        assert "obsidian" in result.message.lower()

    @patch("packages.core.daily_summary.read_note")
    @patch("packages.core.daily_summary.get_daily_note_path")
    def test_note_not_found_returns_failure(self, mock_path, mock_read):
        mock_path.return_value = Path("/vault/2026-04-18.md")
        mock_read.side_effect = FileNotFoundError("nope")
        result = build_daily_summary_request(
            vault_config=_vault_mock(),
            system_prompt="SYS",
            history=[],
            daily_prompt="DAILY",
        )
        assert isinstance(result, DailySummaryFailure)
        assert result.error == DailySummaryError.NOTE_NOT_FOUND
        assert "2026-04-18.md" in result.message

    @patch("packages.core.daily_summary.read_note")
    @patch("packages.core.daily_summary.get_daily_note_path")
    def test_permission_error_returns_failure(self, mock_path, mock_read):
        mock_path.return_value = Path("/vault/x.md")
        mock_read.side_effect = PermissionError("no read")
        result = build_daily_summary_request(
            vault_config=_vault_mock(),
            system_prompt="SYS",
            history=[],
            daily_prompt="DAILY",
        )
        assert isinstance(result, DailySummaryFailure)
        assert result.error == DailySummaryError.NOTE_PERMISSION_DENIED
        assert result.message == "no read"

    @patch("packages.core.daily_summary.find_jarvis_callout")
    @patch("packages.core.daily_summary.read_note")
    @patch("packages.core.daily_summary.get_daily_note_path")
    def test_no_callout_returns_failure(self, mock_path, mock_read, mock_find):
        mock_path.return_value = Path("/vault/2026-04-18.md")
        mock_read.return_value = "# Note\nno callout here"
        mock_find.return_value = CalloutNotFound()
        result = build_daily_summary_request(
            vault_config=_vault_mock(),
            system_prompt="SYS",
            history=[],
            daily_prompt="DAILY",
        )
        assert isinstance(result, DailySummaryFailure)
        assert result.error == DailySummaryError.NO_CALLOUT
        assert "[!JARVIS]" in result.message
        assert "2026-04-18.md" in result.message

    @patch("packages.core.daily_summary.find_jarvis_callout")
    @patch("packages.core.daily_summary.read_note")
    @patch("packages.core.daily_summary.get_daily_note_path")
    def test_happy_path_builds_messages(self, mock_path, mock_read, mock_find):
        mock_path.return_value = Path("/vault/2026-04-18.md")
        note_content = "# Daily\n- did stuff\n> [!JARVIS]\n> old reply\n\n## After"
        mock_read.return_value = note_content
        mock_find.return_value = CalloutBlock(start_line=2, end_line=3, existing_content="old reply")

        result = build_daily_summary_request(
            vault_config=_vault_mock(),
            system_prompt="SYS",
            history=[{"role": "user", "content": "prior"}],
            daily_prompt="DAILY",
            target_date="2026-04-18",
        )

        assert isinstance(result, DailySummaryRequest)
        assert result.target_date == "2026-04-18"
        assert result.note_path == Path("/vault/2026-04-18.md")
        assert len(result.messages) == 3
        assert result.messages[0]["role"] == "system"
        assert result.messages[0]["content"] == "SYS\n\nDAILY"
        assert result.messages[1] == {"role": "user", "content": "prior"}
        assert result.messages[2]["role"] == "user"
        user_text = result.messages[2]["content"]
        assert "2026-04-18" in user_text
        assert "did stuff" in user_text
        assert "After" in user_text
        assert "old callout" not in user_text  # stripped
        assert "DO NOT repeat these" in user_text

    @patch("packages.core.daily_summary.find_jarvis_callout")
    @patch("packages.core.daily_summary.read_note")
    @patch("packages.core.daily_summary.get_daily_note_path")
    def test_no_date_uses_today_label(self, mock_path, mock_read, mock_find):
        mock_path.return_value = Path("/vault/today.md")
        mock_read.return_value = "body\n> [!JARVIS]\n> x"
        mock_find.return_value = CalloutBlock(start_line=1, end_line=2, existing_content="x")

        result = build_daily_summary_request(
            vault_config=_vault_mock(),
            system_prompt="SYS",
            history=[],
            daily_prompt="DAILY",
        )
        assert isinstance(result, DailySummaryRequest)
        assert result.target_date is None
        assert "for today" in result.messages[-1]["content"]

    @patch("packages.core.daily_summary.find_jarvis_callout")
    @patch("packages.core.daily_summary.read_note")
    @patch("packages.core.daily_summary.get_daily_note_path")
    def test_empty_existing_callout_content_omits_repetition_guard(self, mock_path, mock_read, mock_find):
        mock_path.return_value = Path("/vault/today.md")
        mock_read.return_value = "body\n> [!JARVIS]"
        mock_find.return_value = CalloutBlock(start_line=1, end_line=1, existing_content="")

        result = build_daily_summary_request(
            vault_config=_vault_mock(),
            system_prompt="SYS",
            history=[],
            daily_prompt="DAILY",
        )
        assert isinstance(result, DailySummaryRequest)
        assert "DO NOT repeat these" not in result.messages[-1]["content"]
