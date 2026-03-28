"""
Campland on the Bay scraper.
Campland uses a proprietary booking system at campland.com.
We use Playwright headless Chromium to navigate their availability calendar
and detect open site types for target Fri/Sat/Sun dates.

Cancellation policy: 72-hour window
- Cancel 72+ hours before arrival → full refund minus $30 fee
- Cancel within 72 hours → forfeit first night
Minimum stay: 2 nights on summer weekends (Fri–Sat), 3 nights on holidays.
"""
import logging
from datetime import date
from typing import Optional

from app.scrapers.base import AvailabilityResult, BaseScraper

logger = logging.getLogger(__name__)

CAMPLAND_URL = "https://www.campland.com/"
CAMPLAND_BOOKING_URL = "https://www.campland.com/reservations/"


class CamplandScraper(BaseScraper):
    async def check_availability(self, dates: list[date]) -> list[AvailabilityResult]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Cannot scrape Campland.")
            return []

        results: list[AvailabilityResult] = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            for check_in in dates:
                try:
                    found = await self._check_date(page, check_in)
                    results.extend(found)
                except Exception as e:
                    logger.warning("Campland check failed for %s: %s", check_in, e)

            await browser.close()
        return results

    async def _check_date(self, page, check_in: date) -> list[AvailabilityResult]:
        """Navigate to Campland booking page and check availability for a date."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        # Campland requires a 3-night minimum on weekends
        from datetime import timedelta
        check_out = check_in + timedelta(days=3)

        url = (
            f"{CAMPLAND_BOOKING_URL}"
            f"?arrive={check_in.strftime('%m/%d/%Y')}"
            f"&depart={check_out.strftime('%m/%d/%Y')}"
        )

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        results = []

        try:
            # Wait for availability grid or "no availability" message
            await page.wait_for_selector(
                "[class*='available'], [class*='site'], [class*='unit'], "
                "[class*='campsite'], .availability-grid, #availability",
                timeout=15000,
            )
        except PlaywrightTimeout:
            # Try a broader check on page content
            pass

        page_text = (await page.content()).lower()

        # Check for hard "no availability" signals
        no_avail_signals = ["no availability", "no sites available", "sold out", "fully booked"]
        if any(sig in page_text for sig in no_avail_signals):
            return results

        # Look for available site elements
        available_els = await page.query_selector_all(
            "[class*='available']:not([class*='not-available']):not([class*='unavailable']), "
            "[data-available='true'], [data-status='available']"
        )

        for el in available_els:
            try:
                site_name = await el.get_attribute("data-name") or await el.inner_text()
                site_name = site_name.strip().split("\n")[0][:80]
                if not site_name:
                    continue
                price = await self._extract_price(el)
                unit_id = await el.get_attribute("data-id") or await el.get_attribute("id")

                results.append(
                    AvailabilityResult(
                        location_id=self.location.id,
                        check_in_date=check_in,
                        unit_description=site_name,
                        unit_id=unit_id,
                        unit_type="RV / Campsite",
                        price_per_night=price,
                        booking_url=url,
                    )
                )
            except Exception:
                continue

        # Fallback: if page shows booking/select signals but we couldn't parse elements
        if not results:
            avail_signals = ["select site", "book now", "reserve", "add to cart", "available"]
            unavail_signals = ["no availability", "no sites", "sold out", "call to book"]
            if any(sig in page_text for sig in avail_signals) and not any(
                sig in page_text for sig in unavail_signals
            ):
                results.append(
                    AvailabilityResult(
                        location_id=self.location.id,
                        check_in_date=check_in,
                        unit_description="Site available (check campland.com for details)",
                        unit_id=None,
                        unit_type=None,
                        price_per_night=None,
                        booking_url=url,
                    )
                )

        return results

    @staticmethod
    async def _extract_price(element) -> Optional[float]:
        try:
            price_el = await element.query_selector("[class*='price'], .rate, [data-price], .cost")
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
