from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location, CheckLog
from app.schemas import LocationResponse, LocationToggle

router = APIRouter(prefix="/api/locations", tags=["locations"])


def _last_checked(location: Location, db: Session) -> Optional[datetime]:
    log = (
        db.query(CheckLog)
        .filter(CheckLog.location_id == location.id)
        .order_by(CheckLog.checked_at.desc())
        .first()
    )
    return log.checked_at if log else None


def _last_found(location: Location, db: Session) -> Optional[datetime]:
    from app.models import AvailabilityLog
    log = (
        db.query(AvailabilityLog)
        .filter(AvailabilityLog.location_id == location.id)
        .order_by(AvailabilityLog.detected_at.desc())
        .first()
    )
    return log.detected_at if log else None


@router.get("", response_model=list[LocationResponse])
def list_locations(db: Session = Depends(get_db)):
    locations = db.query(Location).order_by(Location.id).all()
    return [
        LocationResponse(
            id=loc.id,
            name=loc.name,
            slug=loc.slug,
            scraper_type=loc.scraper_type,
            enabled=loc.enabled,
            booking_url=loc.booking_url,
            last_checked=_last_checked(loc, db),
            last_found=_last_found(loc, db),
        )
        for loc in locations
    ]


@router.patch("/{slug}", response_model=LocationResponse)
def toggle_location(slug: str, body: LocationToggle, db: Session = Depends(get_db)):
    from app.scheduler.runner import add_location_job, remove_location_job

    location = db.query(Location).filter(Location.slug == slug).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    location.enabled = body.enabled
    db.commit()
    db.refresh(location)

    if body.enabled:
        add_location_job(location)
    else:
        remove_location_job(location.slug)

    return LocationResponse(
        id=location.id,
        name=location.name,
        slug=location.slug,
        scraper_type=location.scraper_type,
        enabled=location.enabled,
        booking_url=location.booking_url,
        last_checked=_last_checked(location, db),
        last_found=_last_found(location, db),
    )
