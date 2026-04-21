"""Tests for packages.core.date_utils."""

from datetime import date, datetime

import pytest

from packages.core.date_utils import parse_relative_date

NOW = datetime(2026, 4, 18, 14, 30, 0)


def test_parses_iso_date():
    assert parse_relative_date("2027-01-15", now=NOW) == date(2027, 1, 15)


def test_parses_iso_date_with_whitespace():
    assert parse_relative_date("  2027-01-15  ", now=NOW) == date(2027, 1, 15)


def test_tomorrow():
    assert parse_relative_date("tomorrow", now=NOW) == date(2026, 4, 19)


def test_tomorrow_case_insensitive():
    assert parse_relative_date("Tomorrow", now=NOW) == date(2026, 4, 19)


def test_next_week():
    assert parse_relative_date("next week", now=NOW) == date(2026, 4, 25)


def test_next_month():
    assert parse_relative_date("next month", now=NOW) == date(2026, 5, 18)


def test_singular_day():
    assert parse_relative_date("1 day", now=NOW) == date(2026, 4, 19)


def test_plural_days():
    assert parse_relative_date("5 days", now=NOW) == date(2026, 4, 23)


def test_singular_week():
    assert parse_relative_date("1 week", now=NOW) == date(2026, 4, 25)


def test_plural_weeks():
    assert parse_relative_date("2 weeks", now=NOW) == date(2026, 5, 2)


def test_singular_month():
    assert parse_relative_date("1 month", now=NOW) == date(2026, 5, 18)


def test_plural_months():
    assert parse_relative_date("3 months", now=NOW) == date(2026, 7, 17)


def test_singular_year():
    assert parse_relative_date("1 year", now=NOW) == date(2027, 4, 18)


def test_plural_years():
    assert parse_relative_date("2 years", now=NOW) == date(2028, 4, 17)


def test_unit_without_space():
    assert parse_relative_date("3days", now=NOW) == date(2026, 4, 21)


def test_invalid_raises_value_error():
    with pytest.raises(ValueError) as exc_info:
        parse_relative_date("eventually", now=NOW)
    assert "Cannot parse 'eventually'" in str(exc_info.value)


def test_invalid_error_lists_supported_forms():
    with pytest.raises(ValueError) as exc_info:
        parse_relative_date("whenever", now=NOW)
    msg = str(exc_info.value)
    assert "N day(s)" in msg
    assert "tomorrow" in msg
    assert "YYYY-MM-DD" in msg


def test_invalid_iso_falls_through_to_error():
    with pytest.raises(ValueError):
        parse_relative_date("2026-13-40", now=NOW)


def test_empty_string_raises():
    with pytest.raises(ValueError):
        parse_relative_date("", now=NOW)


def test_default_now_uses_current_time():
    result = parse_relative_date("1 day")
    assert result == (datetime.now().date() + (date(2026, 4, 19) - date(2026, 4, 18)))


def test_zero_days_returns_today():
    assert parse_relative_date("0 days", now=NOW) == date(2026, 4, 18)
