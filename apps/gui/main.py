"""Entry point: `uv run jarvis-gui` launches the FastAPI server and opens the browser."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import webbrowser

import uvicorn
from dotenv import load_dotenv

from apps.gui.server.app import create_app
from apps.gui.server.auth import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    GuiAuth,
    bootstrap_url,
    install_access_log_redaction,
)
from packages.core.settings import get_project_root, load_config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="jarvis-gui", description="Launch the JARVIS GUI server.")
    p.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host (default: {DEFAULT_HOST}).")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port (default: {DEFAULT_PORT}).")
    p.add_argument("--no-browser", action="store_true", help="Don't auto-open the browser.")
    p.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug"])
    return p.parse_args(argv)


def _open_browser_when_ready(url: str, delay_s: float = 0.8) -> None:
    """Wait briefly for uvicorn to start listening, then open the URL."""

    def _go() -> None:
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

    jarvis_dir = get_project_root()
    # The GUI never loaded .env before (only apps/cli/main.py did), so
    # JARVIS_GUI_TOKEN there was silently ignored — and OPENROUTER_API_KEY had
    # to be exported in the shell, since collect_api_keys() reads os.environ.
    # Additive: load_dotenv does not override variables already set.
    load_dotenv(jarvis_dir / ".env")

    # A second load_config() — the first is inside build_gui_session() during
    # lifespan. Only gui.allowed_origins is read here, before the app exists.
    settings = load_config(jarvis_dir)

    auth = GuiAuth.create(
        args.host,
        args.port,
        project_root=jarvis_dir,
        extra_origins=settings.gui.allowed_origins,
    )
    # uvicorn's access log records the full request line, query string included,
    # so without this the sign-in URL would print the token to stdout.
    install_access_log_redaction()

    app = create_app(auth)

    url = f"http://{args.host}:{args.port}/"
    sign_in = bootstrap_url(args.host, args.port, auth.token)
    if not args.no_browser:
        _open_browser_when_ready(sign_in)

    # print(), not logging: logging may be redirected to a file or aggregated,
    # and this line carries the token.
    print(f"JARVIS GUI listening on {url}")
    print(f"Sign in:  {sign_in}")
    print("Tip: --no-browser to skip auto-open. CTRL+C to quit.")

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
