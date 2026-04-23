"""Cheap, local-only stats about an agent's ``prompts/system.md``.

The Stats tab on the Agent Detail page calls :func:`compute_stats` to render
char / line counts, a byte-based token estimate, and a summary of how each
``prompt_include`` resolves (canonical vs example-fallback vs missing).

All stats are derived from the current on-disk ``system.md`` and the agent's
``meta.yaml`` — no network, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from packages.agents.prompt_includes import IncludeStatus, resolve_include


def approx_tokens(text: str) -> int:
    """Byte-based token estimate. Mirrors ``context_builder._approx_tokens``.

    Kept local to avoid coupling the GUI server to a private helper in core.
    """
    return len(text.encode("utf-8")) // 4


@dataclass(frozen=True)
class IncludeStatusRow:
    placeholder: str
    filename: str
    status: str  # IncludeStatus.value
    path: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "placeholder": self.placeholder,
            "filename": self.filename,
            "status": self.status,
            "path": self.path,
        }


@dataclass(frozen=True)
class PromptStats:
    char_count: int
    line_count: int
    token_estimate: int
    token_estimate_method: str
    last_modified_iso: str | None
    snapshot_count: int
    prompt_includes: list[IncludeStatusRow]

    def to_json(self) -> dict[str, object]:
        return {
            "char_count": self.char_count,
            "line_count": self.line_count,
            "token_estimate": self.token_estimate,
            "token_estimate_method": self.token_estimate_method,
            "last_modified_iso": self.last_modified_iso,
            "snapshot_count": self.snapshot_count,
            "prompt_includes": [r.to_json() for r in self.prompt_includes],
        }


def _iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def include_status_rows(
    agent_dir: Path,
    prompt_includes: dict[str, str] | None,
) -> list[IncludeStatusRow]:
    """Resolve every declared ``prompt_include`` and summarise its source.

    Example fallbacks (``.md.example``) and missing files surface as non-
    canonical rows so the Stats tab can highlight them the same way CLI
    startup does.
    """
    rows: list[IncludeStatusRow] = []
    for placeholder, filename in (prompt_includes or {}).items():
        res = resolve_include(agent_dir, filename)
        path_str = str(res.path) if res.path is not None else None
        rows.append(
            IncludeStatusRow(
                placeholder=placeholder,
                filename=filename,
                status=res.status.value,
                path=path_str,
            )
        )
    return rows


def compute_stats(
    *,
    system_prompt_path: Path,
    agent_dir: Path,
    prompt_includes: dict[str, str] | None,
    snapshot_count: int,
) -> PromptStats:
    """Compute Stats-tab payload from ``system.md`` content + meta includes.

    Returns an empty stats block (all zeros, ``last_modified_iso=None``) when
    the file is missing — the route layer decides whether that's a 404 or a
    valid state for special cases like JARVIS.
    """
    if system_prompt_path.is_file():
        text = system_prompt_path.read_text(encoding="utf-8")
    else:
        text = ""

    _ = IncludeStatus  # re-exported via the rows; silence unused import check.

    return PromptStats(
        char_count=len(text),
        line_count=text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        token_estimate=approx_tokens(text),
        token_estimate_method="len_utf8_over_4",
        last_modified_iso=_iso_mtime(system_prompt_path),
        snapshot_count=snapshot_count,
        prompt_includes=include_status_rows(agent_dir, prompt_includes),
    )
