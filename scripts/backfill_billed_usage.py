"""Replace estimated usage in saved conversation logs with OpenRouter's billed records.

Streamed turns are logged with LiteLLM's local estimate and their generation ids. The
session logger swaps them for billed records when it saves, but a record is published
~10-15 s after the turn, so the last turn before exit usually stays estimated. This
fixes those afterwards. Logs from before 2026-09-29 have no generation ids and can't be
corrected; their costs are lower bounds.

Usage:
    uv run python scripts/backfill_billed_usage.py            # all logs
    uv run python scripts/backfill_billed_usage.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from packages.core.memory import reconcile_estimated_messages
from packages.core.model_resolver import collect_api_keys, get_api_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=PROJECT_ROOT / "data" / "conversations")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = get_api_key("openrouter", collect_api_keys())
    if not api_key:
        print("No OpenRouter API key found.")
        return 1

    files = messages = 0
    cost_delta = 0.0
    for path in sorted(args.dir.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        updated, deltas = reconcile_estimated_messages(data.get("messages", []), api_key, deadline_s=5.0)
        if not updated:
            continue
        files += 1
        messages += updated
        cost_delta += deltas["total_cost_usd"]
        print(f"{path.name}: {updated} message(s), cost {deltas['total_cost_usd']:+.4f} USD")
        if args.dry_run:
            continue
        metrics = data.setdefault("metrics", {})
        for name, delta in deltas.items():
            metrics[name] = metrics.get(name, 0) + delta
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    verb = "Would update" if args.dry_run else "Updated"
    print(f"{verb} {messages} message(s) in {files} file(s); cost {cost_delta:+.4f} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
