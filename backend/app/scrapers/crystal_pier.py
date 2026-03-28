"""
Crystal Pier Hotel scraper.
Crystal Pier uses a third-party booking widget (ResNexus).
We use Playwright headless Chromium to navigate their reservations calendar
and extract available room types for target dates.
"""
import logging
from datetime import date
from typing import Optional

from app.scrapers.base import AvailabilityResult, BaseScraper

logger = logging.getLogger(__name__)

CRYSTAL_PIER_URL = "https://www.crystalpier.com/reservations/"
# ResNexus iframe endpoint (determined via DevTools inspection)
RESNEXUS_BASE = "https://app.resnexus.com/resnexus/reservations/grid"


class CrystalPierScraper(BaseScraper):
    async def check_availability(self, dates: list[date]) -> list[AvailabilityResult]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Cannot scrape Crystal Pier.")
            return []

        results: list[AvailabilityResult] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
                ),
                viewport={"width": 390, "height": 844},
            )
            page = await context.new_page()

            for check_in in dates:
                try:
                    found = await self._check_date(page, check_in)
                    results.extend(found)
                except Exception as e:
                    logger.warning("Crystal Pier check failed for %s: %s", check_in, e)

            await browser.close()
        return results

    async def _check_date(self, page, check_in: date) -> list[AvailabilityResult]:
        """Navigate to Crystal Pier reservations and check a specific date."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        url = (
            f"{CRYSTAL_PIER_URL}?arrivalDate={check_in.strftime('%Y-%m-%d')}"
            f"&departureDate={check_in.strftime('%Y-%m-%d')}&rooms=1&adults=2"
        )

        await page.goto(url, wait_until="networkidle", timeout=30000)

        results = []

        # Look for available room/cottage tiles — Crystal Pier uses ResNexus
        # The page embeds a ResNexus grid; look for availability indicators
        try:
            await page.wait_for_selector(".rn-unit, .room-available, [class*='available']", timeout=8000)
        except PlaywrightTimeout:
            # No availability widget found for this date
            return results

        # Extract available room types
        available_rooms = await page.query_selector_all(
            ".rn-unit.available, .room-available, [data-available='true']"
        )

        for room_el in available_rooms:
            room_name = await room_el.get_attribute("data-name") or await room_el.inner_text()
            room_name = room_name.strip().split("\n")[0][:80]
            price = await self._extract_price(room_el)

            results.append(
                AvailabilityResult(
                    location_id=self.location.id,
                    check_in_date=check_in,
                    unit_description=room_name or "Room Available",
                    unit_id=await room_el.get_attribute("data-id"),
                    unit_type="Hotel Room / Cottage",
                    price_per_night=price,
                    booking_url=url,
                )
            )

        # If we couldn't parse room-level detail but the page shows availability,
        # fall back to a single "availability detected" result
        if not results:
            page_text = await page.content()
            availability_signals = ["available", "select", "book now", "reserve"]
            if any(sig in page_text.lower() for sig in availability_signals):
                results.append(
                    AvailabilityResult(
                        location_id=self.location.id,
                        check_in_date=check_in,
                        unit_description="Room available (check site for details)",
                        unit_id=None,
                        unit_type=None,
                        price_per_night=None,
                        booking_url=CRYSTAL_PIER_URL,
                    )
                )

        return results

    @staticmethod
    async def _extract_price(element) -> Optional[float]:
        try:
            price_el = await element.query_selector("[class*='price'], .rate, [data-price]")
            if price_el:
                text = await price_el.inner_text()
                import re
                from decimal import Decimal
                match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                if match:
                    return Decimal(match.group()).quantize(Decimal("0.01"))
        except Exception:
            pass
        return None
