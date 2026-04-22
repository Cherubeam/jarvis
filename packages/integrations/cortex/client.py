"""HTTP client for the Cortex semantic search API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CortexClient:
    """Synchronous client for the Cortex API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8100", timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=3.0, read=timeout, write=5.0, pool=5.0),
        )

    def search(
        self,
        query: str,
        n_results: int = 5,
        path_prefix: str | None = None,
    ) -> dict[str, Any] | None:
        """POST /search. Returns response dict or None on failure."""
        payload: dict[str, Any] = {"query": query, "n_results": n_results}
        if path_prefix:
            payload["path_prefix"] = path_prefix
        try:
            resp = self._client.post("/search", json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Cortex search failed: %s", exc)
            return None

    def refresh_index(self) -> bool:
        """POST /index/refresh — trigger incremental re-indexing. Returns True on success."""
        try:
            resp = self._client.post("/index/refresh")
            resp.raise_for_status()
            return True
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("Cortex index refresh failed: %s", exc)
            return False

    def is_available(self) -> bool:
        """GET /status — True if Cortex responds healthy."""
        try:
            resp = self._client.get("/status")
            return resp.status_code == 200
        except (httpx.HTTPError, httpx.TimeoutException):
            return False

    def close(self) -> None:
        self._client.close()
