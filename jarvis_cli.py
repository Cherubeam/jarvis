"""
Entry point for the jarvis CLI.

This module bootstraps sys.path before importing project modules,
working around Python 3.13+ behavior where .pth files with the macOS
hidden flag are skipped during site initialization.
"""

import sys
from pathlib import Path

# When installed via hatchling force-include, __file__ resolves to
# site-packages/jarvis_cli.py.  Read the project root from the .pth
# file that the editable install wrote next to us.
_site_packages = Path(__file__).resolve().parent
_pth_file = _site_packages / "_jarvis.pth"

if _pth_file.exists():
    _project_root = _pth_file.read_text().strip().splitlines()[0]
else:
    # Fallback: assume running from project root directly
    _project_root = str(_site_packages)

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main() -> None:
    """Entry point that imports and runs the actual CLI."""
    from apps.cli.main import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
