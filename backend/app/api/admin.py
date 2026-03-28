from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AvailabilityLog, Location, CheckLog
from app.scheduler.runner import get_last_check, get_next_check, run_checks
from app.scheduler.windows import get_current_interval
from app.schemas import HealthResponse, SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    enabled_count = db.query(Location).filter(Location.enabled == True).count()
    today = date.today()
    found_today = (
        db.query(AvailabilityLog)
        .filter(AvailabilityLog.detected_at >= datetime.combine(today, datetime.min.time()))
        .count()
    )
    return HealthResponse(
        status="ok",
        locations_enabled=enabled_count,
        total_found_today=found_today,
        last_check=get_last_check(),
        next_check=get_next_check(),
        current_interval_minutes=get_current_interval(),
    )


@router.post("/check/now", status_code=202)
async def check_now():
    """Trigger an immediate availability check for all enabled locations."""
    import asyncio
    asyncio.create_task(run_checks())
    return {"message": "Check triggered"}


@router.get("/settings", response_model=SettingsResponse)
def get_settings():
    return SettingsResponse(
        default_check_interval=settings.default_check_interval,
        peak_window_interval=settings.peak_window_interval,
        scan_days_ahead=settings.scan_days_ahead,
    )


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate):
    if body.default_check_interval is not None:
        settings.default_check_interval = body.default_check_interval
    if body.peak_window_interval is not None:
        settings.peak_window_interval = body.peak_window_interval
    if body.scan_days_ahead is not None:
        settings.scan_days_ahead = body.scan_days_ahead
    return SettingsResponse(
        default_check_interval=settings.default_check_interval,
        peak_window_interval=settings.peak_window_interval,
        scan_days_ahead=settings.scan_days_ahead,
    )


@router.post("/notify/test", status_code=200)
async def test_notification():
    """Send a test Pushover notification to verify credentials."""
    from app.notifications.pushover import send_test_notification
    success = await send_test_notification()
    if success:
        return {"message": "Test notification sent"}
    return {"message": "Failed — check PUSHOVER credentials in .env"}
