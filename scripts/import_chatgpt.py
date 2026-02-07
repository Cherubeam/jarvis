"""Import ChatGPT conversation exports into Jarvis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.importers.chatgpt import import_conversations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import ChatGPT conversations into Jarvis schema v1.0.0."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to ChatGPT conversations.json export file.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "conversations",
        help="Target directory for converted files (default: data/conversations/).",
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
        help="Only import conversations created on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--date-to",
        type=str,
        default=None,
        help="Only import conversations created on or before this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Only import conversations using this model slug (e.g. gpt-4o).",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived conversations (excluded by default).",
    )

    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: source file not found: {args.source}")
        return 1

    mode = "DRY RUN" if args.dry_run else "IMPORT"
    print(f"[{mode}] ChatGPT → Jarvis")
    print(f"  Source: {args.source}")
    print(f"  Target: {args.target_dir}")

    filters = []
    if args.date_from:
        filters.append(f"from {args.date_from}")
    if args.date_to:
        filters.append(f"to {args.date_to}")
    if args.model:
        filters.append(f"model={args.model}")
    if args.include_archived:
        filters.append("including archived")
    if filters:
        print(f"  Filters: {', '.join(filters)}")

    print()

    summary = import_conversations(
        source_path=args.source,
        target_dir=args.target_dir,
        dry_run=args.dry_run,
        date_from=args.date_from,
        date_to=args.date_to,
        model_filter=args.model,
        include_archived=args.include_archived,
    )

    action = "Would import" if args.dry_run else "Imported"
    print(f"  Total conversations in file: {summary.total}")
    print(f"  {action}: {summary.imported}")
    if summary.skipped_archived:
        print(f"  Skipped (archived): {summary.skipped_archived}")
    if summary.skipped_filter:
        print(f"  Skipped (filtered): {summary.skipped_filter}")
    if summary.skipped_existing:
        print(f"  Skipped (already exists): {summary.skipped_existing}")
    if summary.errors:
        print(f"  Errors: {summary.errors}")
        for err in summary.error_details:
            print(f"    - {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
