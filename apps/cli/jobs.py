"""Unattended jobs: `jarvis run-job <name>` (AON-02).

No front end is attached: nothing can be asked, so a job refuses what a session would ask
about. Each source fails on its own: its section says "not available" and the job goes on.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from apps.cli.review import load_pending_due
from packages.core.briefing import Section, build_messages, save_briefing
from packages.core.cost_ledger import CostLedger
from packages.core.filesystem_access import load_filesystem_guard
from packages.core.llm_client import LLMClient, reported_cost
from packages.core.model_resolver import collect_api_keys, resolve_model
from packages.core.pricing import calculate_cost_from_litellm
from packages.core.settings import Settings, load_config
from packages.core.tools.personal_intelligence_tools import format_direction_map
from packages.integrations.obsidian.vault import get_daily_note_path, load_vault_config, read_note
from packages.integrations.personal_intelligence.client import PersonalIntelligenceClient
from packages.integrations.readwise.client import ReadwiseClient, is_cli_available, parse_json_output
from packages.integrations.things3.task_sync import sync_tasks_to_file

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_READING_LISTS = ("shortlist", "later")


def _gather_tasks(settings: Settings, root: Path) -> Section:
    section = Section("tasks", "Things tasks")
    path = root / settings.paths.tasks_file
    fresh = sync_tasks_to_file(path, settings.things3)
    if not path.is_file():
        section.problem = "the Things export failed and there is no earlier task list"
        return section
    section.text = path.read_text(encoding="utf-8")
    if not fresh:
        age = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        section.text = f"(Things export failed: list from {age}, may be stale. Say so.)\n{section.text}"
    return section


def _gather_daily_note(settings: Settings, day: date) -> Section:
    """Yesterday's note, for the review. At 07:30 today's rarely exists; no note is no gap."""
    section = Section("daily_note", "Yesterday's daily note")
    vault = load_vault_config(settings.obsidian, filesystem_guard=load_filesystem_guard(settings.filesystem))
    if vault is None:
        section.problem = "no vault configured"
        return section
    yesterday = (day - timedelta(days=1)).isoformat()
    try:
        section.text = read_note(get_daily_note_path(vault, yesterday), vault)
    except FileNotFoundError:
        return section
    section.title = f"Daily note of {yesterday}"
    return section


def _gather_outcomes(settings: Settings, root: Path, day: date) -> Section:
    section = Section("outcomes", "Recommendations due for review")
    if not settings.outcomes.enabled:
        section.problem = "outcome tracking is off"
        return section
    due = load_pending_due(root / settings.outcomes.dir, day)
    lines = [f"- {item.meta.get('what', item.path.stem)} (due {item.meta.get('revisit_at')})" for item in due]
    section.text = "\n".join(lines) or "None due."
    return section


def _gather_career(settings: Settings) -> Section:
    section = Section("career", "Career direction map", fenced=True)
    pi = settings.personal_intelligence
    if not pi.enabled:
        section.problem = "Personal Intelligence is off"
        return section
    snapshot = PersonalIntelligenceClient(pi.url, pi.token_file, pi.timeout_seconds).direction_map()
    if snapshot is None:
        section.problem = "the app has no direction map yet"
        return section
    section.text = format_direction_map(snapshot)
    return section


def _gather_reading(settings: Settings) -> Section:
    section = Section("reading", "Reading list (newest from Shortlist and Later)")
    if not is_cli_available():
        section.problem = "the readwise command is not on PATH"
        return section
    client = ReadwiseClient()
    items: list[dict[str, Any]] = []
    for location in _READING_LISTS:
        parsed = parse_json_output(client.list_documents(location, settings.briefing.reading_items))
        if isinstance(parsed, str):
            section.problem = parsed
            return section
        results = parsed.get("results", []) if isinstance(parsed, dict) else parsed
        items.extend(results)
    section.text = json.dumps(
        [
            {
                "title": doc.get("title"),
                "site": doc.get("site_name"),
                "summary": (doc.get("summary") or "")[:300],
                "time": doc.get("reading_time") or doc.get("listening_time"),
                "url": doc.get("url"),
            }
            for doc in items
        ],
        ensure_ascii=False,
        indent=0,
    )
    return section


def _gather_focus(settings: Settings, root: Path) -> Section:
    section = Section("focus", "Current focus")
    path = root / settings.paths.context_dir / settings.paths.context_files.focus
    if path.is_file():
        section.text = path.read_text(encoding="utf-8")
    else:
        section.problem = "no current-focus file"
    return section


def _safely(gather: Callable[[], Section], key: str, title: str) -> Section:
    """One source's failure costs its section, never the briefing."""
    try:
        return gather()
    except Exception as e:
        logger.warning("Briefing source %s failed: %s", key, e)
        return Section(key, title, problem=f"{type(e).__name__} while reading it")


def gather_sections(settings: Settings, root: Path, day: date) -> list[Section]:
    return [
        _safely(lambda: _gather_focus(settings, root), "focus", "Current focus"),
        _safely(lambda: _gather_tasks(settings, root), "tasks", "Things tasks"),
        _safely(lambda: _gather_daily_note(settings, day), "daily_note", "Yesterday's daily note"),
        _safely(lambda: _gather_outcomes(settings, root, day), "outcomes", "Recommendations due for review"),
        _safely(lambda: _gather_career(settings), "career", "Career direction map"),
        _safely(lambda: _gather_reading(settings), "reading", "Reading list"),
    ]


def run_morning_briefing(settings: Settings, root: Path, day: date | None = None) -> int:
    """Gather, write, save. Returns a process exit code; the previous briefing stays on failure."""
    day = day or date.today()
    ledger = CostLedger(root / settings.budget.ledger_dir, lambda: "job:morning-briefing")
    limit = settings.budget.monthly_usd
    if settings.budget.enabled and limit and ledger.month_spend() >= limit:
        print(f"Skipped: this month's spend is over the ${limit:.2f} budget, and a job can't ask.")
        return 1

    sections = gather_sections(settings, root, day)
    model = resolve_model(settings.briefing.model, settings.models).model_id
    client = LLMClient(api_keys=collect_api_keys(), default_model=model)
    response = client.complete(build_messages(day, sections), max_tokens=settings.models.default_max_tokens)
    if settings.budget.enabled:
        ledger.record_response(response, purpose="job", model=model)

    text = response.choices[0].message.content
    if not text:
        print(f"Failed: the model returned no text (finish_reason: {response.choices[0].finish_reason}).")
        return 1
    billed = reported_cost(response.usage)
    cost = billed if billed is not None else calculate_cost_from_litellm(response)
    path = save_briefing(root / settings.briefing.dir, day, text, sections, model=model, cost_usd=cost)
    print(f"Briefing saved to {path} (${cost:.4f}).")
    for section in sections:
        if section.problem:
            print(f"  Not available: {section.key}: {section.problem}")
    return 0


JOBS = {"morning-briefing": run_morning_briefing}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvis run-job", description="Run an unattended JARVIS job.")
    parser.add_argument("job", choices=sorted(JOBS))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    load_dotenv(PROJECT_ROOT / ".env")
    return JOBS[args.job](load_config(PROJECT_ROOT), PROJECT_ROOT)
