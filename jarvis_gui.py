"""
Entry point for the jarvis GUI server.

Mirrors jarvis_cli.py: bootstraps sys.path before importing project modules.
"""

import sys
from pathlib import Path

_site_packages = Path(__file__).resolve().parent
_pth_file = _site_packages / "_jarvis.pth"

if _pth_file.exists():
    _project_root = _pth_file.read_text().strip().splitlines()[0]
else:
    _project_root = str(_site_packages)

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def main():
    """Entry point that imports and runs the GUI server."""
    from apps.gui.main import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
