"""
Unit tests for the web search tool.
"""

from unittest.mock import patch

import pytest

from packages.core.tools.web_search import _MAX_OUTPUT_CHARS, WEB_SEARCH_TOOL, _search_web


def _make_result(title="Title", href="https://example.com", body="Snippet text"):
    return {"title": title, "href": href, "body": body}


@pytest.mark.unit
class TestWebSearchToolDefinition:
    """Tests for the WEB_SEARCH_TOOL constant."""

    def test_tool_name(self):
        assert WEB_SEARCH_TOOL.name == "web_search"

    def test_required_params(self):
        assert WEB_SEARCH_TOOL.parameters["required"] == ["query"]

    def test_has_query_and_max_results_params(self):
        props = WEB_SEARCH_TOOL.parameters["properties"]
        assert "query" in props
        assert "max_results" in props
        assert props["max_results"]["type"] == "integer"

    def test_execute_is_callable(self):
        assert callable(WEB_SEARCH_TOOL.execute)


@pytest.mark.unit
class TestSearchWeb:
    """Tests for the _search_web function."""

    @patch("packages.core.tools.web_search.DDGS")
    def test_successful_search_returns_formatted_results(self, MockDDGS):
        MockDDGS.return_value.text.return_value = [
            _make_result("Python 3.13", "https://python.org", "New features"),
            _make_result("Release Notes", "https://docs.python.org", "Details here"),
        ]

        result = _search_web("python 3.13")

        assert "Python 3.13" in result
        assert "https://python.org" in result
        assert "New features" in result
        assert "Release Notes" in result

    @patch("packages.core.tools.web_search.DDGS")
    def test_empty_results_returns_friendly_message(self, MockDDGS):
        MockDDGS.return_value.text.return_value = []

        result = _search_web("obscure query xyz")
        assert result == "No results found."

    @patch("packages.core.tools.web_search.DDGS")
    def test_error_returns_error_string_with_fallback_guidance(self, MockDDGS):
        MockDDGS.side_effect = RuntimeError("network down")

        result = _search_web("anything")
        assert result.startswith("Error:")
        assert "Do not retry" in result

    @patch("packages.core.tools.web_search.DDGS")
    def test_max_results_clamped_to_minimum_1(self, MockDDGS):
        mock_instance = MockDDGS.return_value
        mock_instance.text.return_value = [_make_result()]

        _search_web("test", max_results=0)
        mock_instance.text.assert_called_once_with("test", max_results=1)

    @patch("packages.core.tools.web_search.DDGS")
    def test_max_results_clamped_to_maximum_10(self, MockDDGS):
        mock_instance = MockDDGS.return_value
        mock_instance.text.return_value = [_make_result()]

        _search_web("test", max_results=50)
        mock_instance.text.assert_called_once_with("test", max_results=10)

    @patch("packages.core.tools.web_search.DDGS")
    def test_output_truncated_at_max_chars(self, MockDDGS):
        MockDDGS.return_value.text.return_value = [
            _make_result(f"Title {i}", f"https://example.com/{i}", "x" * 1000) for i in range(10)
        ]

        result = _search_web("test", max_results=10)
        assert len(result) <= _MAX_OUTPUT_CHARS + 50  # small overhead for truncation notice
        assert "[Results truncated]" in result

    @patch("packages.core.tools.web_search.DDGS")
    def test_results_numbered(self, MockDDGS):
        MockDDGS.return_value.text.return_value = [
            _make_result("First"),
            _make_result("Second"),
        ]

        result = _search_web("test")
        assert "1. **First**" in result
        assert "2. **Second**" in result
