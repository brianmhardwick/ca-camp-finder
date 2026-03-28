from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AvailabilityLog, Location
from app.schemas import AvailabilityLogResponse

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=list[AvailabilityLogResponse])
def list_logs(
    location: str | None = Query(None, description="Filter by location slug"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(AvailabilityLog, Location.name).join(
        Location, Location.id == AvailabilityLog.location_id
    )
    if location:
        query = query.filter(Location.slug == location)
    query = query.order_by(AvailabilityLog.detected_at.desc()).offset(offset).limit(limit)

    results = []
    for log, loc_name in query.all():
        results.append(
            AvailabilityLogResponse(
                id=log.id,
                location_id=log.location_id,
                location_name=loc_name,
                check_in_date=log.check_in_date,
                unit_description=log.unit_description,
                unit_type=log.unit_type,
                price_per_night=log.price_per_night,
                detected_at=log.detected_at,
                booking_url=log.booking_url,
                still_available=log.still_available,
            )
        )
    return results


@router.delete("/{log_id}", status_code=204)
def delete_log(log_id: int, db: Session = Depends(get_db)):
    log = db.query(AvailabilityLog).filter(AvailabilityLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(log)
    db.commit()
