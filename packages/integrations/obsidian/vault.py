"""
Vault access and path validation for Obsidian integration.

Single enforcement point for all vault filesystem operations.
No other module should touch the filesystem for vault operations.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from packages.core.filesystem_access import FilesystemGuard
from packages.core.settings import ObsidianSettings

logger = logging.getLogger(__name__)


@dataclass
class VaultConfig:
    """Configuration for Obsidian vault access."""

    vault_path: Path
    filesystem_guard: FilesystemGuard
    daily_note_path_format: str = "Daily Notes/%Y-%m-%d"
    enabled: bool = True
    # What the agent last saw per note (content hash), so a write can tell when the
    # file changed on disk since then — e.g. the user kept editing in Obsidian.
    read_hashes: dict[Path, str] = field(default_factory=dict, repr=False, compare=False)


def load_vault_config(
    obsidian: ObsidianSettings, filesystem_guard: FilesystemGuard | None = None
) -> VaultConfig | None:
    """Build runtime VaultConfig from ObsidianSettings.

    Returns None if obsidian is disabled or vault_path doesn't resolve.
    """
    if not obsidian.enabled:
        return None

    if not obsidian.vault_path:
        logger.warning("Obsidian enabled but vault_path not set")
        return None

    vault_path = Path(obsidian.vault_path).expanduser().resolve()
    if not vault_path.is_dir():
        logger.warning(f"Vault path does not exist: {vault_path}")
        return None

    if filesystem_guard is None:
        filesystem_guard = FilesystemGuard([])

    return VaultConfig(
        vault_path=vault_path,
        filesystem_guard=filesystem_guard,
        daily_note_path_format=obsidian.daily_notes.path_format,
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


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def record_read(path: Path, content: str, vault_config: VaultConfig) -> None:
    """Remember the version of a note the agent has seen (or just wrote)."""
    vault_config.read_hashes[path.resolve()] = _content_hash(content)


def changed_since_read(path: Path, current_content: str, vault_config: VaultConfig) -> bool:
    """True when the agent read this note and it has changed on disk since.

    Notes the agent never read are not tracked and return False.
    """
    seen = vault_config.read_hashes.get(path.resolve())
    return seen is not None and seen != _content_hash(current_content)


STALE_READ_MESSAGE = (
    "Error: {path} changed on disk since you read it (probably edited in Obsidian). "
    "Nothing was written. Read it again and redo the change on the current version."
)


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
