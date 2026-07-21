"""
Advance booking window monitor for ReserveCA locations.

California State Parks opens reservations exactly 6 calendar months to the day
before check-in at 8:00 AM Pacific. This module fires once per week — on the
morning a new summer Friday-Sunday becomes bookable — and alerts for any
full-weekend (Fri–Sun, 2-night) availability at all enabled ReserveCA locations.

Scheduling: CronTrigger at 08:00 America/Los_Angeles, daily.
Fires meaningful work only on days where today + 6 months is a summer Friday.
"""
import asyncio
import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytz

logger = logging.getLogger(__name__)

PACIFIC = pytz.timezone("America/Los_Angeles")

# Summer season: May 15 – September 30 (the dates users want to book)
SUMMER_START_MONTH, SUMMER_START_DAY = 5, 15
SUMMER_END_MONTH, SUMMER_END_DAY = 9, 30


def add_calendar_months(d: date, months: int) -> date:
    """Add calendar months to a date, clamping to the last day of the target month."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def is_summer_weekend(d: date) -> bool:
    """True if date falls within May 15 – September 30 of the same year."""
    start = date(d.year, SUMMER_START_MONTH, SUMMER_START_DAY)
    end = date(d.year, SUMMER_END_MONTH, SUMMER_END_DAY)
    return start <= d <= end


def get_advance_target_friday() -> Optional[date]:
    """
    Returns the Friday that opens its booking window today (today + 6 calendar
    months), if that Friday falls in the summer window. Otherwise returns None.

    Called daily at 8 AM Pacific — returns a non-None value about once per week.
    """
    today = datetime.now(tz=PACIFIC).date()
    target = add_calendar_months(today, 6)
    if target.weekday() == 4 and is_summer_weekend(target):
        return target
    return None


async def run_advance_booking_check():
    """
    Daily 8 AM Pacific job. Checks all enabled ReserveCA locations for
    Fri–Sun 2-night availability on the weekend whose booking window opens today.
    Sends one batch alert per location; deduplicates via AvailabilityLog.
    """
    target_friday = get_advance_target_friday()
    if target_friday is None:
        return

    target_saturday = target_friday + timedelta(days=1)
    logger.info(
        "Advance booking window opening for %s–%s — scanning ReserveCA locations",
        target_friday, target_saturday,
    )

    from app.database import SessionLocal
    from app.models import Location

    db = SessionLocal()
    try:
        locations = db.query(Location).filter(
            Location.enabled.is_(True),
            Location.scraper_type.in_(["reserveca", "crystal_cove"]),
        ).all()
        location_ids = [loc.id for loc in locations]
    finally:
        db.close()

    if not location_ids:
        logger.info("No enabled ReserveCA locations for advance booking check.")
        return

    await asyncio.gather(*[
        _check_location_advance(loc_id, target_friday)
        for loc_id in location_ids
    ])


async def _check_location_advance(location_id: int, target_friday: date):
    """Check one ReserveCA location for full-weekend (Fri–Sun) availability."""
    from app.database import SessionLocal
    from app.models import Location, AvailabilityLog, CheckLog
    from app.scrapers.reservecalifornia import ReserveCaliforniaScraper
    from app.scrapers.crystal_cove import CrystalCoveScraper
    from app.notifications.pushover import send_advance_alert

    db = SessionLocal()
    try:
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location or not location.enabled:
            return

        scraper_cls = (
            CrystalCoveScraper if location.scraper_type == "crystal_cove"
            else ReserveCaliforniaScraper
        )

        try:
            scraper = scraper_cls(location)
            # check_availability fires both 1-night and 2-night for Fridays;
            # we only want the 2-night (Fri–Sun) results for advance booking.
            all_results = await scraper.check_availability([target_friday])
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
                "Advance booking: %s — %d new Fri–Sun site(s) for %s",
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
