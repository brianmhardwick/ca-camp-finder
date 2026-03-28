"""
Intelligent cancellation window logic based on CA State Parks 48-hour policy.

Reserve California cancellation rules:
- Cancel 2+ days before check-in → refund minus $7.99 service fee
- Cancel within 48 hours → forfeit first night + $7.99 fee

Peak windows (check every 15 min instead of 60):
- Tuesday 6–11 PM: People deliberating about upcoming Fri–Sun weekend
- Wednesday all day: Deadline day for Friday check-ins (heaviest volume)
- Thursday all day: Deadline day for Saturday check-ins
- Friday 6 AM–noon: Last-minute cancellations for Sat/Sun (penalty accepted)
- Every day 6–11 PM: General evening decision-making window
"""
from datetime import datetime, date, timedelta
import pytz

from app.config import settings

PACIFIC = pytz.timezone("America/Los_Angeles")


def _now_pacific() -> datetime:
    return datetime.now(tz=PACIFIC)


def is_peak_window() -> bool:
    """Return True if now is within a high-probability cancellation window."""
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


def get_current_interval() -> int:
    """Return the check interval in minutes based on current window."""
    if is_peak_window():
        return settings.peak_window_interval
    return settings.default_check_interval
