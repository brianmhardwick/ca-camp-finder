"""
Intelligent cancellation window logic.

Cancellation patterns observed for campgrounds / boutique hotels:
- 48–72 hrs before check-in: people finalize plans and cancel
- 6 PM – 11 PM any day: evening decision-making window
- Thursday before a weekend: highest-volume last-minute window

During these windows the scheduler reduces its interval to PEAK_WINDOW_INTERVAL.
"""
from datetime import datetime, date, timedelta
import pytz

from app.config import settings

PACIFIC = pytz.timezone("America/Los_Angeles")


def _now_pacific() -> datetime:
    return datetime.now(tz=PACIFIC)


def _upcoming_fridays(weeks: int = 12) -> list[date]:
    """Return the next `weeks` Fridays from today."""
    today = _now_pacific().date()
    fridays = []
    for i in range(weeks * 7):
        d = today + timedelta(days=i)
        if d.weekday() == 4:  # Friday
            fridays.append(d)
            if len(fridays) >= weeks:
                break
    return fridays


def is_peak_window() -> bool:
    """Return True if now is within a high-probability cancellation window."""
    now = _now_pacific()
    today = now.date()
    hour = now.hour

    # Evening window: 6 PM – 11 PM local time every day
    if 18 <= hour < 23:
        return True

    # 48–72 hour window before each upcoming Friday
    for friday in _upcoming_fridays(weeks=8):
        delta = (friday - today).days
        if 2 <= delta <= 3:  # 2–3 days out = 48–72 hours
            return True
        # Thursday morning + afternoon is also peak
        if delta == 1 and hour < 20:
            return True

    return False


def get_current_interval() -> int:
    """Return the check interval in minutes based on current window."""
    if is_peak_window():
        return settings.peak_window_interval
    return settings.default_check_interval
