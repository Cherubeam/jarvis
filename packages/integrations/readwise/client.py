"""
Readwise CLI subprocess wrapper.

Calls the globally installed `readwise` CLI binary, parses JSON output,
and handles errors and rate limits.
"""

import json
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Map user-friendly location names to CLI values
_LOCATION_MAP = {
    "inbox": "new",
    "new": "new",
    "later": "later",
    "shortlist": "shortlist",
    "archive": "archive",
    "feed": "feed",
}


def is_cli_available() -> bool:
    """Check whether the readwise CLI binary is on PATH."""
    return shutil.which("readwise") is not None


class ReadwiseClient:
    """Thin wrapper around the Readwise CLI for JARVIS tool use."""

    def __init__(self, cache_ttl_seconds: int = 300):
        self._cache_ttl = cache_ttl_seconds

    def search_documents(
        self,
        query: str,
        *,
        location: str = "",
        category: str = "",
    ) -> str:
        """Search Reader documents. Returns JSON string."""
        args = ["reader-search-documents", "--query", query]
        if location:
            cli_loc = _LOCATION_MAP.get(location.lower(), location)
            args.extend(["--location-in", cli_loc])
        if category:
            args.extend(["--category-in", category])
        return self._run(args)

    def search_highlights(self, query: str) -> str:
        """Search across all Readwise highlights. Returns JSON string."""
        return self._run(["readwise-search-highlights", "--vector-search-term", query])

    def get_document_details(self, document_id: str) -> str:
        """Get full details for a specific document. Returns JSON string."""
        return self._run(["reader-get-document-details", "--document-id", document_id])

    def create_document(self, url: str) -> str:
        """Save a URL to Reader. Returns JSON string."""
        return self._run(["reader-create-document", "--url", url])

    def tag_document(self, document_id: str, tags: str) -> str:
        """Add tags to a document. Tags are comma-separated."""
        return self._run(
            ["reader-add-tags-to-document", "--document-id", document_id, "--tag-names", tags]
        )

    def move_document(self, document_id: str, location: str) -> str:
        """Move a document to a location (new, later, shortlist, archive)."""
        cli_loc = _LOCATION_MAP.get(location.lower(), location)
        return self._run(
            ["reader-move-documents", "--document-ids", document_id, "--location", cli_loc]
        )

    def _run(self, args: list[str]) -> str:
        """Execute a readwise CLI command and return stdout.

        Returns the raw stdout on success, or an 'Error: ...' string on failure.
        The global --json flag is appended automatically.
        """
        cmd = ["readwise", "--json", *args]
        try:
            result = subprocess.run(  # noqa: S603, S607
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "429" in stderr or "rate limit" in stderr.lower():
                    return "Error: Readwise API rate limit reached. Please wait a moment and try again."
                return f"Error: readwise CLI failed (exit {result.returncode}): {stderr or result.stdout}"

            return result.stdout.strip()

        except FileNotFoundError:
            return "Error: readwise CLI is not installed. Run: npm install -g @readwise/cli"
        except subprocess.TimeoutExpired:
            return "Error: readwise CLI command timed out after 30 seconds."
        except Exception as e:
            return f"Error: unexpected failure running readwise CLI: {e}"


def parse_json_output(raw: str) -> list[dict] | dict | str:
    """Parse JSON from CLI output. Returns parsed data or the raw string on failure."""
    if raw.startswith("Error:"):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
