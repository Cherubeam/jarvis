"""Prompt-include editor routes — Phase 6 follow-up.

Each agent's ``meta.yaml`` may declare ``prompt_includes``: a mapping from
placeholder name (e.g. ``voice_profile``) to filename (e.g. ``voice-profile``,
no extension). Each ``{placeholder}`` in ``prompts/system.md`` is replaced
with the resolved file's contents at session build time.

These routes let the GUI list, read, and edit those include files — both
agent-local overrides and shared ``_shared/prompts/`` defaults.

- GET    /api/agents/{id}/includes                                   → declared includes
- GET    /api/agents/{id}/includes/{placeholder}                     → one include
- PUT    /api/agents/{id}/includes/{placeholder}                     → write + snapshot
- POST   /api/agents/{id}/includes/{placeholder}/promote             → fork shared/example to local
- GET    /api/agents/{id}/includes/{placeholder}/snapshots           → history listing
- POST   /api/agents/{id}/includes/{placeholder}/restore             → restore a snapshot

Snapshot history is per-(agent_id, placeholder) and stored under
``<history_root>/<agent_id>/_includes/<placeholder>/`` — sharing the same
``prompt_history`` infrastructure as ``system.md``.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.gui.server.agents.prompt_history import (
    ensure_pre_first_save_snapshot,
    list_snapshots,
    read_snapshot,
    write_snapshot,
)
from apps.gui.server.routes.agents import _get_write_lock, _guard_agent_id, _history_root
from packages.agents.prompt_includes import IncludeStatus, resolve_include
from packages.core.frontmatter import write_atomic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_MAX_INCLUDE_BYTES = 1_000_000  # 1 MB — same guardrail as system.md.
_PLACEHOLDER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# Request/response models


class IncludeRow(BaseModel):
    placeholder: str
    filename: str
    status: str  # IncludeStatus.value
    path: str | None  # repo-relative if resolvable
    bytes: int | None
    last_modified_iso: str | None
    editable: bool
    affects_agents: list[str]


class IncludeDetail(IncludeRow):
    content: str


class IncludeSaveRequest(BaseModel):
    content: str
    note: str | None = None


class IncludeRestoreRequest(BaseModel):
    snapshot_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Helpers


def _guard_placeholder(placeholder: str) -> None:
    """Reject placeholder names that don't match Python-identifier-ish form.

    Real-world placeholders are ``voice_profile`` / ``anti_patterns`` etc.
    Anything outside ``[A-Za-z_][A-Za-z0-9_]*`` is rejected to keep paths
    safe and to match how the YAML keys flow into ``str.replace`` substitution.
    """
    if not _PLACEHOLDER_RE.match(placeholder):
        raise HTTPException(status_code=404, detail=f"placeholder '{placeholder}' not declared")


def _meta_dict(meta_path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.debug("failed to re-parse meta.yaml at %s", meta_path, exc_info=True)  # pragma: no mutate
        return {}


def _shared_dir_for(agent_dir: Path) -> Path:
    """Compute the shared-prompts dir relative to ``agent_dir``.

    Mirrors :data:`packages.agents.prompt_includes._DEFAULT_SHARED_DIR` but
    derives the path from the agent's location so tests can stand up a
    self-contained tree under ``tmp_path``.
    """
    return agent_dir.parent / "_shared" / "prompts"


def _resolve(agent_dir: Path, filename: str) -> Any:
    return resolve_include(agent_dir, filename, _shared_dir_for(agent_dir))


def _history_key(agent_id: str, placeholder: str) -> str:
    """Slash-encoded key used as the ``agent_id`` arg to prompt_history.

    Path semantics: ``Path(root) / f"{agent_id}/_includes/{placeholder}"``.
    The resulting subdirectory coexists under ``<root>/<agent_id>/`` next to
    system.md snapshot files; ``_rebuild_index_from_disk`` filters by
    snapshot-filename regex so the directory is silently skipped during
    system.md scans.
    """
    return f"{agent_id}/_includes/{placeholder}"


def _editable_for(status: IncludeStatus) -> bool:
    """Local + shared = editable in place. Examples + missing = promote first."""
    return status in (IncludeStatus.FOUND_LOCAL, IncludeStatus.FOUND_SHARED)


def _repo_rel(path: Path, session: Any) -> str:
    """Best-effort repo-relative string for display."""
    try:
        return str(path.relative_to(session.components.jarvis_dir))
    except ValueError:
        return str(path)


def _affects_agents(
    session: Any,
    self_agent_id: str,
    filename: str,
    self_status: IncludeStatus,
) -> list[str]:
    """List of OTHER agent ids whose include of ``filename`` also resolves shared.

    Returns ``[]`` for any non-shared status — local writes don't propagate.
    Excludes ``self_agent_id`` from the result; the caller knows about itself.
    Calls :func:`resolve_include` per candidate so an agent with its own
    local override is correctly excluded from the affected set.
    """
    if self_status is not IncludeStatus.FOUND_SHARED:
        return []
    out: list[str] = []
    registry = session.components.agent_registry
    for other_id in sorted(registry):
        if other_id == self_agent_id:
            continue
        meta = registry[other_id]
        if meta.meta_path is None:
            continue
        includes = _meta_dict(meta.meta_path).get("prompt_includes") or {}
        if filename not in includes.values():
            continue
        other_dir = meta.meta_path.parent
        if _resolve(other_dir, filename).status is IncludeStatus.FOUND_SHARED:
            out.append(other_id)
    return out


def _row_for(
    agent_id: str,
    placeholder: str,
    filename: str,
    agent_dir: Path,
    session: Any,
) -> IncludeRow:
    res = _resolve(agent_dir, filename)
    path = res.path
    bytes_: int | None = None
    last_modified: str | None = None
    if path is not None and path.is_file():
        st = path.stat()
        bytes_ = st.st_size
        last_modified = datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat()
    return IncludeRow(
        placeholder=placeholder,
        filename=filename,
        status=res.status.value,
        path=_repo_rel(path, session) if path is not None else None,
        bytes=bytes_,
        last_modified_iso=last_modified,
        editable=_editable_for(res.status),
        affects_agents=_affects_agents(session, agent_id, filename, res.status),
    )


# ---------------------------------------------------------------------------
# Routes


@router.get("/agents/{agent_id}/includes")
async def list_includes(agent_id: str, request: Request) -> list[dict[str, Any]]:
    """Return one row per declared ``prompt_include`` for ``agent_id``.

    Empty list for JARVIS (it doesn't declare prompt_includes) and for
    agents whose meta.yaml lacks the field.
    """
    _guard_agent_id(agent_id)
    session = request.app.state.gui_session
    if agent_id == "JARVIS":
        return []
    registry = session.components.agent_registry
    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    meta = registry[agent_id]
    assert meta.meta_path is not None
    includes = _meta_dict(meta.meta_path).get("prompt_includes") or {}
    agent_dir = meta.meta_path.parent
    rows: list[dict[str, Any]] = []
    for placeholder, filename in includes.items():
        rows.append(_row_for(agent_id, placeholder, filename, agent_dir, session).model_dump())
    return rows


def _lookup(agent_id: str, placeholder: str, request: Request) -> tuple[str, Path, Any]:
    """Validate + resolve ``(agent_id, placeholder)``.

    Returns ``(filename, agent_dir, session)``. Raises 404 if the agent is
    unknown or the placeholder isn't declared.
    """
    _guard_agent_id(agent_id)
    _guard_placeholder(placeholder)
    if agent_id == "JARVIS":
        raise HTTPException(status_code=404, detail="JARVIS has no prompt_includes")
    session = request.app.state.gui_session
    registry = session.components.agent_registry
    if agent_id not in registry:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")
    meta = registry[agent_id]
    assert meta.meta_path is not None
    includes = _meta_dict(meta.meta_path).get("prompt_includes") or {}
    if placeholder not in includes:
        raise HTTPException(status_code=404, detail=f"placeholder '{placeholder}' not declared")
    return includes[placeholder], meta.meta_path.parent, session


@router.get("/agents/{agent_id}/includes/{placeholder}")
async def get_include(agent_id: str, placeholder: str, request: Request) -> dict[str, Any]:
    """Return a single include's content + resolution metadata."""
    filename, agent_dir, session = _lookup(agent_id, placeholder, request)
    row = _row_for(agent_id, placeholder, filename, agent_dir, session)
    res = _resolve(agent_dir, filename)
    content = res.path.read_text(encoding="utf-8") if res.path is not None and res.path.is_file() else ""
    return IncludeDetail(**row.model_dump(), content=content).model_dump()


@router.put("/agents/{agent_id}/includes/{placeholder}")
async def save_include(
    agent_id: str,
    placeholder: str,
    payload: IncludeSaveRequest,
    request: Request,
) -> dict[str, Any]:
    """Overwrite the resolved include file with ``payload.content``; snapshot first.

    409 if the include resolves to an example/missing — caller must POST
    ``/promote`` first to create a writable file.
    """
    filename, agent_dir, session = _lookup(agent_id, placeholder, request)

    if len(payload.content.encode("utf-8")) > _MAX_INCLUDE_BYTES:
        raise HTTPException(status_code=413, detail=f"include exceeds {_MAX_INCLUDE_BYTES}-byte cap")

    res = _resolve(agent_dir, filename)
    if not _editable_for(res.status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"include '{placeholder}' is not editable in place "
                f"(status: {res.status.value}). Promote to a local override first."
            ),
        )
    assert res.path is not None  # editable status ⇒ path is real

    target = res.path
    history_root = _history_root(session)
    key = _history_key(agent_id, placeholder)
    lock = await _get_write_lock(request.app, key)

    async with lock:
        prior = target.read_text(encoding="utf-8") if target.is_file() else ""
        ensure_pre_first_save_snapshot(history_root, key, prior)
        snap = write_snapshot(history_root, key, prior, kind="save", note=payload.note)
        write_atomic(target, payload.content)

    st = target.stat()
    return {
        "bytes": st.st_size,
        "last_modified_iso": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
        "snapshot_id": snap.id,
    }


