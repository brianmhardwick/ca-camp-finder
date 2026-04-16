"""
ReserveCA scraper using the Tyler Technologies Recreation Management API.
Endpoint: https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com/rdr/search/grid
"""
import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import httpx

from app.scrapers.base import AvailabilityResult, BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com/rdr/search/grid"
BOOKING_DEEP_LINK = "https://www.reservecalifornia.com/park/{place_id}/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Content-Type": "application/json",
    "Referer": "https://www.reservecalifornia.com/",
    "Origin": "https://www.reservecalifornia.com",
}


class ReserveCaliforniaScraper(BaseScraper):
    def __init__(self, location):
        super().__init__(location)
        cfg = json.loads(location.scraper_config)
        self.facility_id: int = cfg["facility_id"]
        self.unit_type_id: int = cfg.get("unit_type_id", 0)
        self.place_id: int = cfg.get("place_id", self.facility_id)

    async def check_availability(self, dates: list[date]) -> list[AvailabilityResult]:
        results: list[AvailabilityResult] = []
        if not dates:
            return results

        async with httpx.AsyncClient(timeout=30) as client:
            for check_in in dates:
                check_out = check_in + timedelta(days=1)
                try:
                    batch = await self._fetch_date(client, check_in, check_out)
                    results.extend(batch)
                except Exception as e:
                    logger.warning(
                        "ReserveCA fetch failed for %s facility=%s date=%s: %s",
                        self.location.slug, self.facility_id, check_in, e
                    )
        return results

    async def _fetch_date(
        self, client: httpx.AsyncClient, check_in: date, check_out: date
    ) -> list[AvailabilityResult]:
        payload = {
            "FacilityId": self.facility_id,
            "UnitSort": "availability",
            "StartDate": check_in.strftime("%Y-%m-%d"),
            "EndDate": check_out.strftime("%Y-%m-%d"),
            "InSeasonOnly": True,
            "WebOnly": True,
            "IsADA": False,
            "RestrictADA": False,
            "UnitCategoryId": 0,
            "SleepingUnitId": 0,
            "MinVehicleLength": 0,
            "UnitTypeId": self.unit_type_id,
            "UnitTypesGroupIds": [],
            "AmenityIds": [],
            "CustomerId": 0,
        }
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        results = []
        facility_data = data.get("Facility", {})
        units = facility_data.get("Units") or {}

        # New API uses ISO datetime keys: "2026-07-18T00:00:00"
        date_key = check_in.strftime("%Y-%m-%dT%H:%M:%S")

        for unit_id, unit in units.items():
            if not isinstance(unit, dict):
                continue
            slices = unit.get("Slices") or {}
            slice_data = slices.get(date_key)
            if not slice_data:
                continue

            is_available = slice_data.get("IsFree", False)
            if not is_available:
                continue

            unit_name = unit.get("Name", f"Site {unit_id}")
            unit_type = unit.get("UnitTypeName") or ""
            price = self._parse_price(slice_data.get("Price"))

            booking_url = BOOKING_DEEP_LINK.format(place_id=self.place_id)
            desc = f"{unit_name} — {unit_type}" if unit_type else unit_name

            results.append(
                AvailabilityResult(
                    location_id=self.location.id,
                    check_in_date=check_in,
                    unit_description=desc,
                    unit_id=str(unit_id),
                    unit_type=unit_type,
                    price_per_night=price,
                    booking_url=booking_url,
                )
            )
        return results

    @staticmethod
    def _parse_price(price_val) -> Optional[Decimal]:
        if price_val is None:
            return None
        try:
            return Decimal(str(price_val)).quantize(Decimal("0.01"))
        except Exception:
            return None
