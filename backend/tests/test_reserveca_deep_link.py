"""
Unit tests for ReserveCA booking URL deep-link construction.

Fixture is based on the real San Onofre – San Mateo site SM039
(Hook Up E/W, $70/night, Fri Apr 24 2026) from a live screenshot.
Unit ID 42280 is a stand-in; the real ID is assigned by the API at
runtime — URL construction logic is what's under test here.

Note: the remote migrated to the Tyler Technologies API; mock data uses
the new ISO datetime slice keys ("2026-04-24T00:00:00").
"""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.reservecalifornia import BOOKING_DEEP_LINK, BOOKING_PARK_LINK, ReserveCaliforniaScraper

_SM039_UNIT_ID = "42280"

# Mirrors the Tyler Technologies API response shape for facility 686.
# SM039 is free; SM040 is taken.
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


# ── template sanity ───────────────────────────────────────────────────────────

def test_deep_link_template_targets_campsite():
    """`BOOKING_DEEP_LINK` must use {unit_id}, not {place_id} or {facility_id}."""
    assert "{unit_id}" in BOOKING_DEEP_LINK
    assert "{place_id}" not in BOOKING_DEEP_LINK
    assert "{facility_id}" not in BOOKING_DEEP_LINK
    assert "/camping/" in BOOKING_DEEP_LINK


def test_deep_link_template_renders():
    url = BOOKING_DEEP_LINK.format(unit_id="42280")
    assert url == "https://www.reservecalifornia.com/camping/42280/"


def test_park_link_template_renders():
    url = BOOKING_PARK_LINK.format(place_id="686")
    assert url == "https://www.reservecalifornia.com/park/686/"


# ── scraper output ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_booking_url_is_unit_deep_link():
    """Generated URL must point to the specific campsite, not the park search page."""
    scraper = ReserveCaliforniaScraper(_make_location())

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([date(2026, 4, 24)])

    assert len(results) == 1
    url = results[0].booking_url
    assert url == f"https://www.reservecalifornia.com/camping/{_SM039_UNIT_ID}/"
    assert "/camping/" in url
    assert "/park/" not in url


@pytest.mark.asyncio
async def test_only_free_units_returned():
    """SM040 is not free — only SM039 should appear."""
    scraper = ReserveCaliforniaScraper(_make_location())

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([date(2026, 4, 24)])

    assert len(results) == 1
    assert results[0].unit_description.startswith("SM039")


@pytest.mark.asyncio
async def test_unit_description_includes_site_name_and_type():
    """Notification message needs both site name and hook-up type readable at a glance."""
    scraper = ReserveCaliforniaScraper(_make_location())

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([date(2026, 4, 24)])

    desc = results[0].unit_description
    assert "SM039" in desc
    assert "Hook Up (E/W)" in desc


@pytest.mark.asyncio
async def test_price_parsed_correctly():
    scraper = ReserveCaliforniaScraper(_make_location())

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = _mock_http(MOCK_API_RESPONSE)

        results = await scraper.check_availability([date(2026, 4, 24)])

    assert results[0].price_per_night == Decimal("70.00")


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
