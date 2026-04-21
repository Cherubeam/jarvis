"""
Prompt-include resolution for data-driven agents.

Each agent's ``meta.yaml`` may declare ``prompt_includes`` — a mapping from
placeholder name to filename (without ``.md`` extension). During agent
instantiation, each ``{placeholder}`` in ``prompts/system.md`` is replaced
with the contents of the resolved file.

Resolution order (first hit wins):

1. ``<agent_dir>/prompts/<filename>.md``           — personal override, may
                                                     be gitignored
2. ``packages/agents/_shared/prompts/<filename>.md`` — framework default
3. ``<agent_dir>/prompts/<filename>.md.example``   — committed starter
                                                     template (warns on use)
4. ``packages/agents/_shared/prompts/<filename>.md.example`` — shared
                                                     starter (warns on use)
5. None — warn, placeholder renders as an empty string.

The function :func:`validate_agent_includes` inspects every declared
include across all agents and surfaces anything that isn't a canonical
hit (levels 1 or 2). Call it once at CLI startup to fail soft with
actionable warnings instead of hitting a FileNotFoundError mid-stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

# Default location for shared prompt includes — resolved lazily so tests can
# pass their own directory via ``shared_dir`` if needed.
_DEFAULT_SHARED_DIR = Path(__file__).parent / "_shared" / "prompts"


class IncludeStatus(Enum):
    """Where a prompt_include file was found during resolution."""

    FOUND_LOCAL = "found_local"
    FOUND_SHARED = "found_shared"
    FOUND_LOCAL_EXAMPLE = "found_local_example"
    FOUND_SHARED_EXAMPLE = "found_shared_example"
    MISSING = "missing"


@dataclass(frozen=True)
class IncludeResolution:
    """Result of resolving a prompt_include filename to a filesystem path."""

    path: Path | None
    status: IncludeStatus

    @property
    def is_example(self) -> bool:
        """True if the resolution fell through to a ``.md.example`` file."""
        return self.status in (
            IncludeStatus.FOUND_LOCAL_EXAMPLE,
            IncludeStatus.FOUND_SHARED_EXAMPLE,
        )

    @property
    def is_missing(self) -> bool:
        """True if no candidate file was found."""
        return self.status is IncludeStatus.MISSING

    @property
    def is_canonical(self) -> bool:
        """True if the resolution hit a canonical ``.md`` file (not an example)."""
        return self.status in (
            IncludeStatus.FOUND_LOCAL,
            IncludeStatus.FOUND_SHARED,
        )


def resolve_include(
    agent_dir: Path,
    filename: str,
    shared_dir: Path = _DEFAULT_SHARED_DIR,
) -> IncludeResolution:
    """Resolve a prompt_include filename to an actual file path.

    Args:
        agent_dir: The agent's root directory (containing ``meta.yaml``
            and ``prompts/``).
        filename: The filename declared in ``meta.yaml`` (without
            ``.md`` extension).
        shared_dir: Directory for shared fallback prompts. Defaults to
            ``packages/agents/_shared/prompts/``.

    Returns:
        :class:`IncludeResolution` describing which candidate was found.
        When nothing was found, ``path`` is ``None`` and the status is
        :attr:`IncludeStatus.MISSING`.
    """
    local_md = agent_dir / "prompts" / f"{filename}.md"
    if local_md.is_file():
        return IncludeResolution(local_md, IncludeStatus.FOUND_LOCAL)

    shared_md = shared_dir / f"{filename}.md"
    if shared_md.is_file():
        return IncludeResolution(shared_md, IncludeStatus.FOUND_SHARED)

    local_example = agent_dir / "prompts" / f"{filename}.md.example"
    if local_example.is_file():
        return IncludeResolution(local_example, IncludeStatus.FOUND_LOCAL_EXAMPLE)

    shared_example = shared_dir / f"{filename}.md.example"
    if shared_example.is_file():
        return IncludeResolution(shared_example, IncludeStatus.FOUND_SHARED_EXAMPLE)

    return IncludeResolution(None, IncludeStatus.MISSING)


@dataclass(frozen=True)
class AgentIncludeIssue:
    """A prompt_include that resolved to something other than a canonical ``.md``.

    Canonical hits (agent-local ``.md`` or shared ``.md``) are considered
    healthy and aren't reported — only example fallbacks and fully
    missing includes surface as issues.
    """

    agent_name: str
    placeholder: str
    filename: str
    resolution: IncludeResolution


def validate_agent_includes(
    meta_paths: list[Path],
    shared_dir: Path = _DEFAULT_SHARED_DIR,
) -> list[AgentIncludeIssue]:
    """Inspect every agent's ``meta.yaml`` for problematic prompt_includes.

    Args:
        meta_paths: List of ``meta.yaml`` paths to inspect. Typically the
            ``meta_path`` fields of a discovered agent registry.
        shared_dir: Directory for shared fallback prompts.

    Returns:
        List of :class:`AgentIncludeIssue` — one per include that fell back
        to a ``.md.example`` file or couldn't be resolved at all. Canonical
        hits are silently skipped.
    """
    issues: list[AgentIncludeIssue] = []
    for meta_path in meta_paths:
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            # Malformed meta.yaml — let discovery's own warning handle it.
            continue

        includes = meta.get("prompt_includes") or {}
        if not includes:
            continue

        agent_dir = meta_path.parent
        agent_name = meta.get("name", agent_dir.name)
        for placeholder, filename in includes.items():
            res = resolve_include(agent_dir, filename, shared_dir)
            if not res.is_canonical:
                issues.append(
                    AgentIncludeIssue(
                        agent_name=agent_name,
                        placeholder=placeholder,
                        filename=filename,
                        resolution=res,
                    )
                )
    return issues


def format_issue(issue: AgentIncludeIssue) -> str:
    """Render a single issue as a one-line warning for terminal output."""
    if issue.resolution.is_missing:
        return (
            f"Agent '{issue.agent_name}': prompt_include '{issue.placeholder}' "
            f"→ '{issue.filename}.md' not found in agent prompts/ or _shared/prompts/. "
            f"Placeholder will render as empty."
        )
    # example fallback
    assert issue.resolution.path is not None
    return (
        f"Agent '{issue.agent_name}': prompt_include '{issue.placeholder}' "
        f"→ '{issue.filename}.md' not found; falling back to "
        f"'{issue.resolution.path.name}'."
    )
