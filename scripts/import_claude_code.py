"""Import Claude Code session transcripts into Jarvis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.importers.claude_code import (
    DEFAULT_DESKTOP_SESSIONS_DIR,
    DEFAULT_PROJECTS_DIR,
    import_sessions,
)
from packages.core.settings import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Claude Code session transcripts into Jarvis schema v1.0.0.")
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=DEFAULT_PROJECTS_DIR,
        help=f"Claude Code transcripts directory (default: {DEFAULT_PROJECTS_DIR}).",
    )
    parser.add_argument(
        "--desktop-sessions-dir",
        type=Path,
        default=DEFAULT_DESKTOP_SESSIONS_DIR,
        help="Claude desktop app session metadata, used for titles (default: the app's claude-code-sessions).",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Target directory for converted files (default: paths.conversations_dir from config/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be imported without writing files.",
    )
    parser.add_argument(
        "--date-from",
        type=str,
        default=None,
        help="Only import sessions started on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--date-to",
        type=str,
        default=None,
        help="Only import sessions started on or before this date (YYYY-MM-DD).",
    )

    args = parser.parse_args(argv)
    if args.target_dir is None:
        args.target_dir = PROJECT_ROOT / load_config(PROJECT_ROOT).paths.conversations_dir

    if not args.projects_dir.is_dir():
        print(f"Error: transcripts directory not found: {args.projects_dir}")
        return 1

    mode = "DRY RUN" if args.dry_run else "IMPORT"
    print(f"[{mode}] Claude Code → Jarvis")
    print(f"  Source: {args.projects_dir}")
    print(f"  Target: {args.target_dir}")

    filters = []
    if args.date_from:
        filters.append(f"from {args.date_from}")
    if args.date_to:
        filters.append(f"to {args.date_to}")
    if filters:
        print(f"  Filters: {', '.join(filters)}")

    print()

    summary = import_sessions(
        projects_dir=args.projects_dir,
        target_dir=args.target_dir,
        desktop_sessions_dir=args.desktop_sessions_dir,
        dry_run=args.dry_run,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    action = "Would import" if args.dry_run else "Imported"
    update_action = "Would update" if args.dry_run else "Updated"
    print(f"  Transcripts found: {summary.total}")
    print(f"  {action}: {summary.imported}")
    if summary.updated:
        print(f"  {update_action}: {summary.updated}")
    if summary.skipped_filter:
        print(f"  Skipped (filtered): {summary.skipped_filter}")
    if summary.skipped_empty:
        print(f"  Skipped (no user prompt): {summary.skipped_empty}")
    if summary.skipped_existing:
        print(f"  Skipped (unchanged): {summary.skipped_existing}")
    if summary.errors:
        print(f"  Errors: {summary.errors}")
        for err in summary.error_details:
            print(f"    - {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
