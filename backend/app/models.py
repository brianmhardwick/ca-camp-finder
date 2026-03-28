from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    scraper_type: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    booking_url: Mapped[str] = mapped_column(String, nullable=False)
    scraper_config: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    availability_logs: Mapped[list["AvailabilityLog"]] = relationship(back_populates="location")
    check_logs: Mapped[list["CheckLog"]] = relationship(back_populates="location")


class AvailabilityLog(Base):
    __tablename__ = "availability_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"), nullable=False)
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit_description: Mapped[str] = mapped_column(String, nullable=False)
    unit_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    unit_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price_per_night: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    booking_url: Mapped[str] = mapped_column(String, nullable=False)
    still_available: Mapped[bool] = mapped_column(Boolean, default=True)

    location: Mapped["Location"] = relationship(back_populates="availability_logs")


class CheckLog(Base):
    __tablename__ = "check_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String, nullable=False)  # ok, error, no_availability
    units_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    location: Mapped["Location"] = relationship(back_populates="check_logs")
