"""
ReserveCA scraper using the unofficial Aspira/UseDirect JSON API.
Endpoint: https://calirdr.usedirect.com/rdr/rdr/fd/camping/availability/site
"""
import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import httpx

from app.scrapers.base import AvailabilityResult, BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://calirdr.usedirect.com/rdr/rdr/fd/camping/availability/site"
BOOKING_DEEP_LINK = "https://www.reservecalifornia.com/Web/#!park/{facility_id}/site/{unit_id}/{date}"

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

    async def check_availability(self, dates: list[date]) -> list[AvailabilityResult]:
        results: list[AvailabilityResult] = []
        if not dates:
            return results

        # Group dates into contiguous windows to minimize API calls
        # Send one request per date as a 1-night stay check
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
            "FacilityId": str(self.facility_id),
            "StartDate": check_in.strftime("%m-%d-%Y"),
            "EndDate": check_out.strftime("%m-%d-%Y"),
            "MinVehicleLength": 0,
            "UnitTypeId": self.unit_type_id,
            "WebOnly": True,
            "IsADA": False,
            "SleepingUnitId": 83,  # default sleeping unit
            "UnitCategoryId": 0,
        }
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        results = []
        facility_data = data.get("Facility", {})
        units = facility_data.get("Units", {})

        for unit_id, unit in units.items():
            if not isinstance(unit, dict):
                continue
            slices = unit.get("Slices", {})
            date_key = check_in.strftime("%-m/%-d/%Y")
            # Try multiple date key formats
            slice_data = slices.get(date_key) or slices.get(check_in.strftime("%m/%d/%Y"))
            if not slice_data:
                continue

            is_available = slice_data.get("IsFree", False)
            if not is_available:
                continue

            unit_type = unit.get("UnitTypeName", "")
            unit_name = unit.get("Name", f"Site {unit_id}")
            price = self._parse_price(slice_data.get("Price"))

            booking_url = BOOKING_DEEP_LINK.format(
                facility_id=self.facility_id,
                unit_id=unit_id,
                date=check_in.strftime("%m/%d/%Y"),
            )

            results.append(
                AvailabilityResult(
                    location_id=self.location.id,
                    check_in_date=check_in,
                    unit_description=f"{unit_name} — {unit_type}",
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
