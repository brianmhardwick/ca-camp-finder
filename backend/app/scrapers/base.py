from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from app.models import Location


@dataclass
class AvailabilityResult:
    location_id: int
    check_in_date: date
    unit_description: str
    unit_id: Optional[str]
    unit_type: Optional[str]
    price_per_night: Optional[Decimal]
    booking_url: str


class BaseScraper(ABC):
    def __init__(self, location: Location):
        self.location = location

    @abstractmethod
    async def check_availability(self, dates: list[date]) -> list[AvailabilityResult]:
        """Check availability for the given dates. Returns list of available units."""
        ...
