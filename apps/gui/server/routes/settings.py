"""Settings GUI routes.

- ``GET  /api/settings``          — current ``Settings`` + defaults + overrides
- ``GET  /api/settings/schema``   — dereferenced JSON schema (no ``$ref``)
- ``PUT  /api/settings``          — validate + write ``config/local.yaml``

Writes happen as a diff-from-defaults overlay: only user-customised fields
appear on disk. The first write over a hand-crafted ``local.yaml`` requires
``accept_overwrite: true`` to prevent silent data loss (see
:func:`_has_managed_header`).

Validation errors are normalised with ``card_loc`` and ``kind`` so the GUI
can attach field-level errors inline and model-validator errors (e.g. an
MCP server missing ``command`` on stdio) at the enclosing card header.

In-process behaviour on save: ``session.components.settings`` is rebound
to the new ``Settings`` instance. Fields read per request (see
:data:`packages.core.settings.HOT_APPLY_PATHS`) then take effect
immediately; other fields were captured at startup by ``build_session``
into closures and need a restart. The response lists both buckets so the
GUI footer can say "applied live" vs "restart required" honestly.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from packages.core.frontmatter import write_atomic
from packages.core.settings import (
    Settings,
    classify_changes,
    dereferenced_schema,
    diff_from_defaults,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


MANAGED_HEADER = "# Managed by JARVIS Settings — regenerate via Settings view."


# ---------------------------------------------------------------------------
# Request/response models


class PutSettingsRequest(BaseModel):
    """Body for ``PUT /api/settings``.

    ``settings`` carries the full intended state as returned by ``GET``. The
    server re-derives the diff vs defaults to minimise what lands in
    ``config/local.yaml``.
    """

    settings: dict[str, Any] = Field(..., description="Full intended Settings state")
    accept_overwrite: bool = Field(
        default=False,
        description="Set true to overwrite a hand-crafted local.yaml (no managed header).",
    )


# ---------------------------------------------------------------------------
# Helpers


def _local_yaml_path(session: Any) -> Path:
    return Path(session.components.jarvis_dir) / "config" / "local.yaml"


def _has_managed_header(path: Path) -> bool:
    """True iff ``path`` exists and its first non-blank line is :data:`MANAGED_HEADER`.

    Used as the sentinel that ``local.yaml`` was previously GUI-written. A
    missing file or a blank file returns False — first-save against either
    still goes through the overwrite guard, but the user can set
    ``accept_overwrite: true`` once to start managing it.
    """
    if not path.is_file():
        return False
    try:
        with path.open() as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                return line == MANAGED_HEADER
    except OSError:
        return False
    return False


async def _get_write_lock(app: Any) -> asyncio.Lock:
    """Return the single settings write lock, creating it on first use.

    Mirrors the lazy init pattern in ``apps/gui/server/routes/agents.py``.
    Tests that build an app without running the lifespan still work.
    """
    lock = getattr(app.state, "settings_write_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        app.state.settings_write_lock = lock
    return lock


def _classify_error(loc: tuple[Any, ...], schema: dict[str, Any]) -> tuple[str, list[Any]]:
    """Walk ``schema`` alongside ``loc``; return ``(kind, card_loc)``.

    ``kind`` is ``"field"`` when ``loc`` lands on a scalar leaf, otherwise
    ``"model_validator"`` (loc stops at a nested-model boundary — e.g.
    ``MCPServerSettings._validate_transport_fields`` raises at the server
    dict rather than the missing ``command`` field).

    ``card_loc`` is ``loc[:-1]`` for field errors (points at the parent
    section) and ``loc`` itself for model-validator errors.
    """
    current: Any = schema
    for segment in loc:
        if not isinstance(current, dict):
            current = None  # pragma: no mutate
            break
        if isinstance(segment, int):
            current = current.get("items")
        else:
            props = current.get("properties")
            if isinstance(props, dict) and segment in props:
                current = props[segment]
                continue
            additional = current.get("additionalProperties")
            if isinstance(additional, dict):
                current = additional
                continue
            current = None  # pragma: no mutate

    loc_list = list(loc)
    if isinstance(current, dict) and (
        current.get("type") == "object" or "properties" in current or "additionalProperties" in current
    ):
        return "model_validator", loc_list
    return "field", loc_list[:-1]


def _normalize_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Attach ``card_loc`` + ``kind`` to every error from ``exc.errors()``.

    Frontend maps ``kind == "field"`` to inline error text under the input;
    ``kind == "model_validator"`` renders a red header on the panel card at
    ``card_loc``.
    """
    schema = dereferenced_schema()
    out: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        kind, card_loc = _classify_error(loc, schema)
        out.append(
            {
                "loc": list(loc),
                "card_loc": card_loc,
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
                "kind": kind,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Routes


@router.get("/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    """Return the current settings state, defaults, and the overrides diff.

    ``jarvis_dir`` is excluded via the model field's ``exclude=True`` — the
    test suite pins this so a leaking refactor is caught early.
    """
    session = request.app.state.gui_session
    settings: Settings = session.components.settings

    current = settings.model_dump()
    defaults = Settings().model_dump()
    overrides = diff_from_defaults(settings)

    local_path = _local_yaml_path(session)
    return {
        "settings": current,
        "defaults": defaults,
        "overrides": overrides,
        "local_yaml_has_managed_header": _has_managed_header(local_path),
        "paths": {
            "default_yaml": "config/default.yaml",
            "local_yaml": "config/local.yaml",
        },
    }


@router.get("/settings/schema")
async def get_settings_schema() -> dict[str, Any]:
    """Return ``Settings.model_json_schema()`` with every ``$ref`` inlined."""
    return dereferenced_schema()


@router.put("/settings")
async def put_settings(payload: PutSettingsRequest, request: Request) -> dict[str, Any]:
    """Validate, compute diff, and atomically write ``config/local.yaml``.

    Fails with:

    - ``409`` if the current ``local.yaml`` lacks the managed header and
      ``accept_overwrite`` is not ``True``.
    - ``422`` on pydantic validation failure. The body lists normalised
      errors (``loc``, ``card_loc``, ``msg``, ``type``, ``kind``).
    - ``500`` on disk write failure. ``local.yaml`` is left unchanged
      thanks to the atomic tmp + rename.

    On success the in-memory ``components.settings`` is rebound to the new
    instance (preserving the runtime-injected ``jarvis_dir``). Fields in
    :data:`packages.core.settings.HOT_APPLY_PATHS` take effect immediately
    because the GUI bridge reads them off ``components.settings`` at the
    top of each turn; other fields stay captured in tool / client closures
    and need a restart. The response reports both buckets.
    """
    session = request.app.state.gui_session
    local_path = _local_yaml_path(session)
    current_settings: Settings = session.components.settings

    # Managed-header guard — refuse to overwrite a user's hand-crafted file
    # without explicit acknowledgement.
    if local_path.is_file() and not _has_managed_header(local_path) and not payload.accept_overwrite:
        raise HTTPException(
            status_code=409,
            detail=(
                "config/local.yaml was not written by JARVIS Settings. "
                "Review its contents and resubmit with accept_overwrite: true to overwrite."
            ),
        )

    try:
        new_settings = Settings.model_validate(payload.settings)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=_normalize_validation_errors(exc),
        ) from exc

    diff = diff_from_defaults(new_settings)

    body = yaml.safe_dump(diff, sort_keys=False, default_flow_style=False, allow_unicode=True)
    content = f"{MANAGED_HEADER}\n{body}"

    lock = await _get_write_lock(request.app)
    async with lock:
        try:
            write_atomic(local_path, content)
        except OSError as exc:
            logger.exception("failed to write %s", local_path)
            raise HTTPException(status_code=500, detail="failed to write config/local.yaml") from exc

        # Classify changes vs the in-memory state captured BEFORE rebind,
        # then rebind so hot fields take effect on the next turn.
        classification = classify_changes(
            current_settings.model_dump(),
            new_settings.model_dump(),
        )
        new_settings.jarvis_dir = current_settings.jarvis_dir
        session.components.settings = new_settings

    return {
        "overrides": diff,
        "bytes": len(content.encode("utf-8")),
        "restart_required": classification["restart_required"],
        "hot_applied_fields": classification["hot_applied_fields"],
        "restart_required_fields": classification["restart_required_fields"],
    }
