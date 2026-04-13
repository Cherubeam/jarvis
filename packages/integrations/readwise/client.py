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
        response_fields: str = "title,summary,url,tags,category,reading_progress",
    ) -> str:
        """Search Reader documents. Returns JSON string."""
        args = ["reader-search-documents", query, "--json"]
        args.extend(["--response-fields", response_fields])
        if location:
            args.extend(["--location", location])
        if category:
            args.extend(["--category", category])
        return self._run(args)

    def search_highlights(self, query: str) -> str:
        """Search across all Readwise highlights. Returns JSON string."""
        return self._run(["readwise-search-highlights", query, "--json"])

    def get_document_details(self, document_id: str) -> str:
        """Get full details for a specific document. Returns JSON string."""
        return self._run(["reader-get-document-details", document_id, "--json"])

    def create_document(self, url: str) -> str:
        """Save a URL to Reader. Returns JSON string."""
        return self._run(["reader-create-document", url, "--json"])

    def tag_document(self, document_id: str, tags: str) -> str:
        """Add tags to a document. Tags are comma-separated."""
        return self._run(
            ["reader-add-tags-to-document", document_id, "--tags", tags, "--json"]
        )

    def move_document(self, document_id: str, location: str) -> str:
        """Move a document to a location (inbox, archive, shortlist)."""
        return self._run(
            ["reader-move-documents", document_id, "--location", location, "--json"]
        )

    def _run(self, args: list[str]) -> str:
        """Execute a readwise CLI command and return stdout.

        Returns the raw stdout on success, or an 'Error: ...' string on failure.
        """
        cmd = ["readwise", *args]
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
