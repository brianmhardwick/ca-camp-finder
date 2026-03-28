from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


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


class CheckLogResponse(BaseModel):
    id: int
    location_id: int
    checked_at: datetime
    status: str
    units_found: int
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    locations_enabled: int
    total_found_today: int
    last_check: Optional[datetime]
    next_check: Optional[datetime]
    current_interval_minutes: int


class SettingsResponse(BaseModel):
    default_check_interval: int
    peak_window_interval: int
    scan_days_ahead: int


class SettingsUpdate(BaseModel):
    default_check_interval: Optional[int] = None
    peak_window_interval: Optional[int] = None
    scan_days_ahead: Optional[int] = None
