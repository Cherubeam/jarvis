"""
Unit tests for the fetch_url web fetch tool.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from packages.core.tools.web_fetch import FETCH_URL_TOOL, _fetch_url, _MAX_BYTES


@pytest.mark.unit
class TestFetchUrlTool:
    def test_tool_definition_structure(self):
        assert FETCH_URL_TOOL.name == "fetch_url"
        params = FETCH_URL_TOOL.parameters
        assert params["type"] == "object"
        assert set(params["properties"].keys()) == {"url"}
        assert params["properties"]["url"]["type"] == "string"
        assert params["required"] == ["url"]
        assert callable(FETCH_URL_TOOL.execute)

    def test_successful_fetch_with_trafilatura_extraction(self):
        html = "<html><body><article>Clean article text here.</article></body></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value="Clean article text here."):
            result = _fetch_url("https://example.com/article")

        assert result == "Clean article text here."

    def test_falls_back_to_raw_html_when_trafilatura_returns_none(self):
        html = "<html><body>Raw HTML content</body></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=None):
            result = _fetch_url("https://example.com")

        assert "Raw HTML content" in result

    def test_timeout_returns_error_string(self):
        with patch("packages.core.tools.web_fetch.httpx.get", side_effect=httpx.TimeoutException("timeout")):
            result = _fetch_url("https://example.com")

        assert result == "Error: Request to https://example.com timed out after 10s."

    def test_http_error_returns_error_string(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch(
            "packages.core.tools.web_fetch.httpx.get",
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            ),
        ):
            result = _fetch_url("https://example.com/missing")

        assert result == "Error: HTTP 404 from https://example.com/missing."

    def test_network_error_returns_error_string(self):
        with patch(
            "packages.core.tools.web_fetch.httpx.get",
            side_effect=httpx.RequestError("connection refused", request=MagicMock()),
        ):
            result = _fetch_url("https://example.com")

        assert result.startswith("Error: Network error fetching https://example.com:")
        assert "connection refused" in result

    def test_content_truncated_at_50kb(self):
        large_content = "x" * (_MAX_BYTES + 1000)
        mock_response = MagicMock()
        mock_response.text = "<html><body>stub</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=large_content):
            result = _fetch_url("https://example.com")

        assert result.endswith("\n\n[Content truncated at 50 KB]")
        assert len(result) == _MAX_BYTES + len("\n\n[Content truncated at 50 KB]")

    def test_content_exactly_at_max_not_truncated(self):
        """Boundary: content exactly at _MAX_BYTES should NOT be truncated."""
        exact_content = "x" * _MAX_BYTES
        mock_response = MagicMock()
        mock_response.text = "<html><body>stub</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=exact_content):
            result = _fetch_url("https://example.com")

        assert result == exact_content
        assert "[Content truncated" not in result

    def test_raw_html_fallback_truncated_when_large(self):
        large_html = "A" * (_MAX_BYTES + 5000)
        mock_response = MagicMock()
        mock_response.text = large_html
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=None):
            result = _fetch_url("https://example.com")

        assert result.endswith("\n\n[Content truncated at 50 KB]")
        assert result[:_MAX_BYTES] == "A" * _MAX_BYTES

    def test_raw_html_exactly_at_max_not_truncated(self):
        """Boundary: raw HTML fallback exactly at _MAX_BYTES should NOT truncate."""
        exact_html = "B" * _MAX_BYTES
        mock_response = MagicMock()
        mock_response.text = exact_html
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=None):
            result = _fetch_url("https://example.com")

        assert result == exact_html
        assert "[Content truncated" not in result
