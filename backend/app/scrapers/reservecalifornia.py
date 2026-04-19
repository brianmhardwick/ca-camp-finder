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

        async with httpx.AsyncClient(timeout=30) as client:
            for check_in in dates:
                # Friday check-ins: require 2 consecutive nights free (Fri→Sun).
                # Sat check-ins stay 1-night (Sat→Sun) since Fri→Sun is a superset.
                nights = 2 if check_in.weekday() == 4 else 1
                check_out = check_in + timedelta(days=nights)
                try:
                    batch = await self._fetch_date(client, check_in, check_out, nights)
                    results.extend(batch)
                except Exception as e:
                    logger.warning(
                        "ReserveCA fetch failed for %s facility=%s date=%s: %s",
                        self.location.slug, self.facility_id, check_in, e
                    )
        return results

    async def _fetch_date(
        self, client: httpx.AsyncClient, check_in: date, check_out: date, nights: int = 1
    ) -> list[AvailabilityResult]:
        payload = {
            "FacilityId": str(self.facility_id),
            "StartDate": check_in.strftime("%m-%d-%Y"),
            "EndDate": check_out.strftime("%m-%d-%Y"),
            "MinVehicleLength": 0,
            "UnitTypeId": self.unit_type_id,
            "WebOnly": True,
            "IsADA": False,
            "SleepingUnitId": 83,
            "UnitCategoryId": 0,
        }
        resp = await client.post(BASE_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

        results = []
        units = data.get("Facility", {}).get("Units", {})

        for unit_id, unit in units.items():
            if not isinstance(unit, dict):
                continue
            slices = unit.get("Slices", {})

            # Verify every requested night is free for this unit
            all_free = True
            first_price = None
            for offset in range(nights):
                night = check_in + timedelta(days=offset)
                sl = slices.get(night.strftime("%-m/%-d/%Y")) or slices.get(night.strftime("%m/%d/%Y"))
                if not sl or not sl.get("IsFree", False):
                    all_free = False
                    break
                if offset == 0:
                    first_price = sl.get("Price")

            if not all_free:
                continue

            unit_type = unit.get("UnitTypeName", "")
            unit_name = unit.get("Name", f"Site {unit_id}")

            results.append(
                AvailabilityResult(
                    location_id=self.location.id,
                    check_in_date=check_in,
                    unit_description=f"{unit_name} — {unit_type}",
                    unit_id=str(unit_id),
                    unit_type=unit_type,
                    price_per_night=self._parse_price(first_price),
                    booking_url=self.location.booking_url,
                    nights=nights,
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
