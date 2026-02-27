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
        assert "url" in FETCH_URL_TOOL.parameters["properties"]
        assert FETCH_URL_TOOL.parameters["required"] == ["url"]
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

        assert "Error" in result
        assert "timed out" in result

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

        assert "Error" in result
        assert "404" in result

    def test_network_error_returns_error_string(self):
        with patch(
            "packages.core.tools.web_fetch.httpx.get",
            side_effect=httpx.RequestError("connection refused", request=MagicMock()),
        ):
            result = _fetch_url("https://example.com")

        assert "Error" in result
        assert "Network error" in result

    def test_content_truncated_at_50kb(self):
        large_content = "x" * (_MAX_BYTES + 1000)
        mock_response = MagicMock()
        mock_response.text = "<html><body>stub</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=large_content):
            result = _fetch_url("https://example.com")

        assert len(result) <= _MAX_BYTES + 100  # +100 for truncation notice
        assert "truncated" in result

    def test_raw_html_fallback_truncated_when_large(self):
        large_html = "A" * (_MAX_BYTES + 5000)
        mock_response = MagicMock()
        mock_response.text = large_html
        mock_response.raise_for_status = MagicMock()

        with patch("packages.core.tools.web_fetch.httpx.get", return_value=mock_response), \
             patch("packages.core.tools.web_fetch.trafilatura.extract", return_value=None):
            result = _fetch_url("https://example.com")

        assert "truncated" in result
        assert len(result) <= _MAX_BYTES + 100
