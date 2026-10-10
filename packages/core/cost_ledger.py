"""Append-only spend ledger: one JSON line per turn or side call (AON-01).

One file per month (``YYYY-MM.jsonl``) in ``budget.ledger_dir``. The monthly budget check
sums the current file. Streamed turns are logged with LiteLLM's estimate, which runs about
36% below what OpenRouter bills; the ledger keeps the estimate as logged and weights it by
``ESTIMATE_MARGIN`` when summing, so a limit trips early rather than late.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Streamed costs are estimates until OpenRouter's billing record arrives (~36% low, see #73)
ESTIMATE_MARGIN = 1.5


@dataclass
class LedgerEntry:
    """One turn (all its model calls) or one side call such as an evaluation."""

    timestamp: str
    session_id: str
    purpose: str  # "turn" | "evaluate" | "summarize"
    model: str
    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int
    cost_usd: float
    usage_source: str  # "billed" | "estimated"


def weighted_cost(cost_usd: float, usage_source: str) -> float:
    """Cost as the budget counts it: estimates get the safety margin."""
    return cost_usd * ESTIMATE_MARGIN if usage_source == "estimated" else cost_usd


class CostLedger:
    """Writes and sums the monthly ledger files."""

    def __init__(self, directory: Path, session_id: Callable[[], str] = lambda: "") -> None:
        self.directory = directory
        # A callable: the GUI switches conversations within one process
        self._session_id = session_id

    def _file(self, month: str) -> Path:
        return self.directory / f"{month}.jsonl"

    def record(
        self,
        *,
        purpose: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cache_read_tokens: int,
        cost_usd: float,
        billed: bool,
    ) -> None:
        """Append one line. A failed write is logged, never raised: spend tracking must not end a turn."""
        now = datetime.now()
        entry = LedgerEntry(
            timestamp=now.isoformat(timespec="seconds"),
            session_id=self._session_id(),
            purpose=purpose,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cost_usd=cost_usd,
            usage_source="billed" if billed else "estimated",
        )
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with self._file(now.strftime("%Y-%m")).open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("Cost ledger not written to %s", self.directory, exc_info=True)

    def record_response(self, response: Any, *, purpose: str, model: str) -> None:
        """Record a non-streamed side call (evaluation, summary) from its LiteLLM response."""
        from packages.core.llm_client import _extract_cache_tokens, reported_cost
        from packages.core.pricing import calculate_cost_from_litellm

        usage = getattr(response, "usage", None)
        billed = reported_cost(usage)
        cache_read, _ = _extract_cache_tokens(usage)
        self.record(
            purpose=purpose,
            model=getattr(response, "model", None) or model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cache_read_tokens=cache_read,
            cost_usd=billed if billed is not None else calculate_cost_from_litellm(response),
            billed=billed is not None,
        )

    def month_spend(self, month: str | None = None) -> float:
        """Spend in the month (default: this month), estimates weighted by ESTIMATE_MARGIN."""
        path = self._file(month or datetime.now().strftime("%Y-%m"))
        if not path.is_file():
            return 0.0
        total = 0.0
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                total += weighted_cost(float(row["cost_usd"]), str(row["usage_source"]))
            except (ValueError, KeyError, TypeError):
                continue  # a torn or hand-edited line costs nothing rather than breaking the check
        return total
