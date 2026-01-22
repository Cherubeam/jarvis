"""
Entry point for the jarvis CLI.

This module bootstraps sys.path before importing project modules,
working around Python 3.13+ behavior where .pth files with the macOS
hidden flag are skipped during site initialization.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path for editable installs
_project_root = str(Path(__file__).parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main():
    """Entry point that imports and runs the actual CLI."""
    from apps.cli.main import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