@router.post("/agents/{agent_id}/includes/{placeholder}/promote")
async def promote_include(
    agent_id: str,
    placeholder: str,
    request: Request,
) -> dict[str, Any]:
    """Create ``<agent_dir>/prompts/<filename>.md`` so the include becomes editable.

    - From ``local_example``: copy the agent-local ``.md.example`` content.
    - From ``shared_example``: copy the shared ``.md.example`` content into a new local file.
    - From ``missing``: create an empty local file.
    - 409 if the local file already exists (currently ``local`` or ``shared``
      with a local override would never reach this branch).
    """
    filename, agent_dir, session = _lookup(agent_id, placeholder, request)
    res = _resolve(agent_dir, filename)

    prompts_dir = agent_dir / "prompts"
    if not prompts_dir.is_dir():
        raise HTTPException(status_code=500, detail=f"prompts/ missing for agent '{agent_id}'")

    target = prompts_dir / f"{filename}.md"
    if target.exists():
        raise HTTPException(
            status_code=409,
            detail=(f"local override already exists at {_repo_rel(target, session)}; refresh and edit directly."),
        )

    if res.status is IncludeStatus.MISSING:
        seed = ""
    elif res.status in (IncludeStatus.FOUND_LOCAL_EXAMPLE, IncludeStatus.FOUND_SHARED_EXAMPLE):
        assert res.path is not None
        seed = res.path.read_text(encoding="utf-8")
    else:
        # Already editable in place — promote is a no-op error.
        raise HTTPException(
            status_code=409,
            detail=f"include '{placeholder}' is already editable (status: {res.status.value}).",
        )

    key = _history_key(agent_id, placeholder)
    lock = await _get_write_lock(request.app, key)
    async with lock:
        write_atomic(target, seed)

    return _row_for(agent_id, placeholder, filename, agent_dir, session).model_dump() | {
        "content": seed,
    }


