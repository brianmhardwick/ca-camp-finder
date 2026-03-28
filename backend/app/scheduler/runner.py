"""
APScheduler-based job runner.
Manages a single recurring job that checks all enabled locations.
The interval is recalculated after each run based on the current cancellation window.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.scheduler.windows import get_current_interval

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_last_check: Optional[datetime] = None
_next_check: Optional[datetime] = None


def get_last_check() -> Optional[datetime]:
    return _last_check


def get_next_check() -> Optional[datetime]:
    return _next_check


def get_target_dates() -> list[date]:
    """Return all Fri/Sat/Sun dates within the scan window."""
    today = date.today()
    target = []
    for i in range(settings.scan_days_ahead):
        d = today + timedelta(days=i)
        if d.weekday() in (4, 5, 6):  # Fri=4, Sat=5, Sun=6
            target.append(d)
    return target


async def run_checks():
    """Run availability checks for all enabled locations."""
    global _last_check, _next_check

    from app.database import SessionLocal
    from app.models import Location, AvailabilityLog, CheckLog
    from app.scrapers.reservecalifornia import ReserveCaliforniaScraper
    from app.scrapers.crystal_pier import CrystalPierScraper
    from app.scrapers.crystal_cove import CrystalCoveScraper
    from app.notifications.pushover import send_availability_alert

    _last_check = datetime.utcnow()

    scraper_map = {
        "reserveca": ReserveCaliforniaScraper,
        "crystal_pier": CrystalPierScraper,
        "crystal_cove": CrystalCoveScraper,
    }

    dates = get_target_dates()
    db = SessionLocal()

    try:
        locations = db.query(Location).filter(Location.enabled == True).all()
        logger.info("Running checks for %d enabled location(s) across %d dates", len(locations), len(dates))

        for location in locations:
            scraper_cls = scraper_map.get(location.scraper_type)
            if not scraper_cls:
                logger.warning("No scraper for type: %s", location.scraper_type)
                continue

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
                    # Deduplication: skip if we already have an active log for this unit+date
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
                        continue  # already notified, still available

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

                    # Send Pushover notification
                    notified = await send_availability_alert(
                        location_name=location.name,
                        unit_desc=result.unit_description,
                        check_in_date=result.check_in_date,
                        price=result.price_per_night,
                        booking_url=result.booking_url,
                    )
                    if notified:
                        log_entry.notified_at = datetime.utcnow()

                # Mark previously-found units as gone if they no longer appear
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

    finally:
        db.close()

    # Reschedule with the new interval based on current window
    _reschedule()


async def _mark_stale(db, location, current_results):
    """Mark availability log entries as no longer available if they weren't seen this check."""
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


def _reschedule():
    """Update the scheduler interval based on the current cancellation window."""
    global _next_check
    interval = get_current_interval()
    job = scheduler.get_job("availability_check")
    if job:
        job.reschedule(trigger=IntervalTrigger(minutes=interval))
    _next_check = datetime.utcnow() + timedelta(minutes=interval)
    logger.info("Next check in %d minutes", interval)


def start_scheduler():
    """Start APScheduler with the initial interval."""
    global _next_check
    interval = get_current_interval()
    scheduler.add_job(
        run_checks,
        trigger=IntervalTrigger(minutes=interval),
        id="availability_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _next_check = datetime.utcnow() + timedelta(minutes=interval)
    logger.info("Scheduler started. First check in %d minutes.", interval)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
