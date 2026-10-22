"""
Single source of truth for the Camp Finder monitoring season.

Brian's monitoring spec (2026-10-20):
  * The cancellation watch and advance booking target ARRIVALS in season
    only — no perpetual year-round polling.
  * Season: May 15 – September 15.
  * Outside the season the service idles: no availability polling at all
    (health endpoint stays up, jobs wake periodically to re-check the gate).

Both the last-minute cancellation loop (runner.py) and the advance booking
monitor (advance.py) import from here so the season can never drift apart
again (advance.py previously ran its own season ending Sep 30).
"""
from datetime import date

SEASON_START_MONTH, SEASON_START_DAY = 5, 15
SEASON_END_MONTH, SEASON_END_DAY = 9, 15


def season_bounds(year: int) -> tuple[date, date]:
    """(start, end) arrival-season dates for the given year, inclusive."""
    return (
        date(year, SEASON_START_MONTH, SEASON_START_DAY),
        date(year, SEASON_END_MONTH, SEASON_END_DAY),
    )


def is_in_season(d: date) -> bool:
    """True if the arrival date falls inside May 15 – Sep 15 of its year."""
    start, end = season_bounds(d.year)
    return start <= d <= end
