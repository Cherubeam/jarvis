"""Shared utilities for conversation importers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ImportSummary:
    """Summary of an import operation."""

    total: int = 0
    imported: int = 0
    skipped_existing: int = 0
    skipped_archived: int = 0
    skipped_filter: int = 0
    updated: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)


def make_conv_id(source_uuid: str, dt: datetime) -> str:
    """Generate a deterministic conv_id from a source UUID and datetime.

    Format: conv_YYYYMMDD_HHMMSS_4hex
    The 4 hex chars are derived from a SHA-256 of the source UUID.
    """
    hex_suffix = hashlib.sha256(source_uuid.encode()).hexdigest()[:4]
    return f"conv_{dt.strftime('%Y%m%d')}_{dt.strftime('%H%M%S')}_{hex_suffix}"


def make_filename(dt: datetime) -> str:
    """Generate a filename from a datetime.

    Format: YYYY-MM-DD_HH-MM-SS.json
    """
    return dt.strftime("%Y-%m-%d_%H-%M-%S.json")
