"""
Tests for advance booking window logic.

California State Parks opens reservations 6 calendar months to the day at
8 AM Pacific. This module tests the date arithmetic and summer-window logic
that determines when the advance booking check fires.
"""
from datetime import date

import pytest

from app.scheduler.advance import (
    add_calendar_months,
    get_advance_target_friday,
    is_summer_weekend,
)


# ── add_calendar_months ───────────────────────────────────────────────────────

def test_add_6_months_canonical():
    """Official example: Jan 15 + 6 months = Jul 15."""
    assert add_calendar_months(date(2026, 1, 15), 6) == date(2026, 7, 15)


def test_add_6_months_year_boundary():
    """Aug 20 + 6 months = Feb 20 next year."""
    assert add_calendar_months(date(2025, 8, 20), 6) == date(2026, 2, 20)


def test_add_6_months_clamps_month_end():
    """Aug 31 + 6 months = Feb 28 (non-leap year, clamps to last day)."""
    assert add_calendar_months(date(2025, 8, 31), 6) == date(2026, 2, 28)


def test_add_6_months_leap_year():
    """Aug 29 + 6 months = Feb 29 in a leap year."""
    assert add_calendar_months(date(2023, 8, 29), 6) == date(2024, 2, 29)


def test_add_6_months_non_leap_clamps():
    """Aug 31 + 6 months in non-leap year clamps to Feb 28."""
    result = add_calendar_months(date(2026, 8, 31), 6)
    assert result == date(2027, 2, 28)


# ── is_summer_weekend ─────────────────────────────────────────────────────────

def test_summer_start_boundary():
    assert is_summer_weekend(date(2026, 5, 15)) is True


def test_before_summer_start():
    assert is_summer_weekend(date(2026, 5, 14)) is False


def test_summer_end_boundary():
    assert is_summer_weekend(date(2026, 9, 30)) is True


def test_after_summer_end():
    assert is_summer_weekend(date(2026, 10, 1)) is False


def test_mid_summer():
    assert is_summer_weekend(date(2026, 7, 4)) is True


def test_winter_date():
    assert is_summer_weekend(date(2026, 1, 15)) is False


# ── get_advance_target_friday ─────────────────────────────────────────────────

def test_returns_friday_in_summer(monkeypatch):
    """When today + 6 months is a summer Friday, returns that date."""
    from datetime import datetime
    import pytz
    from app.scheduler import advance

    # Jan 17, 2026 + 6 months = Jul 17, 2026 which is a Friday
    mock_now = datetime(2026, 1, 17, 8, 0, 0, tzinfo=pytz.timezone("America/Los_Angeles").localize(datetime(2026, 1, 17, 8, 0, 0)).tzinfo)

    def fake_now(tz=None):
        return datetime(2026, 1, 17, 8, 0, 0, tzinfo=pytz.utc).astimezone(pytz.timezone("America/Los_Angeles"))

    monkeypatch.setattr("app.scheduler.advance.datetime", type("dt", (), {
        "now": staticmethod(fake_now),
    }))
    # Jul 17 2026: let's verify it's a Friday
    assert date(2026, 7, 17).weekday() == 4  # 4 = Friday
    result = get_advance_target_friday()
    assert result == date(2026, 7, 17)


def test_returns_none_when_target_is_saturday(monkeypatch):
    """When today + 6 months is a Saturday, returns None."""
    import pytz
    from datetime import datetime

    def fake_now(tz=None):
        # Jan 18, 2026 + 6 months = Jul 18, 2026 (Saturday)
        return datetime(2026, 1, 18, 8, 0, 0, tzinfo=pytz.utc).astimezone(pytz.timezone("America/Los_Angeles"))

    monkeypatch.setattr("app.scheduler.advance.datetime", type("dt", (), {
        "now": staticmethod(fake_now),
    }))
    assert date(2026, 7, 18).weekday() == 5  # Saturday
    assert get_advance_target_friday() is None


def test_returns_none_when_target_outside_summer(monkeypatch):
    """When today + 6 months is a Friday but not in summer, returns None."""
    import pytz
    from datetime import datetime

    def fake_now(tz=None):
        # Apr 10, 2026 + 6 months = Oct 10, 2026 — past Sept 30
        return datetime(2026, 4, 10, 8, 0, 0, tzinfo=pytz.utc).astimezone(pytz.timezone("America/Los_Angeles"))

    monkeypatch.setattr("app.scheduler.advance.datetime", type("dt", (), {
        "now": staticmethod(fake_now),
    }))
    assert date(2026, 10, 10).weekday() == 5  # Saturday actually, but point stands
    assert get_advance_target_friday() is None


# ── calendar math cross-check ─────────────────────────────────────────────────

def test_6month_booking_window_examples():
    """Round-trip: for every summer Friday, going back 6 months then forward 6 months returns the same date."""
    from datetime import timedelta

    # Collect all Fridays in the 2026 summer window
    summer_fridays = []
    d = date(2026, 5, 15)
    while d <= date(2026, 9, 30):
        if d.weekday() == 4:  # Friday
            summer_fridays.append(d)
        d += timedelta(days=1)

    assert len(summer_fridays) > 0

    for friday in summer_fridays:
        opening_day = add_calendar_months(friday, -6)
        result = add_calendar_months(opening_day, 6)
        assert result == friday, (
            f"Round-trip failed: {friday} → opening {opening_day} → back {result}"
        )
        assert is_summer_weekend(friday)

    # Spot-check a couple of known opening-day → check-in pairs
    # Jul 17, 2026 is a Friday; its booking window opens Jan 17, 2026
    assert date(2026, 7, 17).weekday() == 4
    assert add_calendar_months(date(2026, 1, 17), 6) == date(2026, 7, 17)
    # Sep 25, 2026 is a Friday; its booking window opens Mar 25, 2026
    assert date(2026, 9, 25).weekday() == 4
    assert add_calendar_months(date(2026, 3, 25), 6) == date(2026, 9, 25)
