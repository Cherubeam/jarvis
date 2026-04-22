"""
Obsidian vault integration for JARVIS.
Read from and write to Obsidian vaults, starting with daily notes.
"""

from packages.integrations.obsidian.callout import (
    CalloutBlock,
    CalloutNotFound,
    build_updated_content,
    find_jarvis_callout,
    format_callout_entry,
)
from packages.integrations.obsidian.diff import (
    DiffLine,
    VaultDiff,
    compute_diff,
    format_diff_for_api,
    format_diff_for_cli,
)
from packages.integrations.obsidian.vault import (
    VaultConfig,
    get_daily_note_path,
    list_notes,
    load_vault_config,
    read_note,
    validate_read,
    validate_write,
)
from packages.integrations.obsidian.writer import (
    CLIConfirmationHandler,
    ConfirmationHandler,
    WriteResult,
    append_to_daily_note,
    append_to_note,
)

__all__ = [
    "CLIConfirmationHandler",
    "CalloutBlock",
    "CalloutNotFound",
    "ConfirmationHandler",
    "DiffLine",
    "VaultConfig",
    "VaultDiff",
    "WriteResult",
    "append_to_daily_note",
    "append_to_note",
    "build_updated_content",
    "compute_diff",
    "find_jarvis_callout",
    "format_callout_entry",
    "format_diff_for_api",
    "format_diff_for_cli",
    "get_daily_note_path",
    "list_notes",
    "load_vault_config",
    "read_note",
    "validate_read",
    "validate_write",
]
