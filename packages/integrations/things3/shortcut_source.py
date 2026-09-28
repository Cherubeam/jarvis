"""
Read Things 3 through a user-built Shortcut instead of its SQLite database.

Reading Things' database needs Full Disk Access for whichever app launches JARVIS
(granted per app by macOS). The "JARVIS Things Export" Shortcut uses Things' own
Shortcuts actions instead, so no special permission is needed. See ADR-037 and
docs/engineering/deployment.md#things-3 for how to build the Shortcut.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SHORTCUT_NAME = "JARVIS Things Export"
# Measured: ~1.7 s with Things closed (it's launched in the background), ~0.5-1.2 s
# with Things running. Startup blocks on this, so fail fast rather than hang
TIMEOUT_SECONDS = 10


class ThingsUnavailableError(Exception):
    """Things tasks couldn't be read; the message says why and what to do."""


def run_export(shortcut_name: str = SHORTCUT_NAME, timeout: float = TIMEOUT_SECONDS) -> dict[str, list[dict[str, Any]]]:
    """Run the export Shortcut and return ``{"inbox": [...], "scheduled": [...]}``.

    Raises:
        ThingsUnavailableError: not on macOS, no ``shortcuts`` CLI, Shortcut missing or failing,
            timeout, or output that isn't the expected JSON document.
    """
    if sys.platform != "darwin":
        raise ThingsUnavailableError("Things needs macOS: the export runs through the Shortcuts app")
    if shutil.which("shortcuts") is None:  # type: ignore[unreachable]  # mypy checks as platform=linux
        raise ThingsUnavailableError("the 'shortcuts' command isn't available on this Mac")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "export.json"
        cmd = ["shortcuts", "run", shortcut_name, "--output-type", "public.json", "--output-path", str(out)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as e:
            raise ThingsUnavailableError(f"the '{shortcut_name}' Shortcut didn't finish within {timeout:g}s") from e
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            reason = detail[-1] if detail else f"exit code {proc.returncode}"
            raise ThingsUnavailableError(f"the '{shortcut_name}' Shortcut failed: {reason}")
        if out.is_dir():
            # Shortcuts writes one file per item when the output is a list
            raise ThingsUnavailableError(f"the '{shortcut_name}' Shortcut must output one dictionary, not a list")
        if not out.is_file():
            raise ThingsUnavailableError(
                f"the '{shortcut_name}' Shortcut produced no output (missing 'Stop and Output'?)"
            )
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ThingsUnavailableError(f"the '{shortcut_name}' Shortcut output isn't JSON: {e}") from e

    if not isinstance(data, dict):
        raise ThingsUnavailableError(f"the '{shortcut_name}' Shortcut must output a dictionary")
    export: dict[str, list[dict[str, Any]]] = {}
    for key in ("inbox", "scheduled"):
        items = data.get(key, [])
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise ThingsUnavailableError(f"'{key}' in the Shortcut output must be a list of dictionaries")
        export[key] = items
    return export
