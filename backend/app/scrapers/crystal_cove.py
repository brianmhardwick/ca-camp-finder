"""
Crystal Cove State Park Cottages scraper.
Uses the same ReserveCA API as other state parks (facility_id=728),
with unit_type_id=0 to capture all cottage types.
"""
from datetime import date

from app.scrapers.base import AvailabilityResult
from app.scrapers.reservecalifornia import ReserveCaliforniaScraper


class CrystalCoveScraper(ReserveCaliforniaScraper):
    """Crystal Cove uses the ReserveCA API — facility 728, all unit types."""

    async def check_availability(self, dates: list[date]) -> list[AvailabilityResult]:
        results = await super().check_availability(dates)
        # Tag all results with cottage context for clarity in notifications
        for r in results:
            if "cottage" not in r.unit_description.lower() and "cabin" not in r.unit_description.lower():
                r.unit_description = f"Cottage: {r.unit_description}"
        return results
