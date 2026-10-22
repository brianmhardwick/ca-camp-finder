"""
Advance booking window monitor.

Booking windows (Brian's monitoring spec, 2026-10-20):
  * ReserveCA / Crystal Cove: reservations open exactly 6 calendar months to
    the day before check-in at 8:00 AM Pacific.
  * Crystal Pier: reservations open 12 calendar months out.

Only in-season arrival dates are targeted — Fridays inside the monitoring
season (May 15 – Sep 15, see app/scheduler/season.py).

Scheduling:
  * Main job: CronTrigger at 08:00 America/Los_Angeles, daily. Checks every
    window that opens today, plus a catch-up re-check of yesterday's openings
    (in case the app was down or the 08:00 run errored).
  * Re-poll burst: an interval job every REPOLL_INTERVAL_MINUTES re-runs
    today's checks between 08:00 and REPOLL_END_HOUR Pacific on open days,
    so a single raced/errored 08:00 shot can no longer lose a whole weekend.
    AvailabilityLog de-duping guarantees no duplicate Pushover alerts.
"""
import asyncio
import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytz

from app.scheduler.season import (
    SEASON_END_DAY,
    SEASON_END_MONTH,
    SEASON_START_DAY,
    SEASON_START_MONTH,
    is_in_season,
)

logger = logging.getLogger(__name__)

PACIFIC = pytz.timezone("America/Los_Angeles")

# Kept as aliases of the shared season constants (single source of truth).
SUMMER_START_MONTH, SUMMER_START_DAY = SEASON_START_MONTH, SEASON_START_DAY
SUMMER_END_MONTH, SUMMER_END_DAY = SEASON_END_MONTH, SEASON_END_DAY

# Booking-window lengths, in calendar months.
RESERVECA_ADVANCE_MONTHS = 6
CRYSTAL_PIER_ADVANCE_MONTHS = 12

# Re-poll burst on window-open mornings: repeat today's checks every
# REPOLL_INTERVAL_MINUTES until REPOLL_END_HOUR Pacific.
REPOLL_INTERVAL_MINUTES = 15
REPOLL_END_HOUR = 11


