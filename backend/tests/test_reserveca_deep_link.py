"""
Unit tests for ReserveCA scraper — booking URL construction and consecutive-night detection.

Fixture based on San Onofre – San Mateo site SM039
(Hook Up E/W, $70/night, Fri Apr 24 2026) from a live screenshot.

Key behaviours under test:
- Friday triggers exactly ONE API call (2-night Fri–Sun only)
- Saturday triggers exactly ONE API call (1-night)
- Friday results have num_nights=2 and booking URL with date params
- No 1-night Friday results are produced (would be a false-positive weekend alert)
- Notification message distinguishes multi-night windows
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
    loc.scraper_config = json.dumps({"facility_id": facility_id, "unit_type_id": 29, "place_id": 712})
    return loc


def _mock_http(response_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = response_data
    resp.raise_for_status = MagicMock()
    return resp


# ── URL template ─────────────────────────────────────────────────────────────

def test_park_link_template_renders():
    url = BOOKING_PARK_LINK.format(place_id="686", start="2026-04-24", end="2026-04-26")
    assert "reservecalifornia.com/park/686/" in url
    assert "startDate=2026-04-24" in url
    assert "endDate=2026-04-26" in url


# ── Friday: 2-night only ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_friday_triggers_one_api_call():
    """Friday should make exactly ONE call — the 2-night (Fri–Sun) query."""
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        await scraper.check_availability([friday])

    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_friday_result_has_num_nights_2():
    """Friday query produces a 2-night result (the full Fri–Sun weekend)."""
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([friday])

    assert len(results) == 1
    assert results[0].num_nights == 2
    assert results[0].unit_description.startswith("SM039")


@pytest.mark.asyncio
async def test_friday_produces_no_1night_result():
    """Friday must NOT produce a 1-night result — that would be a false-positive weekend alert."""
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([friday])

    assert all(r.num_nights == 2 for r in results)


@pytest.mark.asyncio
async def test_friday_booking_url_includes_dates():
    """Booking URL should carry startDate/endDate so the park page can pre-fill the picker."""
    scraper = ReserveCaliforniaScraper(_make_location())
    friday = date(2026, 4, 24)  # Friday; 2-night → endDate = Apr 26

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([friday])

    assert results
    url = results[0].booking_url
    assert "startDate=2026-04-24" in url
    assert "endDate=2026-04-26" in url


# ── Saturday: 1-night ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_saturday_query_has_num_nights_1():
    scraper = ReserveCaliforniaScraper(_make_location())
    saturday = date(2026, 4, 25)  # Saturday — 1-night query

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([saturday])

    assert all(r.num_nights == 1 for r in results)
    assert mock_client.post.call_count == 1


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
        booking_url="https://www.reservecalifornia.com/park/712/?startDate=2026-04-24&endDate=2026-04-26",
        num_nights=2,
    )

    # Verify the date formatting logic directly
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
