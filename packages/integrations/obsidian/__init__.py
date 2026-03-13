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
    # vault
    "VaultConfig",
    "load_vault_config",
    "validate_read",
    "validate_write",
    "read_note",
    "list_notes",
    "get_daily_note_path",
    # callout
    "CalloutBlock",
    "CalloutNotFound",
    "find_jarvis_callout",
    "build_updated_content",
    "format_callout_entry",
    # diff
    "DiffLine",
    "VaultDiff",
    "compute_diff",
    "format_diff_for_cli",
    "format_diff_for_api",
    # writer
    "ConfirmationHandler",
    "CLIConfirmationHandler",
    "WriteResult",
    "append_to_daily_note",
    "append_to_note",
]
