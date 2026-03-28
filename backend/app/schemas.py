from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


def _utc(v: Optional[datetime]) -> Optional[datetime]:
    """Attach UTC to naive datetimes (SQLite returns naive even for tz columns)."""
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class LocationResponse(BaseModel):
    id: int
    name: str
    slug: str
    scraper_type: str
    enabled: bool
    booking_url: str
    last_checked: Optional[datetime] = None
    last_found: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("last_checked", "last_found", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        return _utc(v)


class LocationToggle(BaseModel):
    enabled: bool


class AvailabilityLogResponse(BaseModel):
    id: int
    location_id: int
    location_name: str
    check_in_date: date
    unit_description: str
    unit_type: Optional[str] = None
    price_per_night: Optional[Decimal] = None
    detected_at: datetime
    booking_url: str
    still_available: bool

    model_config = {"from_attributes": True}

    @field_validator("detected_at", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        return _utc(v)


class CheckLogResponse(BaseModel):
    id: int
    location_id: int
    checked_at: datetime
    status: str
    units_found: int
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("checked_at", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        return _utc(v)


class HealthResponse(BaseModel):
    status: str
    locations_enabled: int
    total_found_today: int
    last_check: Optional[datetime]
    next_check: Optional[datetime]
    current_interval_minutes: int

    @field_validator("last_check", "next_check", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        return _utc(v)


class SettingsResponse(BaseModel):
    default_check_interval: int
    peak_window_interval: int
    scan_days_ahead: int


class SettingsUpdate(BaseModel):
    default_check_interval: Optional[int] = None
    peak_window_interval: Optional[int] = None
    scan_days_ahead: Optional[int] = None
