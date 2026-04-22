"""
Vault access and path validation for Obsidian integration.

Single enforcement point for all vault filesystem operations.
No other module should touch the filesystem for vault operations.
"""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.filesystem_access import FilesystemGuard

logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Configuration for Obsidian vault access."""

    vault_path: Path
    filesystem_guard: FilesystemGuard
    daily_note_path_format: str = "Daily Notes/%Y-%m-%d"
    enabled: bool = True


def load_vault_config(config: dict[str, Any], filesystem_guard: FilesystemGuard | None = None) -> VaultConfig | None:
    """Load vault configuration from config dictionary.

    Args:
        config: Full application config dictionary.
        filesystem_guard: Pre-built guard. If None, a guard with no rules is used.

    Returns None if obsidian is disabled or not configured.
    """
    obsidian_config = config.get("obsidian", {})

    if not obsidian_config.get("enabled", False):
        return None

    vault_path_str = obsidian_config.get("vault_path", "")
    if not vault_path_str:
        logger.warning("Obsidian enabled but vault_path not set")
        return None

    vault_path = Path(vault_path_str).expanduser().resolve()
    if not vault_path.is_dir():
        logger.warning(f"Vault path does not exist: {vault_path}")
        return None

    if filesystem_guard is None:
        filesystem_guard = FilesystemGuard([])

    daily_notes = obsidian_config.get("daily_notes", {})
    path_format = daily_notes.get("path_format", "Daily Notes/%Y-%m-%d")

    return VaultConfig(
        vault_path=vault_path,
        filesystem_guard=filesystem_guard,
        daily_note_path_format=path_format,
        enabled=True,
    )


def validate_read(path: Path, vault_config: VaultConfig) -> bool:
    """Check whether read access is allowed for a path via the filesystem guard."""
    return vault_config.filesystem_guard.check_read(path)


def validate_write(path: Path, vault_config: VaultConfig) -> bool:
    """Check whether write access is allowed for a path via the filesystem guard."""
    return vault_config.filesystem_guard.check_write(path)


def read_note(path: Path, vault_config: VaultConfig) -> str:
    """Read a note from the vault.

    Raises:
        PermissionError: If path is not readable.
        FileNotFoundError: If note does not exist.
    """
    if not validate_read(path, vault_config):
        raise PermissionError(f"Access denied: {path} is not readable")

    return path.read_text(encoding="utf-8")


def list_notes(directory: Path, vault_config: VaultConfig, pattern: str = "*.md") -> list[Path]:
    """List notes in a directory within the vault.

    Raises:
        PermissionError: If directory is not readable.
    """
    if not validate_read(directory, vault_config):
        raise PermissionError(f"Access denied: {directory} is not readable")

    if not directory.is_dir():
        return []

    return sorted(directory.glob(pattern))


def get_daily_note_path(vault_config: VaultConfig, target_date: str | None = None) -> Path:
    """Get the path to a daily note.

    Args:
        vault_config: Vault configuration.
        target_date: Date string in YYYY-MM-DD format. Defaults to today.

    Returns:
        Path to the daily note file.
    """
    if target_date:
        d = date.fromisoformat(target_date)
    else:
        d = date.today()

    subpath = d.strftime(vault_config.daily_note_path_format) + ".md"
    return vault_config.vault_path / subpath