@router.get("/agents/{agent_id}/includes/{placeholder}/snapshots")
async def list_include_snapshots(
    agent_id: str,
    placeholder: str,
    request: Request,
) -> list[dict[str, Any]]:
    """Snapshots for one include, newest-first."""
    _, _, session = _lookup(agent_id, placeholder, request)
    history_root = _history_root(session)
    key = _history_key(agent_id, placeholder)
    return [m.to_json() for m in list_snapshots(history_root, key)]


@router.post("/agents/{agent_id}/includes/{placeholder}/restore")
async def restore_include(
    agent_id: str,
    placeholder: str,
    payload: IncludeRestoreRequest,
    request: Request,
) -> dict[str, Any]:
    """Restore ``payload.snapshot_id``; writes to the include's currently-resolved file.

    If the include has been promoted since the snapshot was taken, restore
    writes to the new local path — i.e. it tracks the resolved target, not
    the path at snapshot time. Pre-restore snapshot is taken first.
    """
    filename, agent_dir, session = _lookup(agent_id, placeholder, request)
    res = _resolve(agent_dir, filename)
    if not _editable_for(res.status):
        raise HTTPException(
            status_code=409,
            detail=(
                f"cannot restore: include '{placeholder}' isn't editable in place "
                f"(status: {res.status.value}). Promote first."
            ),
        )
    assert res.path is not None

    history_root = _history_root(session)
    key = _history_key(agent_id, placeholder)
    lock = await _get_write_lock(request.app, key)
    async with lock:
        snapshot_content = read_snapshot(history_root, key, payload.snapshot_id)
        if snapshot_content is None:
            raise HTTPException(status_code=404, detail=f"snapshot '{payload.snapshot_id}' not found")
        prior = res.path.read_text(encoding="utf-8") if res.path.is_file() else ""
        pre_restore = write_snapshot(
            history_root,
            key,
            prior,
            kind="pre_restore",
            note=f"before restoring {payload.snapshot_id}",
        )
        write_atomic(res.path, snapshot_content)

    st = res.path.stat()
    return {
        "bytes": st.st_size,
        "last_modified_iso": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
        "snapshot_id": pre_restore.id,
    }
