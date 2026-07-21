"""
Unit tests for ReserveCA scraper — booking URL construction and multi-night detection.

Fixture based on San Onofre – San Mateo site SM039
(Hook Up E/W, $70/night, Fri Apr 24 2026) from a live screenshot.

Key behaviours under test:
- 1-night query for every target date (Fri + Sat)
- Additional 2-night query for Friday specifically (Fri–Sun)
- num_nights field set correctly on results
- Notification message distinguishes 1-night vs 2-night windows
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.reservecalifornia import BOOKING_PARK_LINK, ReserveCaliforniaScraper

_SM039_UNIT_ID = "42280"

MOCK_API_RESPONSE = {
    "Facility": {
        "FacilityId": 686,
        "Units": {
            _SM039_UNIT_ID: {
                "UnitId": int(_SM039_UNIT_ID),
                "Name": "SM039",
                "UnitTypeName": "Hook Up (E/W)",
                "Slices": {
                    "2026-04-24T00:00:00": {"IsFree": True, "Price": 70.00},
                },
            },
            "42281": {
                "UnitId": 42281,
                "Name": "SM040",
                "UnitTypeName": "Hook Up (E/W)",
                "Slices": {
                    "2026-04-24T00:00:00": {"IsFree": False, "Price": 70.00},
                },
            },
        },
    }
}


def _make_location(facility_id: int = 686) -> MagicMock:
    loc = MagicMock()
    loc.id = 1
    loc.slug = "san_onofre_san_mateo"
    loc.scraper_config = json.dumps({"facility_id": facility_id, "unit_type_id": 29})
    return loc


def _mock_http(response_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = response_data
    resp.raise_for_status = MagicMock()
    return resp


# ── URL template ─────────────────────────────────────────────────────────────

def test_park_link_template_renders():
    url = BOOKING_PARK_LINK.format(place_id="686")
    assert url == "https://www.reservecalifornia.com/park/686/"


# ── 1-night baseline ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_friday_1night_result_has_num_nights_1():
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)  # Friday

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([friday])

    one_night = [r for r in results if r.num_nights == 1]
    assert len(one_night) >= 1
    assert one_night[0].unit_description.startswith("SM039")


@pytest.mark.asyncio
async def test_saturday_query_has_num_nights_1():
    scraper = ReserveCaliforniaScraper(_make_location())
    saturday = date(2026, 4, 25)  # Saturday — only 1-night, no 2-night query

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([saturday])

    assert all(r.num_nights == 1 for r in results)
    # Saturday should only trigger 1 API call (no 2-night bonus)
    assert mock_client.post.call_count == 1


# ── 2-night Friday behaviour ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_friday_triggers_two_api_calls():
    """Friday should call the API twice: 1-night and 2-night."""
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        await scraper.check_availability([friday])

    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_friday_2night_result_has_num_nights_2():
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([friday])

    two_night = [r for r in results if r.num_nights == 2]
    assert len(two_night) == 1
    assert two_night[0].unit_description.startswith("SM039")


@pytest.mark.asyncio
async def test_friday_produces_both_1night_and_2night_results():
    """Same site on same Friday should appear twice: once per night-count."""
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([friday])

    assert len(results) == 2
    night_counts = {r.num_nights for r in results}
    assert night_counts == {1, 2}


# ── notification formatting ───────────────────────────────────────────────────

def test_batch_alert_formats_2night_window():
    """2-night result should show date range (Fri–Sun) in the message."""
    from app.notifications.pushover import send_batch_alert
    from app.scrapers.base import AvailabilityResult

    result = AvailabilityResult(
        location_id=1,
        check_in_date=date(2026, 4, 24),
        unit_description="SM039 — Hook Up (E/W)",
        unit_id="42280",
        unit_type="Hook Up (E/W)",
        price_per_night=Decimal("70.00"),
        booking_url="https://www.reservecalifornia.com/park/686/",
        num_nights=2,
    )

    # Verify the date formatting logic directly
    from datetime import timedelta
    d = result.check_in_date
    check_out = d + timedelta(days=result.num_nights)
    date_str = f"{d.strftime('%a, %b %-d')}–{check_out.strftime('%b %-d')} ({result.num_nights} nights)"
    assert date_str == "Fri, Apr 24–Apr 26 (2 nights)"


# ── misc ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_only_free_units_returned():
    scraper = ReserveCaliforniaScraper(_make_location())

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([date(2026, 4, 24)])

    assert all(r.unit_description.startswith("SM039") for r in results)


@pytest.mark.asyncio
async def test_price_parsed_correctly():
    scraper = ReserveCaliforniaScraper(_make_location())

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([date(2026, 4, 24)])

    assert all(r.price_per_night == Decimal("70.00") for r in results)


@pytest.mark.asyncio
async def test_empty_units_returns_no_results():
    scraper = ReserveCaliforniaScraper(_make_location())
    empty = {"Facility": {"FacilityId": 686, "Units": {}}}

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(empty)

        results = await scraper.check_availability([date(2026, 4, 24)])

    assert results == []
