"""
Intelligent cancellation window logic per scraper type.

CA State Parks 48-hour policy:
- Cancel 2+ days before check-in → refund minus $7.99 fee
- Cancel within 48 hours → forfeit first night + $7.99 fee
Peak days: Wed/Thu all day (48-hr deadline for Fri/Sat), Fri AM, evenings daily.

Crystal Pier Hotel 7-day cancellation policy:
- Cancel 7+ days before check-in → full refund
- Cancel within 7 days → $50 fee; within 48 hours → forfeit first night
Peak days: Fri/Sat/Sun all day (7-day deadline for Fri/Sat/Sun arrivals), evenings daily.
"""
from datetime import datetime
import pytz

from app.config import settings

PACIFIC = pytz.timezone("America/Los_Angeles")


def _now_pacific() -> datetime:
    return datetime.now(tz=PACIFIC)


def _is_ca_parks_peak() -> bool:
    """Peak window for CA State Parks (48-hour cancellation policy)."""
    now = _now_pacific()
    hour = now.hour
    weekday = now.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

    # Evening window every day 6–11 PM
    if 18 <= hour < 23:
        return True

    # Wednesday all day: 48-hr deadline for Friday check-ins
    if weekday == 2:
        return True

    # Thursday all day: 48-hr deadline for Saturday check-ins
    if weekday == 3:
        return True

    # Friday morning: last-minute cancellations for Sat/Sun
    if weekday == 4 and hour < 12:
        return True

    return False


def _is_crystal_pier_peak() -> bool:
    """Peak window for Crystal Pier Hotel (7-day cancellation policy).

    7-day deadlines fall on: Fri arrivals → deadline is Fri of prior week,
    Sat → Sat prior week, Sun → Sun prior week.
    So Fri/Sat/Sun all day are peak (people cancelling for next Fri/Sat/Sun).
    """
    now = _now_pacific()
    hour = now.hour
    weekday = now.weekday()  # 4=Fri, 5=Sat, 6=Sun

    # Evening window every day 6–11 PM
    if 18 <= hour < 23:
        return True

    # Fri/Sat/Sun all day: 7-day deadline days
    if weekday in (4, 5, 6):
        return True

    return False


def get_interval_for_scraper_type(scraper_type: str) -> int:
    """Return the check interval in minutes for the given scraper type."""
    if scraper_type == "crystal_pier":
        return settings.peak_window_interval if _is_crystal_pier_peak() else settings.default_check_interval
    # reserveca, crystal_cove, and any unknown types use CA parks logic
    return settings.peak_window_interval if _is_ca_parks_peak() else settings.default_check_interval


def get_current_interval() -> int:
    """Return the minimum active interval across all scraper types (used by health endpoint)."""
    ca_interval = settings.peak_window_interval if _is_ca_parks_peak() else settings.default_check_interval
    pier_interval = settings.peak_window_interval if _is_crystal_pier_peak() else settings.default_check_interval
    return min(ca_interval, pier_interval)
