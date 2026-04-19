"""Entry point: `uv run jarvis-gui` launches the FastAPI server and opens the browser."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser

import uvicorn

from apps.gui.server.app import create_app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8123


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="jarvis-gui", description="Launch the JARVIS GUI server.")
    p.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST}).")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT}).")
    p.add_argument("--no-browser", action="store_true", help="Don't auto-open the browser.")
    p.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug"])
    return p.parse_args(argv)


def _open_browser_when_ready(url: str, delay_s: float = 0.8) -> None:
    """Wait briefly for uvicorn to start listening, then open the URL."""
    def _go():
        time.sleep(delay_s)
        try:
            webbrowser.open(url)
        except Exception:
            logging.exception("webbrowser.open failed; visit manually: %s", url)
    threading.Thread(target=_go, daemon=True).start()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = create_app()

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        _open_browser_when_ready(url)

    print(f"JARVIS GUI listening on {url}")
    print("Tip: --no-browser to skip auto-open. CTRL+C to quit.")

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
