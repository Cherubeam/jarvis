"""Unit tests for the Cortex HTTP client."""

from __future__ import annotations

import httpx
import pytest
import respx

from packages.integrations.cortex.client import CortexClient


BASE_URL = "http://127.0.0.1:8100"


@pytest.fixture
def client() -> CortexClient:
    return CortexClient(base_url=BASE_URL, timeout=5.0)


class TestSearch:
    @respx.mock
    def test_search_success(self, client: CortexClient) -> None:
        payload = {"results": [{"path": "Note.md", "content": "hello", "score": 0.9}], "count": 1}
        respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(200, json=payload))

        result = client.search("test query", n_results=3)

        assert result is not None
        assert result["count"] == 1
        assert result["results"][0]["path"] == "Note.md"

    @respx.mock
    def test_search_connection_error(self, client: CortexClient) -> None:
        respx.post(f"{BASE_URL}/search").mock(side_effect=httpx.ConnectError("connection refused"))

        result = client.search("test query")

        assert result is None

    @respx.mock
    def test_search_timeout(self, client: CortexClient) -> None:
        respx.post(f"{BASE_URL}/search").mock(side_effect=httpx.ReadTimeout("read timed out"))

        result = client.search("test query")

        assert result is None


    @respx.mock
    def test_search_http_500(self, client: CortexClient) -> None:
        respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(500, text="Internal Server Error"))

        result = client.search("test query")

        assert result is None

    @respx.mock
    def test_search_malformed_json(self, client: CortexClient) -> None:
        respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(200, text="not json"))

        result = client.search("test query")

        assert result is None

    @respx.mock
    def test_search_sends_path_prefix(self, client: CortexClient) -> None:
        payload = {"results": [], "count": 0}
        route = respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(200, json=payload))

        client.search("test query", path_prefix="Projects/")

        assert route.called
        sent_json = route.calls[0].request.content
        import json

        body = json.loads(sent_json)
        assert body["path_prefix"] == "Projects/"


class TestIsAvailable:
    @respx.mock
    def test_is_available_healthy(self, client: CortexClient) -> None:
        respx.get(f"{BASE_URL}/status").mock(return_value=httpx.Response(200, json={"status": "ok"}))

        assert client.is_available() is True

    @respx.mock
    def test_is_available_unreachable(self, client: CortexClient) -> None:
        respx.get(f"{BASE_URL}/status").mock(side_effect=httpx.ConnectError("connection refused"))

        assert client.is_available() is False
