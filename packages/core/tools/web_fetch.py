"""
Web fetch tool — fetches and extracts text content from URLs.

Uses httpx for HTTP requests and trafilatura for clean article extraction.
All errors are returned as strings so the LLM can reason about failures.
"""

import httpx
import trafilatura

from packages.core.tools.base import ToolDefinition

_MAX_BYTES = 50_000  # 50 KB cap on extracted content
_TIMEOUT = 10.0
_HEADERS = {"User-Agent": "JARVIS/1.0"}


def _fetch_url(url: str) -> str:
    """Fetch a URL and return its extracted text content."""
    try:
        response = httpx.get(
            url,
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers=_HEADERS,
        )
        response.raise_for_status()
    except httpx.TimeoutException:
        return f"Error: Request to {url} timed out after {int(_TIMEOUT)}s."
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} from {url}."
    except httpx.RequestError as e:
        return f"Error: Network error fetching {url}: {e}"

    html = response.text

    # Try trafilatura for clean article extraction
    extracted = trafilatura.extract(html)
    if not extracted:
        # Fall back to a raw HTML slice so the LLM still gets something
        extracted = html[:_MAX_BYTES]
        if len(html) > _MAX_BYTES:
            extracted += "\n\n[Content truncated at 50 KB]"
        return extracted

    if len(extracted) > _MAX_BYTES:
        extracted = extracted[:_MAX_BYTES] + "\n\n[Content truncated at 50 KB]"

    return extracted


FETCH_URL_TOOL = ToolDefinition(
    name="fetch_url",
    description=(  # pragma: no mutate
        "Fetch the text content of a web page. "  # pragma: no mutate
        "Use this to read articles, documentation, or any public URL. "  # pragma: no mutate
        "Returns the extracted text. Returns an error string on failure."  # pragma: no mutate
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL to fetch (must start with http:// or https://).",  # pragma: no mutate
            }
        },
        "required": ["url"],
    },
    execute=_fetch_url,
)
