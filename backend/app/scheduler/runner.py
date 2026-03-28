"""
APScheduler-based job runner.
Each enabled location gets its own recurring job with an interval determined
by its scraper type (CA parks vs Crystal Pier cancellation policy windows).
"""
import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.scheduler.windows import get_interval_for_scraper_type, get_current_interval

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Per-location tracking (keyed by location_id)
_location_last_check: dict[int, datetime] = {}
_location_next_check: dict[int, datetime] = {}


def get_last_check() -> Optional[datetime]:
    """Most recent check across all locations."""
    if not _location_last_check:
        return None
    return max(_location_last_check.values())


def get_next_check() -> Optional[datetime]:
    """Soonest upcoming check across all locations."""
    if not _location_next_check:
        return None
    return min(_location_next_check.values())


def get_target_dates() -> list[date]:
    """Return all Fri/Sat/Sun dates within the scan window."""
    today = date.today()
    target = []
    for i in range(settings.scan_days_ahead):
        d = today + timedelta(days=i)
        if d.weekday() in (4, 5, 6):  # Fri=4, Sat=5, Sun=6
            target.append(d)
    return target


async def run_check_for_location(location_id: int):
    """Run availability check for a single location, then reschedule its job."""
    global _location_last_check, _location_next_check

    from app.database import SessionLocal
    from app.models import Location, AvailabilityLog, CheckLog
    from app.scrapers.reservecalifornia import ReserveCaliforniaScraper
    from app.scrapers.crystal_pier import CrystalPierScraper
    from app.scrapers.crystal_cove import CrystalCoveScraper
    from app.notifications.pushover import send_availability_alert

    scraper_map = {
        "reserveca": ReserveCaliforniaScraper,
        "crystal_pier": CrystalPierScraper,
        "crystal_cove": CrystalCoveScraper,
    }

    dates = get_target_dates()
    db = SessionLocal()

    try:
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location or not location.enabled:
            logger.info("Location %d not found or disabled, skipping", location_id)
            return

        _location_last_check[location_id] = datetime.now(timezone.utc)

        scraper_cls = scraper_map.get(location.scraper_type)
        if not scraper_cls:
            logger.warning("No scraper for type: %s", location.scraper_type)
            return

        try:
            scraper = scraper_cls(location)
            results = await scraper.check_availability(dates)

            check_log = CheckLog(
                location_id=location.id,
                status="ok" if results is not None else "no_availability",
                units_found=len(results),
            )
            db.add(check_log)

            for result in results:
                existing = (
                    db.query(AvailabilityLog)
                    .filter(
                        AvailabilityLog.location_id == result.location_id,
                        AvailabilityLog.check_in_date == result.check_in_date,
                        AvailabilityLog.unit_id == result.unit_id,
                        AvailabilityLog.still_available == True,
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
                    still_available=True,
                )
                db.add(log_entry)
                db.flush()

                notified = await send_availability_alert(
                    location_name=location.name,
                    unit_desc=result.unit_description,
                    check_in_date=result.check_in_date,
                    price=result.price_per_night,
                    booking_url=result.booking_url,
                )
                if notified:
                    log_entry.notified_at = datetime.now(timezone.utc)

            await _mark_stale(db, location, results)
            db.commit()
            logger.info("  %s: %d available unit(s)", location.name, len(results))

        except Exception as e:
            db.rollback()
            db.add(CheckLog(
                location_id=location.id,
                status="error",
                units_found=0,
                error_message=str(e)[:500],
            ))
            db.commit()
            logger.error("Error checking %s: %s", location.name, e)

        # Reschedule this location's job based on its scraper type
        interval = get_interval_for_scraper_type(location.scraper_type)
        job_id = f"check_{location.slug}"
        job = scheduler.get_job(job_id)
        if job:
            job.reschedule(trigger=IntervalTrigger(minutes=interval))
        _location_next_check[location_id] = datetime.now(timezone.utc) + timedelta(minutes=interval)
        logger.info("Next check for %s in %d minutes", location.name, interval)

    finally:
        db.close()


async def run_checks():
    """Run availability checks for all enabled locations concurrently (used by Check Now)."""
    from app.database import SessionLocal
    from app.models import Location

    db = SessionLocal()
    try:
        locations = db.query(Location).filter(Location.enabled == True).all()
        location_ids = [loc.id for loc in locations]
        logger.info("Triggering checks for %d enabled location(s)", len(location_ids))
    finally:
        db.close()

    await asyncio.gather(*[run_check_for_location(lid) for lid in location_ids])


async def _mark_stale(db, location, current_results):
    """Mark availability log entries as no longer available if not seen this check."""
    from app.models import AvailabilityLog

    current_keys = {(r.unit_id, r.check_in_date) for r in current_results}
    active_logs = (
        db.query(AvailabilityLog)
        .filter(
            AvailabilityLog.location_id == location.id,
            AvailabilityLog.still_available == True,
        )
        .all()
    )
    for log in active_logs:
        if (log.unit_id, log.check_in_date) not in current_keys:
            log.still_available = False


def _add_location_job(location) -> None:
    """Add or replace an APScheduler job for a single location."""
    interval = get_interval_for_scraper_type(location.scraper_type)
    job_id = f"check_{location.slug}"
    scheduler.add_job(
        run_check_for_location,
        args=[location.id],
        trigger=IntervalTrigger(minutes=interval),
        id=job_id,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _location_next_check[location.id] = datetime.now(timezone.utc) + timedelta(minutes=interval)
    logger.info("Registered job %s (every %d min)", job_id, interval)


def add_location_job(location) -> None:
    """Public API: add/re-add a job when a location is enabled."""
    _add_location_job(location)


def remove_location_job(slug: str) -> None:
    """Public API: remove the job for a location when it is disabled."""
    job_id = f"check_{slug}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed job %s", job_id)


def start_scheduler():
    """Start APScheduler with one job per enabled location."""
    from app.database import SessionLocal
    from app.models import Location

    db = SessionLocal()
    try:
        locations = db.query(Location).filter(Location.enabled == True).all()
        for location in locations:
            _add_location_job(location)
    finally:
        db.close()

    scheduler.start()
    logger.info("Scheduler started with %d location job(s).", len(_location_next_check))


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
