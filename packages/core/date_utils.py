"""Date parsing utilities for relative date strings."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_UNIT_PATTERN = re.compile(r"(\d+)\s*(day|days|week|weeks|month|months|year|years)")

SUPPORTED_FORMS = (
    "'N day(s)', 'N week(s)', 'N month(s)', 'N year(s)', "
    "'tomorrow', 'next week', 'next month', or ISO date 'YYYY-MM-DD'"
)


def parse_relative_date(value: str, now: datetime | None = None) -> date:
    """Parse a relative date string into an absolute date.

    Month/year arithmetic uses 30/365-day approximations, which is acceptable
    for revisit horizons (we don't need calendar-exact semantics).
    """
    if now is None:
        now = datetime.now()
    today = now.date()

    stripped = value.strip()

    try:
        return date.fromisoformat(stripped)
    except ValueError:
        pass

    s = stripped.lower()

    if s == "tomorrow":
        return today + timedelta(days=1)
    if s == "next week":
        return today + timedelta(days=7)
    if s == "next month":
        return today + timedelta(days=30)

    m = _UNIT_PATTERN.fullmatch(s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("day"):
            return today + timedelta(days=n)
        if unit.startswith("week"):
            return today + timedelta(weeks=n)
        if unit.startswith("month"):
            return today + timedelta(days=30 * n)
        if unit.startswith("year"):
            return today + timedelta(days=365 * n)

    raise ValueError(f"Cannot parse '{value}' as a relative date. Supported forms: {SUPPORTED_FORMS}.")