def add_calendar_months(d: date, months: int) -> date:
    """Add calendar months to a date, clamping to the last day of the target month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def is_summer_weekend(d: date) -> bool:
    """True if the arrival date is inside the monitoring season (May 15 – Sep 15)."""
    return is_in_season(d)


def get_advance_friday(today: date, months: int) -> Optional[date]:
    """
    The Friday whose booking window opens `today` for a `months`-ahead
    booking window, if that Friday is an in-season arrival. Otherwise None.
    """
    target = add_calendar_months(today, months)
    if target.weekday() == 4 and is_summer_weekend(target):
        return target
    return None


def get_advance_targets(today: date) -> list[tuple[str, date]]:
    """
    All (window, friday) pairs whose booking windows open today.

    window is "reserveca" (6-month window) or "crystal_pier" (12-month).
    """
    targets: list[tuple[str, date]] = []
    friday = get_advance_friday(today, RESERVECA_ADVANCE_MONTHS)
    if friday:
        targets.append(("reserveca", friday))
    friday = get_advance_friday(today, CRYSTAL_PIER_ADVANCE_MONTHS)
    if friday:
        targets.append(("crystal_pier", friday))
    return targets


def get_advance_target_friday() -> Optional[date]:
    """
    Returns the Friday that opens its ReserveCA booking window today
    (today + 6 calendar months), if that Friday falls in the season window.
    Otherwise returns None.

    Called daily at 8 AM Pacific — returns a non-None value about once per week.
    """
    today = datetime.now(tz=PACIFIC).date()
    return get_advance_friday(today, RESERVECA_ADVANCE_MONTHS)


def repoll_is_active(now: datetime) -> bool:
    """True during the re-poll burst window (08:00–11:00 Pacific) on a day
    where at least one booking window opens."""
    return 8 <= now.hour < REPOLL_END_HOUR and bool(get_advance_targets(now.date()))


async def _check_window(window: str, target_friday: date):
    """Run the advance check for one booking window on one target Friday."""
    from app.database import SessionLocal
    from app.models import Location

    scraper_types = (
        ["reserveca", "crystal_cove"] if window == "reserveca" else ["crystal_pier"]
    )

    db = SessionLocal()
    try:
        locations = db.query(Location).filter(
            Location.enabled.is_(True),
            Location.scraper_type.in_(scraper_types),
        ).all()
        location_ids = [loc.id for loc in locations]
    finally:
        db.close()

    if not location_ids:
        logger.info("No enabled %s locations for advance booking check.", window)
        return

    logger.info(
        "Advance booking (%s): window open for Fri %s — scanning %d location(s)",
        window, target_friday, len(location_ids),
    )
    await asyncio.gather(*[
        _check_location_advance(loc_id, target_friday)
        for loc_id in location_ids
    ])


async def run_advance_booking_check():
    """
    Daily 8 AM Pacific job. Checks every booking window that opens today
    (ReserveCA 6-month, Crystal Pier 12-month) for in-season Fridays, plus a
    catch-up re-check of yesterday's openings in case yesterday's run was
    missed or errored. De-duping via AvailabilityLog prevents double alerts.
    """
    today = datetime.now(tz=PACIFIC).date()
    targets = list(get_advance_targets(today))

    yesterday_targets = get_advance_targets(today - timedelta(days=1))
    if yesterday_targets:
        logger.info(
            "Advance booking catch-up: re-checking yesterday's opening(s) %s",
            yesterday_targets,
        )
        targets.extend(yesterday_targets)

    for window, target_friday in targets:
        await _check_window(window, target_friday)


async def run_advance_repoll_check():
    """
    Re-poll burst job (every REPOLL_INTERVAL_MINUTES). No-ops except between
    08:00 and REPOLL_END_HOUR Pacific on days a booking window opens, when it
    repeats today's advance checks so a failed or raced 08:00 run is retried.
    """
    now = datetime.now(tz=PACIFIC)
    if not repoll_is_active(now):
        return
    logger.info("Advance booking re-poll burst for %s", now.date())
    for window, target_friday in get_advance_targets(now.date()):
        await _check_window(window, target_friday)


async def _check_location_advance(location_id: int, target_friday: date):
    """Check one location for availability on the advance target Friday."""
    from app.database import SessionLocal
    from app.models import Location, AvailabilityLog, CheckLog
    from app.scrapers.reservecalifornia import ReserveCaliforniaScraper
    from app.scrapers.crystal_cove import CrystalCoveScraper
    from app.scrapers.crystal_pier import CrystalPierScraper
    from app.notifications.pushover import send_advance_alert

    db = SessionLocal()
    try:
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location or not location.enabled:
            return

        if location.scraper_type == "crystal_cove":
            scraper_cls = CrystalCoveScraper
        elif location.scraper_type == "crystal_pier":
            scraper_cls = CrystalPierScraper
        else:
            scraper_cls = ReserveCaliforniaScraper

        try:
            scraper = scraper_cls(location)
            all_results = await scraper.check_availability([target_friday])
            if location.scraper_type == "crystal_pier":
                # Hotel results are per-night stays (num_nights=1); a hit on
                # the target Friday means a room is open for that arrival.
                results = list(all_results)
            else:
                # ReserveCA check_availability fires both 1-night and 2-night
                # for Fridays; advance booking only wants the 2-night
                # (Fri–Sun) results.
                results = [r for r in all_results if r.num_nights == 2]

            db.add(CheckLog(
                location_id=location.id,
                status="ok",
                units_found=len(results),
            ))

            new_results = []
            new_log_entries = []
            for result in results:
                existing = (
                    db.query(AvailabilityLog)
                    .filter(
                        AvailabilityLog.location_id == result.location_id,
                        AvailabilityLog.check_in_date == result.check_in_date,
                        AvailabilityLog.unit_id == result.unit_id,
                        AvailabilityLog.num_nights == result.num_nights,
                        AvailabilityLog.still_available.is_(True),
                    )
                    .first()
                )
                if existing:
                    continue

                log_entry = AvailabilityLog(
                    location_id=result.location_id,
                    check_in_date=result.check_in_date,
                    unit_description=result.unit_description,
                    unit_id=result.unit_id,
                    unit_type=result.unit_type,
                    price_per_night=result.price_per_night,
                    booking_url=result.booking_url,
                    num_nights=result.num_nights,
                    still_available=True,
                )
                db.add(log_entry)
                db.flush()
                new_results.append(result)
                new_log_entries.append(log_entry)

            if new_results:
                notified = await send_advance_alert(
                    location_name=location.name,
                    new_results=new_results,
                    target_friday=target_friday,
                    booking_url=new_results[0].booking_url,
                )
                if notified:
                    now = datetime.now(timezone.utc)
                    for log_entry in new_log_entries:
                        log_entry.notified_at = now

            db.commit()
            logger.info(
                "Advance booking: %s — %d new site(s) for %s",
                location.name, len(new_results), target_friday,
            )

        except Exception as e:
            db.rollback()
            db.add(CheckLog(
                location_id=location.id,
                status="error",
                units_found=0,
                error_message=str(e)[:500],
            ))
            db.commit()
            logger.error("Advance booking check failed for %s: %s", location.name, e)

    finally:
        db.close()
