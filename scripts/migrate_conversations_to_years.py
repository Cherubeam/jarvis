"""Migrate flat data/conversations/*.json into year-based subdirectories.

Scans only root-level JSON files (not already in a year subdir) and moves
each file into data/conversations/YYYY/ based on the filename prefix.

Usage:
    uv run python scripts/migrate_conversations_to_years.py
"""

from pathlib import Path


def main():
    conversations_dir = Path(__file__).resolve().parent.parent / "data" / "conversations"

    if not conversations_dir.exists():
        print(f"Directory not found: {conversations_dir}")
        return

    # Only grab root-level JSON files (not already in year subdirs)
    files = sorted(conversations_dir.glob("*.json"))

    if not files:
        print("No flat conversation files to migrate.")
        return

    moved = 0
    for f in files:
        # Parse year from filename: YYYY-MM-DD_HH-MM-SS.json
        year = f.name[:4]
        if not year.isdigit():
            print(f"  Skipping (unexpected name): {f.name}")
            continue

        year_dir = conversations_dir / year
        year_dir.mkdir(exist_ok=True)

        dest = year_dir / f.name
        f.rename(dest)
        moved += 1

    print(f"Migrated {moved} file(s) into year subdirectories.")

    # Show resulting structure
    for d in sorted(conversations_dir.iterdir()):
        if d.is_dir() and d.name.isdigit():
            count = len(list(d.glob("*.json")))
            print(f"  {d.name}/  ({count} files)")


if __name__ == "__main__":
    main()
