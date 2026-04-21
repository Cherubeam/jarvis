"""Import Claude context exports (memories + projects) into Jarvis context files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.importers.claude_context import import_context


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Claude context (memories + projects) into Jarvis context files."
    )
    parser.add_argument(
        "--memories",
        type=Path,
        default=PROJECT_ROOT / "imports" / "memories.json",
        help="Path to Claude memories.json export (default: imports/memories.json).",
    )
    parser.add_argument(
        "--projects",
        type=Path,
        default=PROJECT_ROOT / "imports" / "projects.json",
        help="Path to Claude projects.json export (default: imports/projects.json).",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "context",
        help="Target context directory (default: data/context/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be imported without writing files.",
    )

    args = parser.parse_args()

    # Resolve profile.md path
    profile_path = args.target_dir / "profile.md"
    existing_profile = profile_path if profile_path.exists() else None

    mode = "DRY RUN" if args.dry_run else "IMPORT"
    print(f"[{mode}] Claude Context -> Jarvis")
    print(f"  Memories: {args.memories}")
    print(f"  Projects: {args.projects}")
    print(f"  Target:   {args.target_dir}")
    print()

    summary = import_context(
        memories_path=args.memories if args.memories.exists() else None,
        projects_path=args.projects if args.projects.exists() else None,
        target_dir=args.target_dir,
        existing_profile_path=existing_profile,
        dry_run=args.dry_run,
    )

    action = "Would write" if args.dry_run else "Wrote"
    print(f"  {action}: {len(summary.files_written)} files")
    for f in summary.files_written:
        print(f"    - {f}")

    if summary.projects_imported:
        print(f"  Projects imported: {summary.projects_imported}")
    if summary.projects_skipped:
        print(f"  Projects skipped (starter): {summary.projects_skipped}")
    if summary.docs_saved:
        print(f"  Docs saved: {summary.docs_saved}")

    if summary.files_skipped:
        print(f"  Skipped: {len(summary.files_skipped)} files")
        for f in summary.files_skipped:
            print(f"    - {f}")

    if summary.warnings:
        print("  Warnings:")
        for w in summary.warnings:
            print(f"    - {w}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
