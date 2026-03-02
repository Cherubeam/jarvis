#!/usr/bin/env bash
# Link private skill directories into packages/skills/ so the JARVIS
# skill registry discovers them transparently via symlinks.
#
# Usage:
#   ./scripts/link_skills.sh                       # default sibling path
#   ./scripts/link_skills.sh /path/to/private/repo  # custom path

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/packages/skills"

# Default: sibling repo relative to this repo's parent
SOURCE="${1:-$(cd "$REPO_ROOT/.." && pwd)/agent-capability-specifications}"

if [ ! -d "$SOURCE" ]; then
    echo "Error: source directory not found: $SOURCE" >&2
    exit 1
fi

linked=0
skipped=0

for dir in "$SOURCE"/*/; do
    [ -d "$dir" ] || continue

    dirname="$(basename "$dir")"

    # Skip hidden and underscore-prefixed directories
    case "$dirname" in
        .* | _*) continue ;;
    esac

    target="$SKILLS_DIR/$dirname"

    if [ -L "$target" ]; then
        existing="$(readlink "$target")"
        real_source="$(cd "$dir" && pwd)"
        if [ "$existing" = "$real_source" ] || [ "$existing" = "$dir" ]; then
            echo "  skip  $dirname (symlink already correct)"
            skipped=$((skipped + 1))
            continue
        else
            echo "  update $dirname (was → $existing)"
            rm "$target"
        fi
    elif [ -e "$target" ]; then
        echo "  skip  $dirname (real directory exists, not a symlink)"
        skipped=$((skipped + 1))
        continue
    fi

    ln -s "$(cd "$dir" && pwd)" "$target"
    echo "  link  $dirname → $target"
    linked=$((linked + 1))
done

echo ""
echo "Done: $linked linked, $skipped skipped"
