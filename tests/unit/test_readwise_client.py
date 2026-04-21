"""
Unit tests for Readwise CLI subprocess wrapper.
"""

from unittest.mock import MagicMock, patch

import pytest

from packages.integrations.readwise.client import (
    ReadwiseClient,
    is_cli_available,
    parse_json_output,
)


@pytest.mark.unit
class TestIsCliAvailable:
    """Tests for CLI availability check."""

    @patch("packages.integrations.readwise.client.shutil.which")
    def test_available_when_binary_found(self, mock_which):
        mock_which.return_value = "/usr/local/bin/readwise"
        assert is_cli_available() is True
        mock_which.assert_called_once_with("readwise")

    @patch("packages.integrations.readwise.client.shutil.which")
    def test_unavailable_when_binary_missing(self, mock_which):
        mock_which.return_value = None
        assert is_cli_available() is False


@pytest.mark.unit
class TestReadwiseClientSearchDocuments:
    """Tests for search_documents method."""

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_basic_search_returns_stdout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"title": "Test Article"}]',
            stderr="",
        )
        client = ReadwiseClient()
        result = client.search_documents("ai agents")

        assert result == '[{"title": "Test Article"}]'
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "readwise"
        assert "--json" in cmd
        assert "reader-search-documents" in cmd
        assert "--query" in cmd
        idx = cmd.index("--query")
        assert cmd[idx + 1] == "ai agents"

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_search_with_location_filter_maps_inbox_to_new(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        client = ReadwiseClient()
        client.search_documents("test", location="inbox")

        cmd = mock_run.call_args[0][0]
        assert "--location-in" in cmd
        idx = cmd.index("--location-in")
        assert cmd[idx + 1] == "new"

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_search_with_category_filter(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        client = ReadwiseClient()
        client.search_documents("test", category="article")

        cmd = mock_run.call_args[0][0]
        assert "--category-in" in cmd
        idx = cmd.index("--category-in")
        assert cmd[idx + 1] == "article"

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_search_without_filters_omits_flags(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        client = ReadwiseClient()
        client.search_documents("test")

        cmd = mock_run.call_args[0][0]
        assert "--location-in" not in cmd
        assert "--category-in" not in cmd


@pytest.mark.unit
class TestReadwiseClientErrorHandling:
    """Tests for error handling in _run method."""

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_nonzero_exit_returns_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="auth failed")
        client = ReadwiseClient()
        result = client.search_documents("test")

        assert result.startswith("Error:")
        assert "auth failed" in result

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_rate_limit_429_returns_specific_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="HTTP 429 Too Many Requests"
        )
        client = ReadwiseClient()
        result = client.search_documents("test")

        assert result.startswith("Error:")
        assert "rate limit" in result.lower()

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_file_not_found_returns_install_message(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        client = ReadwiseClient()
        result = client.search_documents("test")

        assert result.startswith("Error:")
        assert "not installed" in result

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_timeout_returns_error(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="readwise", timeout=30)
        client = ReadwiseClient()
        result = client.search_documents("test")

        assert result.startswith("Error:")
        assert "timed out" in result


@pytest.mark.unit
class TestReadwiseClientOtherMethods:
    """Tests for search_highlights, get_document_details, and write methods."""

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_search_highlights_uses_vector_search_term(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"text": "highlight"}]', stderr="")
        client = ReadwiseClient()
        result = client.search_highlights("systems thinking")

        assert result == '[{"text": "highlight"}]'
        cmd = mock_run.call_args[0][0]
        assert "readwise-search-highlights" in cmd
        assert "--vector-search-term" in cmd
        idx = cmd.index("--vector-search-term")
        assert cmd[idx + 1] == "systems thinking"

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_get_document_details_uses_named_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"title": "Doc"}', stderr="")
        client = ReadwiseClient()
        result = client.get_document_details("doc123")

        assert result == '{"title": "Doc"}'
        cmd = mock_run.call_args[0][0]
        assert "reader-get-document-details" in cmd
        assert "--document-id" in cmd
        idx = cmd.index("--document-id")
        assert cmd[idx + 1] == "doc123"

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_create_document_uses_url_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"id": "new123"}', stderr="")
        client = ReadwiseClient()
        result = client.create_document("https://example.com/article")

        assert "new123" in result
        cmd = mock_run.call_args[0][0]
        assert "reader-create-document" in cmd
        assert "--url" in cmd

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_tag_document_uses_tag_names_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
        client = ReadwiseClient()
        client.tag_document("doc123", "ai,research")

        cmd = mock_run.call_args[0][0]
        assert "reader-add-tags-to-document" in cmd
        assert "--tag-names" in cmd
        assert "--document-id" in cmd

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_move_document_uses_document_ids_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
        client = ReadwiseClient()
        client.move_document("doc123", "archive")

        cmd = mock_run.call_args[0][0]
        assert "reader-move-documents" in cmd
        assert "--document-ids" in cmd
        assert "--location" in cmd
        idx = cmd.index("--location")
        assert cmd[idx + 1] == "archive"

    @patch("packages.integrations.readwise.client.subprocess.run")
    def test_move_document_maps_inbox_to_new(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
        client = ReadwiseClient()
        client.move_document("doc123", "inbox")

        cmd = mock_run.call_args[0][0]
        idx = cmd.index("--location")
        assert cmd[idx + 1] == "new"


@pytest.mark.unit
class TestParseJsonOutput:
    """Tests for parse_json_output helper."""

    def test_parses_valid_json_array(self):
        result = parse_json_output('[{"title": "Test"}]')
        assert isinstance(result, list)
        assert result[0]["title"] == "Test"

    def test_parses_valid_json_object(self):
        result = parse_json_output('{"id": "abc"}')
        assert isinstance(result, dict)
        assert result["id"] == "abc"

    def test_returns_error_string_unchanged(self):
        result = parse_json_output("Error: something failed")
        assert result == "Error: something failed"

    def test_returns_raw_string_on_invalid_json(self):
        result = parse_json_output("not json at all")
        assert result == "not json at all"
