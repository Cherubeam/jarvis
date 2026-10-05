"""Propose memory changes from a Claude memory export; apply only what you approve.

Archives the raw export in ``paths.imports_dir`` (without login history and account data), asks
a model for proposals per memory note, then shows each one: [y]es applies it, [e]dit opens the
proposed text for editing, [n]o rejects it, [q]uit stops. Conflicts (facts older than the note) are only shown.
Every decision is logged next to the archived export.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from prompt_toolkit import PromptSession

from packages.core.frontmatter import write_atomic
from packages.core.importers.claude_memory import (
    PROPOSABLE_SECTIONS,
    Proposal,
    apply_proposal,
    archive_export,
    draft_proposals,
    export_date,
    find_memory_file,
    load_export_facts,
    log_decision,
)
from packages.core.llm_client import LLMClient
from packages.core.model_resolver import collect_api_keys
from packages.core.settings import load_config

# Reasoning models spend part of max_tokens on thinking (see #67); leave room for the JSON.
_MAX_TOKENS = 16000


def _show(proposal: Proposal, note_name: str) -> None:
    print(f"\n── {note_name} › ## {proposal.heading}  ({proposal.action}, facts from {proposal.fact_date})")
    if proposal.old:
        print(f"  - {proposal.old}")
        print(f"  + {proposal.new}")
    else:
        print(f"  + {proposal.new}")
    if proposal.reason:
        print(f"  why: {proposal.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Propose memory changes from a Claude memory export.")
    parser.add_argument("export_dir", type=Path, help="Unzipped Claude export folder (contains memories/).")
    parser.add_argument("--model", default=None, help="Model for drafting proposals (default: the quality preset).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Draft and show proposals; archive, apply and log nothing.",
    )
    args = parser.parse_args(argv)

    load_dotenv(PROJECT_ROOT / ".env")
    settings = load_config(PROJECT_ROOT)
    model = args.model or settings.models.presets.quality
    context_dir = PROJECT_ROOT / settings.paths.context_dir
    context_files = settings.paths.context_files.model_dump()

    try:
        memory_file = find_memory_file(args.export_dir)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    exported = export_date(args.export_dir)
    import_dir = PROJECT_ROOT / settings.paths.imports_dir / "claude" / exported
    log_file = import_dir / "memory-decisions.jsonl"

    mode = "DRY RUN" if args.dry_run else "REVIEW"
    print(f"[{mode}] Claude memory export {exported} → memory proposals ({model})")
    if not args.dry_run:
        archived = archive_export(args.export_dir, import_dir / "export")
        print(f"  Raw export {'archived to' if archived else 'already archived in'} {import_dir / 'export'}")

    facts = load_export_facts(memory_file)
    print(f"  Project memories left for the project mapping: {facts.skipped_projects} files")
    if facts.unrouted:
        print(f"  Not routed to any note (add a route if they matter): {', '.join(facts.unrouted)}")

    client = LLMClient(api_keys=collect_api_keys(), default_model=model)

    def complete(prompt: str) -> str:
        response = client.complete([{"role": "user", "content": prompt}], max_tokens=_MAX_TOKENS)
        return str(response.choices[0].message.content or "")

    today = date.today().isoformat()
    prompts: PromptSession[str] = PromptSession()
    counts = {"applied": 0, "edited": 0, "rejected": 0, "conflict": 0, "stale": 0}

    for section in PROPOSABLE_SECTIONS:
        section_facts = facts.by_section.get(section, [])
        if not section_facts:
            continue
        note_name = context_files[section]
        note_path = context_dir / note_name
        if not note_path.exists():
            print(f"\n  {note_name}: missing, skipped")
            continue
        print(f"\n== {note_name}: {len(section_facts)} export facts, asking the model …")
        proposals = draft_proposals(section, note_path.read_text(encoding="utf-8"), section_facts, complete)
        appliable = [p for p in proposals if p.appliable]
        conflicts = [p for p in proposals if not p.appliable]
        print(f"   {len(appliable)} proposal(s), {len(conflicts)} conflict(s)")

        for proposal in conflicts:
            _show(proposal, note_name)
            print("  conflict: the note is newer than these facts; not applied (ADR-041)")
            counts["conflict"] += 1
            if not args.dry_run:
                log_decision(log_file, proposal, "conflict", model=model, applied_text=None)

        for proposal in appliable:
            _show(proposal, note_name)
            if args.dry_run:
                continue
            answer = ""
            while answer not in ("y", "n", "e", "q"):
                answer = prompts.prompt("  apply? [y]es / [e]dit / [n]o / [q]uit: ").strip().lower()
            if answer == "q":
                print("\nStopped. Decisions so far are applied and logged.")
                print(f"  {counts}")
                return 0
            if answer == "n":
                counts["rejected"] += 1
                log_decision(log_file, proposal, "rejected", model=model, applied_text=None)
                continue
            to_apply = proposal
            if answer == "e":
                # Pre-filled and pasteable; a bullet is one line, so pasted line breaks are collapsed.
                edited = " ".join(prompts.prompt("  edit: ", default=proposal.new).split())
                if not edited:
                    counts["rejected"] += 1
                    log_decision(log_file, proposal, "rejected", model=model, applied_text=None)
                    continue
                to_apply = dataclasses.replace(proposal, new=edited)
            current = note_path.read_text(encoding="utf-8")
            updated = apply_proposal(current, to_apply, today=today)
            if updated is None:
                print("  the note changed and this line no longer fits; skipped")
                counts["stale"] += 1
                log_decision(log_file, proposal, "stale", model=model, applied_text=None)
                continue
            write_atomic(note_path, updated)
            decision = "edited" if to_apply is not proposal else "applied"
            counts[decision] += 1
            log_decision(log_file, proposal, decision, model=model, applied_text=to_apply.new)

    print(f"\nDone. {counts}")
    if not args.dry_run:
        print(f"  Decision log: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
